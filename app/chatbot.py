import os
import json
import logging
import requests
import networkx as nx
from typing import List, Dict, Any, Tuple

from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.query_resolver import resolve_query
from app.graph_traversal import get_1hop_neighbors, serialize_traversal_results

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """\
Anda adalah asisten akademik yang bertugas menjawab pertanyaan berdasarkan graf pengetahuan ilmiah (GraphRAG).
Gunakan HANYA informasi yang disediakan dalam blok "KONTEKS GRAPH" di bawah ini.
Jika informasi yang ditanyakan TIDAK ADA di dalam konteks, jawab dengan jujur "Saya tidak tahu berdasarkan dokumen yang ada" atau "Informasi tidak tersedia di dalam konteks".
JANGAN mengarang jawaban (no hallucination).
Jawablah dalam bahasa Indonesia dengan jelas dan profesional.

PERTANYAAN USER:
{query}

KONTEKS GRAPH:
{context}
"""

def answer_question(query: str, graph: nx.Graph, aliases_cache_path: str = "output/extractions/entity_aliases.json") -> str:
    """
    End-to-end pipeline untuk menjawab pertanyaan menggunakan GraphRAG.
    """
    # 1. Resolve entity dari pertanyaan
    matched_nodes, unmapped = resolve_query(query, aliases_cache_path, graph=graph)
    
    if not matched_nodes:
        return "Maaf, saya tidak menemukan entitas yang relevan dengan pertanyaan Anda di dalam graf dokumen ini."
        
    # 2 & 3. Traversal dan Serialize (Handling Multi-Entity: Gabungkan konteksnya)
    # PENDEKATAN MULTI-ENTITY: Jika ada >1 entry point, kita lakukan traversal untuk masing-masing
    # entry point, serialisasi, lalu gabungkan string teksnya. LLM akan menerima konteks gabungan.
    all_contexts = []
    for ep in matched_nodes:
        traversal_data = get_1hop_neighbors(graph, ep)
        text_context = serialize_traversal_results(traversal_data)
        all_contexts.append(text_context)
        
    combined_context = "\n\n".join(all_contexts)
    
    # 4. Kirim ke LLM
    if not GEMINI_API_KEY:
        return "Error: GEMINI_API_KEY tidak dikonfigurasi."
        
    prompt = PROMPT_TEMPLATE.format(
        query=query,
        context=combined_context
    )
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0} # Temperature 0 untuk meminimalisir halusinasi
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"Error API LLM ({resp.status_code}): {resp.text}"
    except Exception as e:
        return f"Gagal menghubungi LLM: {e}"
