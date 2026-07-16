#!/usr/bin/env python3
"""
chat.py — Interaktif RAG Chatbot untuk Paper Visualizer.

Cara pakai:
    python chat.py
"""

import os
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.graph_builder import build_graph, load_extraction
from app.config import EXTRACTIONS_DIR
from app.chatbot import answer_question
import logging

# Matikan log yang berisik agar layar chat tetap bersih
logging.getLogger("app.graph_builder").setLevel(logging.CRITICAL)
logging.getLogger("app.entity_resolver").setLevel(logging.CRITICAL)
logging.getLogger("app.query_resolver").setLevel(logging.CRITICAL)

def main():
    print("="*60)
    print("  GraphRAG Academic Chatbot")
    print("="*60)
    
    # 1. Load data
    print("[1/2] Memuat cache ekstraksi paper...")
    json_files = glob.glob(os.path.join(EXTRACTIONS_DIR, '*.json'))
    json_files = [f for f in json_files if not f.endswith("entity_aliases.json")]
    extractions = [e for jf in json_files if (e := load_extraction(jf))]
    
    if not extractions:
        print("ERROR: Tidak ada data paper yang ditemukan. Silakan jalankan 'python main.py' terlebih dahulu.")
        sys.exit(1)
        
    print(f"      {len(extractions)} paper dimuat.")
    
    # 2. Build graph (Sangat cepat karena deduplikasi sudah di-cache)
    print("[2/2] Membangun graf pengetahuan...")
    graph = build_graph(extractions)
    print(f"      Graf siap ({graph.number_of_nodes()} node, {graph.number_of_edges()} edge).\n")
    
    print("Chatbot siap! Ketik 'exit' atau 'quit' untuk keluar.\n")
    
    # 3. Interactive Loop
    while True:
        try:
            query = input("User> ")
            if not query.strip():
                continue
                
            if query.strip().lower() in ['exit', 'quit']:
                print("Selamat tinggal!")
                break
                
            print("GraphRAG> ... (mencari relasi graf & berpikir) ...")
            answer = answer_question(query, graph)
            print(f"\nGraphRAG> {answer}\n")
            print("-" * 60)
            
        except KeyboardInterrupt:
            print("\nSelamat tinggal!")
            break
        except Exception as e:
            print(f"\n[Error]: {e}\n")

if __name__ == "__main__":
    main()
