"""
chunker.py — Tahap 3: Pecah teks menjadi chunk untuk LLM.

Menggunakan RecursiveCharacterTextSplitter dari LangChain.
"""

import logging
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import CHUNK_SIZE, CHUNK_OVERLAP

logger = logging.getLogger(__name__)

# Minimum chunk length — chunk yang terlalu pendek biasanya noise
MIN_CHUNK_LENGTH = 200


def chunk_text(text: str) -> List[str]:
    """
    Pecah teks bersih menjadi list chunk untuk dikirim ke LLM.

    Args:
        text: Teks bersih dari section_filter.

    Returns:
        List of string chunks.
    """
    if not text or not text.strip():
        logger.warning("chunk_text: teks kosong diterima, tidak ada chunk yang dibuat.")
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    raw_chunks = splitter.split_text(text)

    # Filter chunk yang terlalu pendek
    chunks = [c for c in raw_chunks if len(c.strip()) >= MIN_CHUNK_LENGTH]

    logger.info(
        f"Chunking: {len(text)} karakter → {len(chunks)} chunk "
        f"(dari {len(raw_chunks)} raw, {len(raw_chunks) - len(chunks)} terlalu pendek di-drop)"
    )

    return chunks
