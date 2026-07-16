import networkx as nx
from typing import Dict, Any

def get_1hop_neighbors(graph: nx.Graph, entry_point: str) -> Dict[str, Any]:
    """
    Mengambil tetangga 1-hop dari entry point di graph.
    Jika tetangga adalah "Paper", ia akan ditandai sebagai `is_paper_blocked` 
    untuk mencegah traversal lebih lanjut (berguna untuk iterasi selanjutnya).
    """
    if not graph.has_node(entry_point):
        return {
            "entry_point": entry_point, 
            "total_neighbors": 0,
            "paper_blocked": 0,
            "neighbors": [], 
            "error": "Node not found in graph"
        }
        
    neighbors_list = []
    paper_blocked = 0
    
    for neighbor in graph.neighbors(entry_point):
        edge_data = graph.get_edge_data(entry_point, neighbor)
        neighbor_data = graph.nodes[neighbor]
        
        node_type = neighbor_data.get("type", "Unknown")
        # Handle cases where multiple edges might exist (NetworkX MultiGraph), though we use standard Graph
        # So edge_data is just a dict of attributes.
        rel_type = edge_data.get("type", "Unknown")
        
        is_paper_blocked = (node_type == "Paper")
        if is_paper_blocked:
            paper_blocked += 1
            
        neighbors_list.append({
            "node_id": neighbor,
            "relationship_type": rel_type,
            "node_type": node_type,
            "is_paper_blocked": is_paper_blocked
        })
        
    return {
        "entry_point": entry_point,
        "total_neighbors": len(neighbors_list),
        "paper_blocked": paper_blocked,
        "neighbors": neighbors_list
    }

def serialize_traversal_results(traversal_data: Dict[str, Any]) -> str:
    """
    Mengubah hasil get_1hop_neighbors menjadi teks natural untuk diumpankan ke LLM prompt.
    """
    if "error" in traversal_data:
        return f"Informasi tentang '{traversal_data.get('entry_point')}' tidak ditemukan di dalam graf."
        
    entry_point = traversal_data["entry_point"]
    neighbors = traversal_data["neighbors"]
    
    if not neighbors:
        return f"Tidak ada informasi relasional yang ditemukan untuk '{entry_point}'."
        
    by_rel: Dict[str, List[Dict[str, Any]]] = {}
    for n in neighbors:
        rel = n["relationship_type"]
        by_rel.setdefault(rel, []).append(n)
        
    lines = []
    lines.append(f"=== KONTEKS UNTUK: {entry_point} ===\n")
    
    # Pemetaan frase bahasa natural
    phrase_map = {
        "compares": "dibandingkan dengan",
        "uses_dataset": "menggunakan dataset",
        "uses_method": "menggunakan metode/komponen",
        "uses_metric": "dievaluasi menggunakan metrik",
        "proposes_method": "diusulkan dalam",
        "has_limitation": "memiliki batasan/kelemahan berupa",
        "finds": "memiliki temuan atau karakteristik:",
        "written_by": "ditulis oleh author",
        "mentioned_in": "secara eksplisit dibahas dalam"
    }
    
    for rel_type, items in by_rel.items():
        rel_phrase = phrase_map.get(rel_type, "memiliki relasi dengan")
        lines.append(f"KATEGORI RELASI: {rel_type.upper()}")
        for item in items:
            target = item["node_id"]
            if item["is_paper_blocked"]:
                if rel_type == "proposes_method":
                    lines.append(f"- [Entry Point] {entry_point} diusulkan dalam paper ({rel_type}) '{target}'.")
                else:
                    lines.append(f"- [Entry Point] {entry_point} {rel_phrase} ({rel_type}) paper '{target}'.")
            else:
                lines.append(f"- [Entry Point] {entry_point} {rel_phrase} ({rel_type}) '{target}'.")
        lines.append("") # Spasi antar grup
        
    return "\n".join(lines).strip()
