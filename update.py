"""
update_graph.py

Skrip jalan pintas (shortcut) untuk me-rebuild graf dan memperbarui HTML 
langsung dari file JSON ekstraksi yang ada, tanpa melakukan proses ekstraksi PDF.
Sangat berguna jika Anda memodifikasi file JSON secara manual dan ingin
langsung melihat perubahannya di browser.
"""

import glob
import os
import webbrowser

from app.graph_builder import build_graph, load_extraction
from app.visualizer import visualize
from app.config import EXTRACTIONS_DIR, GRAPH_HTML_PATH

def main():
    print(f"Membaca file JSON dari: {EXTRACTIONS_DIR}")
    json_files = glob.glob(os.path.join(EXTRACTIONS_DIR, '*.json'))
    
    if not json_files:
        print(f"[WARN] Tidak ditemukan file JSON berakhiran .json di {EXTRACTIONS_DIR}")
        return
        
    print(f"Ditemukan {len(json_files)} file ekstraksi. Sedang membangun graf...")
    
    # Load semua JSON
    extractions = []
    for jf in json_files:
        ext = load_extraction(jf)
        if ext:
            extractions.append(ext)
            
    # Proses deduplikasi dan pembuatan node/edge
    print("-" * 50)
    graph = build_graph(extractions)
    print("-" * 50)
    
    # Perbarui HTML
    print("Memperbarui antarmuka visualisasi...")
    visualize(graph, GRAPH_HTML_PATH)
    
    abs_path = os.path.abspath(GRAPH_HTML_PATH)
    print(f"\n[OK] Visualisasi berhasil diperbarui!")
    print(f"     Disimpan di: {abs_path}")
    


if __name__ == "__main__":
    main()
