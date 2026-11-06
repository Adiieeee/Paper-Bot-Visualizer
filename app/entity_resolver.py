import json
import logging
import os
import time
from typing import Dict, List, Tuple

import requests

from app.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """\
You are an expert academic knowledge graph curator. 
Your task is Entity Linking (deduplication).
You are given a "Master List of Seen Entities" and a "New Entities Chunk".
For each entity in the "New Entities Chunk", check if it is a duplicate, synonym, or acronym of any entity ALREADY IN the "Master List of Seen Entities".
If it is a duplicate, output a JSON mapping: {{"New Entity": "Matched Entity from Master List"}}.
If it is NOT a duplicate of anything in the Master List, DO NOT include it in the JSON output.
DO NOT group entities that are distinct versions, variants, or opposite concepts (e.g., 'ResNet-44' vs 'ResNet-56' are distinct).
CRITICAL 1: JANGAN gabungkan entitas yang mengandung angka, metrik, atau nomor versi yang berbeda (misal: 'Top-1' vs 'Top-5', 'CIFAR-10' vs 'CIFAR-100', 'ResNet-44' vs 'ResNet-56') meskipun mereka berada dalam kategori yang sama. Mereka adalah entitas yang BERBEDA secara semantik.
CRITICAL 2: JANGAN petakan entitas spesifik ke kategori yang lebih umum (Hypernymy). Contoh: JANGAN petakan 'Top-1 Error' atau 'Top-5 Error' ke 'Classification error'. HANYA gabungkan jika keduanya adalah sinonim yang 100% sama maknanya (seperti 'ConvNet' dan 'Convolutional Neural Network').
Master List of Seen Entities:
{master_list}

New Entities Chunk:
{entity_chunk}

Output ONLY valid JSON. Example: {{"DenseNet": "Dense Convolutional Network"}}
"""

def build_entity_aliases(raw_entities: List[str], cache_path: str = "output/extractions/entity_aliases.json") -> Dict[str, str]:
    """
    Build or load entity aliases using LLM Entity Linking strategy incrementally.
    """
    aliases: Dict[str, str] = {}
    checked_entities: List[str] = []
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "aliases" in data and "checked_entities" in data:
                    aliases = data["aliases"]
                    checked_entities = data["checked_entities"]
                elif isinstance(data, dict):
                    aliases = data
                    # Fallback for old format
                    checked_entities = list(set(aliases.keys()) | set(aliases.values()))
                    
            logger.info(f"Loaded {len(aliases)} aliases and {len(checked_entities)} checked entities from cache.")
        except Exception as e:
            logger.error(f"Failed to read cache {cache_path}: {e}")

    # Determine which entities are truly new
    unique_entities = sorted(list(set(e.strip() for e in raw_entities if e.strip())), key=lambda x: x.lower())
    
    known_lower = {e.lower() for e in checked_entities}
    new_entities = [ent for ent in unique_entities if ent.lower() not in known_lower]
            
    if not new_entities:
        logger.info("No new entities to resolve. 0 LLM API calls will be made.")
        # Ensure we always return the mapping
        return aliases

    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not set. Skipping LLM entity resolution.")
        return aliases

    logger.info(f"Starting LLM Entity Linking for {len(new_entities)} new entities...")
    
    # Master list contains ONLY canonical forms and explicitly standalone checked entities.
    # We rebuild it dynamically here from checked_entities that are not aliases.
    alias_keys_lower = {k.lower() for k in aliases.keys()}
    master_list = [ent for ent in checked_entities if ent.lower() not in alias_keys_lower]
    master_list = sorted(list(set(master_list)), key=lambda x: x.lower())
    
    # Track API Calls
    api_calls = 0

    def _run_llm(master: List[str], chunk: List[str]) -> dict:
        nonlocal api_calls
        if not master:
            return {}
            
        prompt = PROMPT_TEMPLATE.format(
            master_list=json.dumps(master, indent=2),
            entity_chunk=json.dumps(chunk, indent=2)
        )
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"}
        }
        
        # Max retries increased to handle strict 15 RPM
        for attempt in range(5):
            api_calls += 1
            try:
                resp = requests.post(url, json=payload, timeout=40)
                if resp.status_code == 429:
                    # Rate limit exceeded. Try to parse retryDelay, default to 20s.
                    delay = 20
                    try:
                        error_data = resp.json()
                        for detail in error_data.get("error", {}).get("details", []):
                            if detail.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
                                d_str = detail.get("retryDelay", "20s")
                                delay = int(d_str.replace("s", "")) + 2
                    except Exception:
                        pass
                    logger.warning(f"429 Rate Limit on attempt {attempt+1}. Sleeping {delay}s...")
                    time.sleep(delay)
                    continue
                    
                if resp.status_code != 200:
                    logger.error(f"API Error {resp.status_code}: {resp.text}")
                    # If not 429, we still wait and retry
                    time.sleep(5)
                    continue
                    
                data = resp.json()
                raw_text = data['candidates'][0]['content']['parts'][0]['text']
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:-3]
                elif raw_text.startswith("```"):
                    raw_text = raw_text[3:-3]
                    
                return json.loads(raw_text.strip())
            except (json.JSONDecodeError, requests.Timeout, ValueError) as e:
                logger.warning(f"JSON/Timeout Error (attempt {attempt+1}): {e}")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected LLM error: {e}")
                time.sleep(5)
                
        # If all 5 attempts fail, return empty but log it loudly
        logger.error("FATAL: Failed to resolve chunk after 5 retries.")
        return {}

    chunk_size = 20
    chunks = [new_entities[i:i+chunk_size] for i in range(0, len(new_entities), chunk_size)]
    
    print(f"  [API] Memulai proses Entity Linking ke LLM untuk {len(new_entities)} entitas baru ({len(chunks)} chunks)...")
    for i, chunk in enumerate(chunks):
        logger.info(f"Processing LLM chunk {i+1}/{len(chunks)}...")
        print(f"    -> Memproses chunk {i+1}/{len(chunks)}...")
        matches = _run_llm(master_list, chunk)
        
        if matches:
            for new_ent, matched_ent in matches.items():
                if new_ent in chunk:
                    # Match to the canonical version in master_list (case insensitive lookup)
                    final_target = matched_ent
                    visited = set()
                    while final_target in aliases and final_target not in visited:
                        visited.add(final_target)
                        final_target = aliases[final_target]
                    aliases[new_ent] = final_target
                    
        for c in chunk:
            # We add all chunks to checked_entities and master_list
            if c not in checked_entities:
                checked_entities.append(c)
            # Only add to master list if it wasn't deduplicated
            if c not in aliases:
                master_list.append(c)
                
        time.sleep(2) # Normal rate limit protection
        
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({
            "aliases": aliases,
            "checked_entities": checked_entities
        }, f, indent=2, ensure_ascii=False)
        
    logger.info(f"LLM Entity Linking completed. API Calls made: {api_calls}. Saved {len(aliases)} aliases and {len(checked_entities)} checked entities.")
    return aliases
