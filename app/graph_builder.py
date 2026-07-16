"""
graph_builder.py — Tahap 5 & 6: Merge, deduplicate, dan build graph.

Perbaikan dari spesifikasi:
- Deduplikasi per-tipe entitas (tidak merge Method dengan Author)
- Ekspansi akronim dari COMMON_ACRONYMS sebelum dedup string similarity
- Threshold similarity 0.85 (lebih ketat dari spec's 0.8)
- Validasi: relasi ke entitas yang tidak ada di graph di-skip
- same_author edges ditambahkan otomatis antar paper yang berbagi penulis
"""

import json
import logging
import os
import re
from difflib import SequenceMatcher
from typing import Optional

import networkx as nx

from app.config import (
    COMMON_ACRONYMS,
    ENTITY_SIMILARITY_THRESHOLD,
    VALID_ENTITY_TYPES,
)

logger = logging.getLogger(__name__)


# ─── Public API ───────────────────────────────────────────────

def build_graph(all_extractions: list[dict]) -> nx.Graph:
    """
    Bangun NetworkX Graph dari semua hasil ekstraksi.

    Args:
        all_extractions: List dict hasil extract_from_paper() untuk setiap paper.

    Returns:
        NetworkX Graph object.
    """
    graph = nx.Graph()

    # Kumpulkan semua entitas dan relasi dari semua paper
    raw_entities: list[dict] = []
    raw_relationships: list[dict] = []

    for extraction in all_extractions:
        paper_title = extraction.get("title", "Unknown Paper")
        file_name = extraction.get("file_name", "unknown.pdf")

        # Cari judul asli paper dari LLM (biasanya bukan arXiv ID)
        best_title = paper_title
        for ent in extraction.get("entities", []):
            if ent.get("type") == "Paper":
                t = ent.get("name", "").strip()
                if t and "arxiv" not in t.lower() and len(t) > 10:
                    best_title = t
                    break

        # Node paper itu sendiri
        raw_entities.append({
            "name":         best_title,
            "type":         "Paper",
            "source_paper": best_title,
            "file_name":    file_name,
        })

        # Mapping untuk melacak perubahan nama split agar relasi bisa di-update
        split_author_map: dict[str, list[str]] = {}

        for ent in extraction.get("entities", []):
            name = ent.get("name", "").strip()
            ent_type = ent.get("type")

            if not name:
                continue

            if ent_type == "Paper":
                # Fix: Paksa semua entitas Paper menjadi best_title karena kita 
                # melarang ekstraksi paper lain dari kutipan.
                ent["name"] = best_title
                raw_entities.append({
                    **ent,
                    "source_paper": best_title,
                    "file_name":    file_name,
                })

            elif ent_type == "Author":
                # Fix: Hapus " et al." dan tahun kutipan seperti ", 2024"
                clean_name = re.sub(r'(?i)\s+et\s+al\.?', '', name)
                clean_name = re.sub(r',\s*\d{4}[a-z]?', '', clean_name).strip()
                
                # Fix: Split jika ada "&" atau "and"
                if " & " in clean_name or " and " in clean_name.lower():
                    parts = re.split(r'(?i)\s+&\s+|\s+and\s+', clean_name)
                    valid_parts = [p.strip() for p in parts if p.strip()]
                    
                    split_author_map[name] = valid_parts
                    
                    for part in valid_parts:
                        raw_entities.append({
                            **ent,
                            "name": part,
                            "source_paper": best_title,
                            "file_name":    file_name,
                        })
                else:
                    ent["name"] = clean_name
                    raw_entities.append({
                        **ent,
                        "source_paper": best_title,
                        "file_name":    file_name,
                    })
            else:
                raw_entities.append({
                    **ent,
                    "source_paper": best_title,
                    "file_name":    file_name,
                })

        for rel in extraction.get("relationships", []):
            source = rel.get("source", "")
            target = rel.get("target", "")
            
            # Jika source/target adalah author yang di-split, duplikasi relasinya
            sources = split_author_map.get(source, [source])
            targets = split_author_map.get(target, [target])
            
            for s in sources:
                for t in targets:
                    raw_relationships.append({
                        **rel,
                        "source": s,
                        "target": t,
                        "source_paper": best_title,
                    })

    print(f"  Total entitas mentah: {len(raw_entities)}")

    # Extract all raw names for LLM resolution (Method, Dataset, Metric)
    raw_names = []
    for ent in raw_entities:
        t = ent.get("type", "Unknown")
        name = ent.get("name", "").strip()
        if name and t in ["Method", "Dataset", "Metric"]:
            raw_names.append(name)
            
    # Resolve aliases with LLM Entity Linking
    from app.entity_resolver import build_entity_aliases
    cache_path = os.path.join(os.getcwd(), "output", "extractions", "entity_aliases.json")
    llm_aliases = build_entity_aliases(raw_names, cache_path=cache_path)

    # Deduplikasi entitas
    canonical_entities, entity_map = _deduplicate_entities(raw_entities, llm_aliases)
    print(f"  Setelah dedup: {len(canonical_entities)} entitas unik")

    # Tambahkan node ke graph
    for ent in canonical_entities:
        node_id = ent["name"]
        graph.add_node(
            node_id,
            type=ent.get("type", "Unknown"),
            label=node_id,
            source_paper=ent.get("source_paper", ""),
            file_name=ent.get("file_name", ""),
            title=node_id,  # Pyvis gunakan 'title' sebagai tooltip
        )

    # Tambahkan edge
    print(f"  Total relasi mentah: {len(raw_relationships)}")
    edge_set: set[tuple] = set()
    edges_added = 0
    edges_skipped = 0

    for rel in raw_relationships:
        source_raw = rel.get("source", "")
        target_raw = rel.get("target", "")
        rel_type   = rel.get("type", "")
        description = rel.get("description", "")
        source_paper = rel.get("source_paper", "")

        # Resolve ke nama canonical melalui entity_map
        source = _resolve(source_raw, entity_map)
        target = _resolve(target_raw, entity_map)

        # Skip jika node tidak ada di graph
        if source not in graph.nodes or target not in graph.nodes:
            edges_skipped += 1
            continue

        # Skip self-loop
        if source == target:
            edges_skipped += 1
            continue

        # Dedup edge: (a, b, type) tanpa arah
        edge_key = (_canonical_pair(source, target), rel_type)
        if edge_key in edge_set:
            continue

        edge_set.add(edge_key)
        graph.add_edge(
            source, target,
            type=rel_type,
            label=rel_type.replace("_", " "),
            title=f"{rel_type.replace('_', ' ').title()}\n{description}",
            description=description,
            source_paper=source_paper,
        )
        edges_added += 1

    print(f"  Edge ditambahkan: {edges_added} | di-skip: {edges_skipped}")

    # Tambahkan edge same_author antar paper
    _add_same_author_edges(graph, all_extractions, entity_map)

    # Hubungkan node yatim (isolate) ke paper sumbernya
    _connect_isolated_nodes(graph)

    print(
        f"  Graph final: {graph.number_of_nodes()} node, "
        f"{graph.number_of_edges()} edge"
    )

    return graph


def save_graph(
    graph: nx.Graph,
    extractions: list[dict],
    output_dir: str = "output",
) -> None:
    """
    Simpan graph ke GraphML dan setiap ekstraksi ke file JSON.

    Args:
        graph:       NetworkX Graph.
        extractions: List hasil ekstraksi mentah.
        output_dir:  Direktori output (default: 'output').
    """
    os.makedirs(output_dir, exist_ok=True)
    extractions_dir = os.path.join(output_dir, "extractions")
    os.makedirs(extractions_dir, exist_ok=True)

    # GraphML
    graphml_path = os.path.join(output_dir, "graph.graphml")
    nx.write_graphml(graph, graphml_path)
    logger.info(f"Graph disimpan ke {graphml_path}")

    # JSON per paper
    for extraction in extractions:
        file_name = extraction.get("file_name", "unknown.pdf")
        json_name = os.path.splitext(file_name)[0] + ".json"
        json_path = os.path.join(extractions_dir, json_name)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(extraction, f, indent=2, ensure_ascii=False)

    logger.info(f"Ekstraksi disimpan ke {extractions_dir}/")


def load_extraction(json_path: str) -> Optional[dict]:
    """Muat hasil ekstraksi dari file JSON cache."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Gagal load extraction dari {json_path}: {e}")
        return None


def load_graph(graphml_path: str) -> Optional[nx.Graph]:
    """Muat graph dari file GraphML."""
    try:
        graph = nx.read_graphml(graphml_path)
        logger.info(f"Graph dimuat dari {graphml_path}")
        return graph
    except Exception as e:
        logger.error(f"Gagal load graph dari {graphml_path}: {e}")
        return None



# ─── Private helpers ──────────────────────────────────────────

def _normalize(name: str) -> str:
    """Normalisasi nama entitas untuk perbandingan."""
    return name.lower().strip().strip(".,;:!?\"'()[]{}")


def _expand_acronym(name: str) -> str:
    """
    Coba ekspansi akronim menggunakan kamus COMMON_ACRONYMS.
    Hanya expand jika nama adalah akronim yang dikenal persis.
    """
    key = _normalize(name)
    return COMMON_ACRONYMS.get(key, name)


def _resolve(raw_name: str, entity_map: dict[str, str]) -> str:
    """
    Resolve nama entitas mentah ke nama canonical.
    Coba: exact → setelah expand akronim → fallback ke raw.
    """
    norm = _normalize(raw_name)
    if norm in entity_map:
        return entity_map[norm]

    expanded = _expand_acronym(raw_name)
    norm_exp = _normalize(expanded)
    if norm_exp in entity_map:
        return entity_map[norm_exp]

    return raw_name


def _canonical_pair(a: str, b: str) -> tuple[str, str]:
    """Buat pasangan (a, b) yang tidak berarah untuk dedup edge."""
    return (min(a, b), max(a, b))


def _deduplicate_entities(
    entities: list[dict],
    llm_aliases: dict[str, str] = None
) -> tuple[list[dict], dict[str, str]]:
    """
    Deduplikasi entitas menggunakan LLM Entity Linking untuk tipe tertentu,
    dan fallback string/substring matching untuk Author dan tipe lainnya.

    Returns:
        (canonical_entities, entity_map)
        entity_map: normalized_name → canonical_name
    """
    if llm_aliases is None:
        llm_aliases = {}
        
    canonical_entities: list[dict] = []
    entity_map: dict[str, str] = {}  # normalized → canonical_name
    
    # Buat dictionary lookup yang case-insensitive dari hasil LLM
    lower_aliases = {k.lower(): v for k, v in llm_aliases.items()}

    # Group by type
    by_type: dict[str, list[dict]] = {}
    for ent in entities:
        t = ent.get("type", "Unknown")
        by_type.setdefault(t, []).append(ent)

    for entity_type, group in by_type.items():
        type_canonical: list[dict] = []

        for ent in group:
            name = (ent.get("name") or "").strip()
            if not name:
                continue
                
            norm = _normalize(name)

            if norm in entity_map:
                continue

            merged = False
            
            # 1. Cek di LLM Aliases (Prioritas Utama untuk tipe terkait)
            if entity_type in ["Method", "Dataset", "Metric"]:
                if name.lower() in lower_aliases:
                    canonical_name = lower_aliases[name.lower()]
                    entity_map[norm] = canonical_name
                    
                    # Cari apakah canonical_name sudah ada di type_canonical
                    found = False
                    for canon in type_canonical:
                        if canon["name"].lower() == canonical_name.lower():
                            found = True
                            break
                            
                    if not found:
                        ent["name"] = canonical_name
                        type_canonical.append(ent)
                        
                    merged = True
                    continue

            # 2. Fallback untuk Author atau entitas yang tidak ada di LLM
            for canon in type_canonical:
                canon_name = canon["name"]
                canon_norm = _normalize(canon_name)

                # Exact match
                if canon_norm == norm:
                    entity_map[norm] = canon_name
                    merged = True
                    break

                # Substring check for Authors
                if entity_type == "Author":
                    if len(canon_norm) > 4 and len(norm) > 4:
                        if canon_norm in norm or norm in canon_norm:
                            # Keep the longer name
                            if len(name) > len(canon_name):
                                old_canon = canon_name
                                canon["name"] = name
                                for k in list(entity_map):
                                    if entity_map[k] == old_canon:
                                        entity_map[k] = name
                                canon_name = name
                            entity_map[norm] = canon_name
                            merged = True
                            break

            if not merged:
                entity_map[norm] = name
                type_canonical.append(ent)

        canonical_entities.extend(type_canonical)

    return canonical_entities, entity_map


def _add_same_author_edges(
    graph: nx.Graph,
    all_extractions: list[dict],
    entity_map: dict[str, str],
) -> None:
    """
    Tambahkan edge 'same_author' antara paper yang berbagi penulis.
    Deteksi penulis dari relasi 'written_by' dalam extractions.
    """
    paper_authors: dict[str, set[str]] = {}

    for extraction in all_extractions:
        paper_title = extraction.get("title", "")
        if not paper_title:
            continue

        authors: set[str] = set()
        for rel in extraction.get("relationships", []):
            if rel.get("type") == "written_by":
                target = (rel.get("target") or "").strip()
                if target:
                    # Normalize untuk perbandingan
                    authors.add(_normalize(target))

        if authors:
            paper_authors[paper_title] = authors

    # Cari pasangan paper dengan author yang sama
    paper_titles = list(paper_authors.keys())
    edges_added = 0

    for i in range(len(paper_titles)):
        for j in range(i + 1, len(paper_titles)):
            title_a = paper_titles[i]
            title_b = paper_titles[j]
            shared = paper_authors[title_a] & paper_authors[title_b]

            if shared and title_a in graph.nodes and title_b in graph.nodes:
                # Hindari duplikat
                if not graph.has_edge(title_a, title_b):
                    shared_display = ", ".join(list(shared)[:3])
                    graph.add_edge(
                        title_a, title_b,
                        type="same_author",
                        label="same author",
                        title=f"<b>Same Author</b><br>Shared: {shared_display}",
                        description=f"Papers share authors: {shared_display}",
                        source_paper="",
                    )
                    edges_added += 1

    if edges_added:
        logger.info(f"Ditambahkan {edges_added} edge 'same_author'")


def _connect_isolated_nodes(graph: nx.Graph) -> None:
    """
    Pastikan setiap node memiliki jalur (path) ke node Paper sumbernya.
    Jika tidak ada jalur sama sekali (baik terisolasi penuh atau bagian dari
    'pulau' kecil yang terputus), buat edge 'mentioned_in'.
    """
    paper_nodes = {
        n for n, d in graph.nodes(data=True)
        if d.get("type") == "Paper"
    }

    connected = 0
    for node_id, attrs in list(graph.nodes(data=True)):
        if attrs.get("type") == "Paper":
            continue

        source_paper = attrs.get("source_paper", "")
        if not source_paper or source_paper not in paper_nodes:
            continue

        # Cek apakah ada rute dari node ini ke paper sumbernya
        try:
            if nx.has_path(graph, node_id, source_paper):
                continue
        except nx.NodeNotFound:
            pass

        # Jika tidak ada rute, paksa hubungkan
        graph.add_edge(
            node_id,
            source_paper,
            type="mentioned_in",
            label="mentioned in",
            title="mentioned in\nEntity found in this paper",
            description="Entity found in this paper",
            source_paper=source_paper,
        )
        connected += 1

    if connected:
        logger.info(f"Dihubungkan {connected} node terputus ke paper sumbernya")
        print(f"  {connected} node terputus dihubungkan ke paper sumber")
