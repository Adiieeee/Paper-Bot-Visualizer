"""
extractor.py — Tahap 4: Ekstraksi entitas dan relasi via Gemini Flash.

Perbaikan dari spesifikasi:
- Prompt memerintahkan LLM untuk SELALU pakai nama lengkap (bukan akronim)
- Rate limiting lebih konservatif: 3 detik antar panggilan
- Retry dengan exponential backoff saat rate limit
- Robust JSON parsing (handle markdown code block)
- Validasi output terhadap schema
"""

import json
import re
import time
import logging
from typing import Optional

from google import genai
from google.genai import types as genai_types

from app.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    API_DELAY_SECONDS,
    API_MAX_RETRIES,
    API_RETRY_DELAY_SECONDS,
    VALID_ENTITY_TYPES,
    VALID_RELATIONSHIP_TYPES,
    GENERIC_ENTITY_BLOCKLIST,
)
from app.pdf_parser import parse_pdf
from app.section_filter import filter_sections
from app.chunker import chunk_text

logger = logging.getLogger(__name__)

# ─── Inisialisasi Gemini ──────────────────────────────────────
if GEMINI_API_KEY:
    _client = genai.Client(api_key=GEMINI_API_KEY)
else:
    _client = None
    logger.error("GEMINI_API_KEY tidak ditemukan di environment variables!")

# Flag global: jika True, semua panggilan API berikutnya langsung di-skip
_fatal_error = False

# Keyword yang menandakan error fatal (tidak perlu retry)
_FATAL_ERROR_KEYWORDS = (
    "API key not valid",
    "API_KEY_INVALID",
    "invalid api key",
    "permission denied",
    "PERMISSION_DENIED",
    "invalid authentication",
    "401",
)

# ─── Prompt Template ─────────────────────────────────────────
_EXTRACTION_PROMPT = """\
You are an academic paper analyzer. Extract entities and relationships from the text below.

PAPER METADATA:
Title: {paper_title}
Year: {paper_year}
Venue: {paper_venue}

TEXT CHUNK:
{text_chunk}

STRICT RULES:
1. Only extract entities EXPLICITLY mentioned in this text. Do NOT infer.
2. Always use the FULL NAME, never acronyms. Write "Retrieval-Augmented Generation" not "RAG", "Large Language Model" not "LLM", "Bidirectional Encoder Representations from Transformers" not "BERT", etc. If the text only uses an acronym without defining it, skip that entity.
3. Do NOT extract generic terms: "the model", "our approach", "the method", "the system", "the framework", "the algorithm", "this paper", "the proposed method".
4. For Finding: extract only MAJOR findings as concise statements (max 15 words). Skip minor observations.
5. For Limitation: only extract limitations EXPLICITLY stated by the authors.
6. Do NOT extract anything from a references or bibliography section.
7. For Author: ONLY extract the actual authors of the current paper. Do NOT extract authors from in-text citations (e.g., skip "Smith et al. (2020)").
8. Output MUST be valid JSON only. No markdown, no explanation, no code blocks.

ENTITY TYPES (use exactly): Paper | Author | Institution | Method | Dataset | Metric | Finding | Limitation

RELATIONSHIP TYPES (use exactly): written_by | affiliated_with | uses_method | proposes_method | uses_dataset | uses_metric | finds | has_limitation | criticizes | builds_on | compares

OUTPUT FORMAT (JSON only):
{{
  "entities": [
    {{"name": "full name here", "type": "EntityType"}}
  ],
  "relationships": [
    {{"source": "entity name", "target": "entity name", "type": "relationship_type", "description": "brief description"}}
  ]
}}"""


# ─── Public API ───────────────────────────────────────────────

def extract_from_chunk(
    chunk: str,
    paper_title: str,
    paper_year: str = "Unknown",
    paper_venue: str = "Unknown",
) -> Optional[dict]:
    """
    Kirim satu chunk ke Gemini dan kembalikan entitas + relasi.

    Args:
        chunk:       Teks chunk untuk diekstrak.
        paper_title: Judul paper (untuk konteks prompt).
        paper_year:  Tahun publikasi.
        paper_venue: Nama venue/konferensi.

    Returns:
        Dict {"entities": [...], "relationships": [...]} atau None jika gagal.
    """
    global _fatal_error

    if _fatal_error:
        return None

    if not _client:
        logger.error("Gemini client tidak terinisialisasi. Cek GEMINI_API_KEY.")
        return None

    prompt = _EXTRACTION_PROMPT.format(
        paper_title=paper_title,
        paper_year=paper_year,
        paper_venue=paper_venue,
        text_chunk=chunk,
    )

    for attempt in range(1, API_MAX_RETRIES + 1):
        try:
            response = _client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
            raw_text = response.text

            parsed = _parse_json(raw_text)
            if parsed is None:
                logger.warning(
                    f"Attempt {attempt}: JSON parse gagal. "
                    f"Snippet: {raw_text[:200]!r}"
                )
                if attempt < API_MAX_RETRIES:
                    time.sleep(API_RETRY_DELAY_SECONDS)
                continue

            cleaned = _validate_and_clean(parsed)

            # Rate limiting — tunggu sebelum panggilan berikutnya
            time.sleep(API_DELAY_SECONDS)

            return cleaned

        except Exception as e:
            err_str = str(e)

            # Deteksi error fatal: API key salah, akses ditolak, dll.
            if any(kw.lower() in err_str.lower() for kw in _FATAL_ERROR_KEYWORDS):
                _fatal_error = True
                print("\n")
                print("❌  FATAL ERROR: API key tidak valid atau akses ditolak.")
                print("    Pastikan GEMINI_API_KEY di file .env sudah benar.")
                print("    API key Gemini diawali dengan 'AIza...'")
                print(f"    Detail: {err_str[:300]}")
                print("    Dapatkan API key di: https://aistudio.google.com/apikey")
                raise SystemExit(1)

            # Rate limit / quota habis — retry dengan backoff
            elif any(kw in err_str for kw in ("429", "quota", "rate", "RESOURCE_EXHAUSTED")):
                wait = API_RETRY_DELAY_SECONDS * attempt
                logger.warning(f"Rate limit hit (attempt {attempt}). Tunggu {wait}s...")
                time.sleep(wait)

            # Error lain — retry biasa
            else:
                logger.error(f"API error (attempt {attempt}): {e}")
                if attempt < API_MAX_RETRIES:
                    time.sleep(API_RETRY_DELAY_SECONDS)

    logger.error(f"Ekstraksi gagal setelah {API_MAX_RETRIES} percobaan.")
    return None


def extract_from_paper(file_path: str) -> Optional[dict]:
    """
    Jalankan pipeline ekstraksi lengkap untuk satu paper PDF.

    Pipeline: parse → filter → chunk → extract per chunk → gabungkan.

    Args:
        file_path: Path ke file PDF.

    Returns:
        Dict berisi metadata paper dan semua entitas/relasi,
        atau None jika pipeline gagal total.
    """
    # Tahap 1: Parse PDF
    print(f"  Parsing PDF...", end=" ", flush=True)
    paper_data = parse_pdf(file_path)
    if not paper_data:
        print("GAGAL")
        logger.error(f"Gagal parse PDF: {file_path}")
        return None
    print(f"{paper_data['total_pages']} halaman")

    # Tahap 2: Filter sections
    filtered_text = filter_sections(paper_data["text_by_page"], paper_data["total_pages"])
    if not filtered_text.strip():
        logger.error(f"Tidak ada teks setelah section filter: {file_path}")
        return None
    print(f"  Section filter: ~{len(filtered_text) // 5} kata dipertahankan")

    # Tahap 3: Chunking
    chunks = chunk_text(filtered_text)
    if not chunks:
        logger.error(f"Chunking menghasilkan 0 chunk: {file_path}")
        return None
    print(f"  {len(chunks)} chunk dibuat")

    # Tahap 4: Ekstraksi per chunk
    all_entities: list[dict] = []
    all_relationships: list[dict] = []
    failed_chunks = 0

    for i, chunk in enumerate(chunks, 1):
        print(f"  Chunk {i}/{len(chunks)}...", end=" ", flush=True)

        result = extract_from_chunk(
            chunk=chunk,
            paper_title=paper_data["title"],
            paper_year=paper_data.get("year", "Unknown"),
            paper_venue="Unknown",  # tidak di-parse otomatis, lihat analisis
        )

        if result:
            n_ent = len(result["entities"])
            n_rel = len(result["relationships"])
            print(f"✓ ({n_ent} entitas, {n_rel} relasi)")
            all_entities.extend(result["entities"])
            all_relationships.extend(result["relationships"])
        else:
            print("✗ GAGAL (chunk di-skip)")
            failed_chunks += 1

    if failed_chunks == len(chunks):
        logger.error(f"Semua chunk gagal untuk: {file_path}")
        return None

    return {
        "file_path":     file_path,
        "file_name":     paper_data["file_name"],
        "title":         paper_data["title"],
        "year":          paper_data.get("year", "Unknown"),
        "total_pages":   paper_data["total_pages"],
        "total_chunks":  len(chunks),
        "failed_chunks": failed_chunks,
        "entities":      all_entities,
        "relationships": all_relationships,
    }


# ─── Private helpers ──────────────────────────────────────────

def _parse_json(raw: str) -> Optional[dict]:
    """
    Parse JSON dari respons LLM.
    Handle: JSON langsung, markdown code block, JSON tertanam dalam teks.
    """
    # 1. Parse langsung
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown code block (```json ... ``` atau ``` ... ```)
    stripped = re.sub(r"```(?:json)?\s*", "", raw)
    stripped = re.sub(r"```\s*$", "", stripped, flags=re.MULTILINE).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # 3. Cari objek JSON pertama dalam teks
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def _validate_and_clean(data: dict) -> dict:
    """
    Validasi entity types dan relationship types terhadap schema,
    dan filter entitas generik yang tidak boleh menjadi node.
    """
    raw_entities = data.get("entities", [])
    raw_relationships = data.get("relationships", [])

    # ── Validasi entitas ──────────────────────────────
    valid_entities: list[dict] = []
    for ent in raw_entities:
        if not isinstance(ent, dict):
            continue

        name = (ent.get("name") or "").strip()
        etype = (ent.get("type") or "").strip()

        # Minimal 2 karakter
        if len(name) < 2:
            continue

        # Tipe harus valid
        if etype not in VALID_ENTITY_TYPES:
            logger.debug(f"Tipe tidak valid di-skip: {etype!r} untuk '{name}'")
            continue

        # Blokir entitas generik
        if name.lower() in GENERIC_ENTITY_BLOCKLIST:
            logger.debug(f"Entitas generik di-skip: '{name}'")
            continue

        valid_entities.append({"name": name, "type": etype})

    # ── Validasi relasi ───────────────────────────────
    entity_names = {e["name"] for e in valid_entities}
    valid_relationships: list[dict] = []

    for rel in raw_relationships:
        if not isinstance(rel, dict):
            continue

        source = (rel.get("source") or "").strip()
        target = (rel.get("target") or "").strip()
        rtype = (rel.get("type") or "").strip()
        description = (rel.get("description") or "").strip()

        if not source or not target or not rtype:
            continue

        if rtype not in VALID_RELATIONSHIP_TYPES:
            logger.debug(f"Tipe relasi tidak valid di-skip: {rtype!r}")
            continue

        # Self-loop
        if source == target:
            continue

        valid_relationships.append({
            "source":      source,
            "target":      target,
            "type":        rtype,
            "description": description,
        })

    return {"entities": valid_entities, "relationships": valid_relationships}
