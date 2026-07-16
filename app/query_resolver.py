import json
import logging
import os
from difflib import SequenceMatcher
from typing import List, Tuple

import requests

from app.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """\
You are an expert at natural language understanding. 
Extract all named entities (methods, datasets, metrics, authors, concepts) mentioned in the following user query.
Return the output STRICTLY as a JSON list of strings. Do not include markdown formatting.

Query: "{query}"
Example Output: ["Entity1", "Entity2"]
"""

def extract_entities_from_query(query: str) -> List[str]:
    """Menggunakan LLM untuk mengekstrak entitas dari pertanyaan."""
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not set. Cannot extract entities.")
        return []

    prompt = PROMPT_TEMPLATE.format(query=query)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"}
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=20)
        if resp.status_code != 200:
            logger.error(f"API Error {resp.status_code}: {resp.text}")
            return []
            
        data = resp.json()
        raw_text = data['candidates'][0]['content']['parts'][0]['text']
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:-3]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:-3]
            
        return json.loads(raw_text.strip())
    except Exception as e:
        logger.error(f"Error extracting entities from query: {e}")
        return []

def resolve_query(query: str, aliases_cache_path: str = "output/extractions/entity_aliases.json") -> Tuple[List[str], List[str]]:
    """
    Ekstrak entitas dari query dan cocokkan dengan node di graph melalui kamus kanonikal.
    
    Args:
        query: Pertanyaan natural language dari user.
        aliases_cache_path: Path ke file entity_aliases.json yang dihasilkan tahap deduplikasi.
        
    Returns:
        Tuple(matched_node_ids, unmapped_entities)
    """
    extracted_entities = extract_entities_from_query(query)
    if not extracted_entities:
        return [], []
        
    alias_dict = {}
    if os.path.exists(aliases_cache_path):
        try:
            with open(aliases_cache_path, "r", encoding="utf-8") as f:
                alias_dict = json.load(f)
        except Exception as e:
            logger.error(f"Gagal memuat alias dict dari {aliases_cache_path}: {e}")
            
    matched_nodes = []
    not_found = []
    
    for query_ent in extracted_entities:
        # 1. Exact match (case insensitive) ke keys di alias dict
        exact_match = None
        for alias, canonical in alias_dict.items():
            if alias.lower() == query_ent.lower():
                exact_match = canonical
                break
                
        if exact_match:
            matched_nodes.append(exact_match)
            continue
            
        # 2. Fuzzy match fallback
        best_match = None
        best_score = 0
        for alias, canonical in alias_dict.items():
            score = SequenceMatcher(None, alias.lower(), query_ent.lower()).ratio()
            if score > best_score:
                best_score = score
                best_match = canonical
                
        if best_score > 0.70:
            matched_nodes.append(best_match)
        else:
            not_found.append(query_ent)
            
    # Hapus duplikat dari matched_nodes
    matched_nodes = list(set(matched_nodes))
    
    return matched_nodes, not_found
