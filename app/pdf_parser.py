"""
pdf_parser.py — Tahap 1: Parse PDF paper menggunakan PyMuPDF.

Output: dict berisi teks per halaman, judul, dan metadata dasar.
"""

import os
import re
import logging
from typing import Optional

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def parse_pdf(file_path: str) -> Optional[dict]:
    """
    Parse sebuah file PDF dan ekstrak teksnya per halaman.

    Args:
        file_path: Path ke file PDF.

    Returns:
        Dict dengan keys: title, text_by_page, full_text, total_pages, file_path, file_name.
        None jika parsing gagal.
    """
    if not os.path.exists(file_path):
        logger.error(f"File tidak ditemukan: {file_path}")
        return None

    if not file_path.lower().endswith(".pdf"):
        logger.error(f"Bukan file PDF: {file_path}")
        return None

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        logger.error(f"Gagal membuka PDF '{file_path}': {e}")
        return None

    if doc.is_encrypted:
        logger.error(f"PDF terproteksi password: {file_path}")
        doc.close()
        return None

    total_pages = len(doc)

    if total_pages == 0:
        logger.warning(f"PDF tidak memiliki halaman: {file_path}")
        doc.close()
        return None

    # Ekstrak teks per halaman
    text_by_page: dict[int, str] = {}
    for page_num in range(total_pages):
        page = doc[page_num]
        text = page.get_text()
        text_by_page[page_num] = text

    # Ekstrak judul dari halaman pertama
    title = _extract_title(doc[0], file_path)

    # Coba ekstrak tahun publikasi dari teks awal
    year = _extract_year(text_by_page.get(0, "") + text_by_page.get(1, ""))

    doc.close()

    full_text = "\n\n".join(text_by_page.values())

    return {
        "title":        title,
        "year":         year,
        "text_by_page": text_by_page,
        "full_text":    full_text,
        "total_pages":  total_pages,
        "file_path":    file_path,
        "file_name":    os.path.basename(file_path),
    }


# ─── Private helpers ──────────────────────────────────────────

def _extract_title(first_page, file_path: str) -> str:
    """
    Ekstrak judul paper dari halaman pertama.
    Heuristik: kumpulkan span teks dengan font size terbesar.
    Fallback: nama file.
    """
    try:
        blocks = first_page.get_text("dict")["blocks"]

        # Kumpulkan (font_size, text) dari semua span
        spans: list[tuple[float, str]] = []
        for block in blocks:
            if block.get("type") != 0:  # hanya teks
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    size = span.get("size", 0.0)
                    # Filter: minimal 5 karakter, bukan angka saja, ukuran wajar
                    if text and len(text) >= 5 and size > 8 and not text.isdigit():
                        spans.append((size, text))

        if not spans:
            return _filename_to_title(file_path)

        # Ambil font size maksimal, lalu kumpulkan semua span ≥ 90% ukuran itu
        max_size = max(s[0] for s in spans)
        title_parts = [
            text for size, text in spans
            if size >= max_size * 0.90 and len(text) > 3
        ]

        # Ambil maksimal 8 bagian pertama (hindari judul terlalu panjang)
        title = " ".join(title_parts[:8])
        title = " ".join(title.split())  # normalisasi whitespace

        if len(title) > 250:
            title = title[:250]

        return title if title else _filename_to_title(file_path)

    except Exception as e:
        logger.warning(f"Gagal ekstrak judul dari halaman 1: {e}")
        return _filename_to_title(file_path)


def _extract_year(text: str) -> str:
    """
    Coba ekstrak tahun publikasi dari teks awal paper.
    Cari pola seperti '(2024)', '2024', 'arXiv:2401.xxxxx', dll.
    """
    # Pola paling umum di paper akademik
    patterns = [
        r"\(20[1-2]\d\)",       # (2024)
        r"\b20[1-2]\d\b",       # 2024 standalone
        r"arXiv:(\d{4})\.",     # arXiv ID prefix = year
    ]

    for pattern in patterns:
        match = re.search(pattern, text[:3000])
        if match:
            year_str = match.group()
            # Ekstrak hanya angkanya
            year_only = re.search(r"20[1-2]\d", year_str)
            if year_only:
                return year_only.group()

    return "Unknown"


def _filename_to_title(file_path: str) -> str:
    """Konversi nama file ke judul yang bisa dibaca sebagai fallback."""
    basename = os.path.basename(file_path)
    name = os.path.splitext(basename)[0]
    return name.replace("_", " ").replace("-", " ").title()
