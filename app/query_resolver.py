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
    checked_entities = []
    if os.path.exists(aliases_cache_path):
        try:
            with open(aliases_cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "aliases" in data and "checked_entities" in data:
                    alias_dict = data["aliases"]
                    checked_entities = data["checked_entities"]
                elif isinstance(data, dict):
                    alias_dict = data
                    checked_entities = list(set(alias_dict.keys()) | set(alias_dict.values()))
        except Exception as e:
            logger.error(f"Gagal memuat alias dict dari {aliases_cache_path}: {e}")
            
    matched_nodes = []
    not_found = []
    
    # Kumpulkan semua valid node IDs (canonical names yang ada di checked_entities + values dari alias)
    # Gunakan lowercase map agar pencarian cepat
    valid_canonicals_lower = {c.lower(): c for c in checked_entities}
    for v in alias_dict.values():
        valid_canonicals_lower[v.lower()] = v
        
    for query_ent in extracted_entities:
        q_lower = query_ent.lower()
        
        # 1. Exact match ke keys di alias dict (Prioritas Utama)
        exact_match = None
        for alias, canonical in alias_dict.items():
            if alias.lower() == q_lower:
                exact_match = canonical
                break
                
        if exact_match:
            matched_nodes.append(exact_match)
            continue
            
        # 2. Exact match ke Canonical Nodes langsung
        if q_lower in valid_canonicals_lower:
            matched_nodes.append(valid_canonicals_lower[q_lower])
            continue
            
        # 3. Fuzzy match fallback
        best_match = None
        best_score = 0
        
        # Cek fuzzy terhadap aliases
        for alias, canonical in alias_dict.items():
            score = SequenceMatcher(None, alias.lower(), q_lower).ratio()
            if score > best_score:
                best_score = score
                best_match = canonical
                
        # Cek fuzzy terhadap canonicals
        for c_lower, canonical in valid_canonicals_lower.items():
            score = SequenceMatcher(None, c_lower, q_lower).ratio()
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
