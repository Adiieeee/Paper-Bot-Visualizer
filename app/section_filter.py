"""
section_filter.py — Tahap 2: Filter bagian paper yang tidak relevan.

Menghapus References, Appendix, Acknowledgments, dll. menggunakan
regex yang lebih robust daripada plain keyword matching.
"""

import re
import logging
from typing import Dict

from app.config import SECTION_SKIP_PATTERNS

logger = logging.getLogger(__name__)

# Kompilasi semua pattern sekali saat modul di-load
_COMPILED_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in SECTION_SKIP_PATTERNS
]


def filter_sections(text_by_page: Dict[int, str], total_pages: int) -> str:
    """
    Filter teks paper, hentikan saat menemukan section yang harus di-skip.

    Args:
        text_by_page: dict {page_num: page_text} dari pdf_parser.
        total_pages:  total jumlah halaman.

    Returns:
        Teks bersih sebagai satu string, siap untuk di-chunk.
    """
    kept_pages: list[str] = []
    short_pages_skipped = 0
    stop_page: Optional[int] = None

    for page_num in sorted(text_by_page.keys()):
        page_text = text_by_page[page_num]

        # Skip halaman yang terlalu pendek (cover image, halaman nomor, dll.)
        if len(page_text.strip()) < 100:
            short_pages_skipped += 1
            continue

        # Cek apakah halaman ini membuka section yang harus di-skip
        if _page_starts_skip_section(page_text):
            stop_page = page_num
            logger.info(f"Section filter: berhenti di halaman {page_num + 1}")
            break

        # Cek apakah ada batas section DI TENGAH halaman
        filtered_text, found_boundary = _cut_at_boundary(page_text)
        kept_pages.append(filtered_text)

        if found_boundary:
            stop_page = page_num
            logger.info(
                f"Section filter: batas section ditemukan di tengah halaman {page_num + 1}"
            )
            break

    result = "\n\n".join(kept_pages)

    logger.info(
        f"Section filter selesai: {len(kept_pages)} halaman dipertahankan, "
        f"{short_pages_skipped} halaman pendek di-skip, "
        f"berhenti di halaman {(stop_page + 1) if stop_page is not None else total_pages}."
    )

    return result


# ─── Private helpers ──────────────────────────────────────────

def _page_starts_skip_section(page_text: str) -> bool:
    """
    Periksa 5 baris pertama halaman untuk mendeteksi section header.
    """
    lines = page_text.strip().split("\n")
    for line in lines[:5]:
        if _matches_skip(line.strip()):
            return True
    return False


def _cut_at_boundary(page_text: str) -> tuple[str, bool]:
    """
    Scan setiap baris dalam halaman.
    Jika ditemukan boundary, kembalikan teks sebelumnya dan flag True.

    Returns:
        (text_before_boundary, found_boundary)
    """
    lines = page_text.split("\n")
    kept: list[str] = []

    for line in lines:
        if _matches_skip(line.strip()):
            return "\n".join(kept), True
        kept.append(line)

    return "\n".join(kept), False


def _matches_skip(line: str) -> bool:
    """Return True jika baris cocok dengan salah satu pola skip."""
    if not line:
        return False
    for pattern in _COMPILED_PATTERNS:
        if pattern.match(line):
            return True
    return False


# Type hint helper
from typing import Optional
