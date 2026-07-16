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
