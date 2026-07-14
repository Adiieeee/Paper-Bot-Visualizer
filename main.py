#!/usr/bin/env python3
"""
main.py — Entry point Graph RAG Academic Paper Explorer.

Cara pakai:
    python main.py                  # proses semua PDF di folder papers/
    python main.py --force          # paksa ekstraksi ulang semua paper
    python main.py --no-open        # jangan buka browser otomatis
    python main.py --papers-dir /path/ke/folder  # custom folder PDF
"""

import argparse
import json
import logging
import os
import sys
import webbrowser
from datetime import datetime

from app.config import (
    EXTRACTIONS_DIR,
    GEMINI_API_KEY,
    GRAPH_GRAPHML_PATH,
    GRAPH_HTML_PATH,
    LOG_FILE_PATH,
    OUTPUT_DIR,
    PAPERS_DIR,
)
from app.extractor import extract_from_paper
from app.graph_builder import build_graph, load_extraction, save_graph
from app.visualizer import visualize


# ─── Setup logging ────────────────────────────────────────────
os.makedirs(OUTPUT_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        # Log ke file (detail lengkap)
        logging.FileHandler(LOG_FILE_PATH, encoding="utf-8"),
        # Tidak log ke console — kita print manual supaya output lebih bersih
    ],
)
logger = logging.getLogger(__name__)


# ─── Main ─────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()

    _print_header()

    # Validasi API key
    if not GEMINI_API_KEY:
        print("[ERROR] GEMINI_API_KEY tidak ditemukan.")
        print("    Buat file .env di root project dengan isi:")
        print("    GEMINI_API_KEY=api_key_kamu_di_sini")
        print("    Dapatkan API key gratis di: https://aistudio.google.com/apikey")
        sys.exit(1)

    papers_dir = args.papers_dir

    # Validasi dan siapkan folder papers
    if not os.path.exists(papers_dir):
        os.makedirs(papers_dir, exist_ok=True)
        print(f"[INFO] Folder '{papers_dir}' dibuat.")
        print(f"    Masukkan file PDF ke folder tersebut, lalu jalankan lagi.")
        sys.exit(0)

    # Cari semua PDF
    pdf_files = sorted(
        os.path.join(papers_dir, f)
        for f in os.listdir(papers_dir)
        if f.lower().endswith(".pdf")
    )

    if not pdf_files:
        print(f"[INFO] Tidak ada file PDF di '{papers_dir}'.")
        print(f"    Masukkan PDF paper akademik ke folder tersebut dan jalankan lagi.")
        sys.exit(0)

    print(f"[INFO] Ditemukan {len(pdf_files)} file PDF\n")
    os.makedirs(EXTRACTIONS_DIR, exist_ok=True)

    # --- Proses setiap paper ----------------------------------
    all_extractions: list[dict] = []

    for pdf_path in pdf_files:
        pdf_name  = os.path.basename(pdf_path)
        json_name = os.path.splitext(pdf_name)[0] + ".json"
        json_path = os.path.join(EXTRACTIONS_DIR, json_name)

        print(f">> {pdf_name}")

        # Incremental processing: skip jika sudah ada cache
        if not args.force and os.path.exists(json_path):
            print(f"    [CACHE] Already extracted - loading from JSON...")
            extraction = load_extraction(json_path)
            if extraction:
                n_ent = len(extraction.get("entities", []))
                n_rel = len(extraction.get("relationships", []))
                print(f"    {n_ent} entities, {n_rel} relations loaded\n")
                all_extractions.append(extraction)
                continue
            else:
                print(f"    [WARN] Cache broken - re-extracting...\n")

        # Jalankan pipeline ekstraksi
        extraction = extract_from_paper(pdf_path)

        if extraction:
            # Simpan JSON cache
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(extraction, f, indent=2, ensure_ascii=False)

            n_ent = len(extraction.get("entities", []))
            n_rel = len(extraction.get("relationships", []))
            failed = extraction.get("failed_chunks", 0)

            status = "[OK]" if failed == 0 else "[WARN]"
            print(f"    {status} Done: {n_ent} entities, {n_rel} relations", end="")
            if failed > 0:
                print(f" ({failed} chunks failed)", end="")
            print("\n")

            all_extractions.append(extraction)
        else:
            print(f"    [ERROR] Total failure - paper skipped\n")
            logger.error(f"Extraction failed for: {pdf_path}")

    if not all_extractions:
        print("[ERROR] Tidak ada ekstraksi yang berhasil.")
        print(f"    Lihat detail error di: {LOG_FILE_PATH}")
        sys.exit(1)

    # -- Build graph
    print("-" * 50)
    graph = build_graph(all_extractions)

    # Simpan graph dan JSON mentah
    save_graph(graph, all_extractions, OUTPUT_DIR)
    print(f"[OK] Graph disimpan ke {GRAPH_GRAPHML_PATH}")

    # -- Visualisasi
    print(f"Generating visualization...", end=" ", flush=True)
    visualize(graph, GRAPH_HTML_PATH)
    print(f"done")
    print(f"    Saved to: {os.path.abspath(GRAPH_HTML_PATH)}")

    # -- Summary
    _print_summary(graph, all_extractions)

    # -- Buka di browser
    abs_path = os.path.abspath(GRAPH_HTML_PATH)
    if not args.no_open:
        print(f"Opening graph in browser...")
        webbrowser.open(f"file:///{abs_path.replace(os.sep, '/')}")
    else:
        print(f"\nOpen this file in your browser:")
        print(f"    {abs_path}")


# --- Helpers --------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Graph RAG Academic Paper Explorer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Paksa ekstraksi ulang semua paper (abaikan cache JSON)",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Jangan buka graph.html di browser secara otomatis",
    )
    parser.add_argument(
        "--papers-dir",
        default=PAPERS_DIR,
        metavar="DIR",
        help=f"Folder berisi file PDF (default: {PAPERS_DIR})",
    )
    return parser.parse_args()


def _print_header() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'=' * 54}")
    print(f"  Graph RAG Academic Paper Explorer")
    print(f"  {now}")
    print(f"{'=' * 54}\n")


def _print_summary(graph, all_extractions: list[dict]) -> None:
    type_counts: dict[str, int] = {}
    for _, attrs in graph.nodes(data=True):
        t = attrs.get("type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    edge_type_counts: dict[str, int] = {}
    for _, _, attrs in graph.edges(data=True):
        t = attrs.get("type", "unknown")
        edge_type_counts[t] = edge_type_counts.get(t, 0) + 1

    print(f"\n{'=' * 54}")
    print(f"  Ringkasan")
    print(f"{'-' * 54}")
    print(f"  Paper diproses : {len(all_extractions)}")
    print(f"  Total node     : {graph.number_of_nodes()}")
    print(f"  Total edge     : {graph.number_of_edges()}")

    print(f"\n  Tipe node:")
    for ntype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {ntype:<15} {count}")

    print(f"\n  Tipe edge:")
    for etype, count in sorted(edge_type_counts.items(), key=lambda x: -x[1]):
        print(f"    {etype:<20} {count}")

    print(f"\n  Log detail : {LOG_FILE_PATH}")
    print(f"{'=' * 54}\n")


if __name__ == "__main__":
    main()
