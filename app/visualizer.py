"""
visualizer.py — Tahap 7: Visualisasi graph interaktif menggunakan Pyvis.

Output: file graph.html yang bisa dibuka langsung di browser.
Fitur:
- Warna node berdasarkan tipe entitas
- Ukuran node berdasarkan degree (lebih terhubung = lebih besar)
- Tooltip detail saat hover node dan edge
- Physics force-directed yang stabil
- Legend panel di pojok kanan
- Dark theme background
"""

import logging

import networkx as nx
from pyvis.network import Network

from app.config import NODE_COLORS

logger = logging.getLogger(__name__)

# Warna edge berdasarkan tipe relasi
_EDGE_COLORS: dict[str, str] = {
    "written_by":      "#E74C3C",
    "affiliated_with": "#E74C3C",
    "uses_method":     "#2ECC71",
    "proposes_method": "#27AE60",
    "uses_dataset":    "#F39C12",
    "uses_metric":     "#E67E22",
    "finds":           "#9B59B6",
    "has_limitation":  "#95A5A6",
    "criticizes":      "#E74C3C",
    "builds_on":       "#3498DB",
    "compares":        "#1ABC9C",
    "same_author":     "#BDC3C7",
}

_DEFAULT_EDGE_COLOR = "#555577"


def visualize(graph: nx.Graph, output_path: str = "output/graph.html") -> None:
    """
    Buat visualisasi interaktif dari graph dan simpan ke HTML.

    Args:
        graph:       NetworkX Graph.
        output_path: Path output file HTML.
    """
    if graph.number_of_nodes() == 0:
        logger.warning("Graph kosong, visualisasi di-skip.")
        return

    net = Network(
        height="100vh",
        width="100%",
        bgcolor="#0f0f1a",
        font_color="#e0e0e0",
        directed=False,
        notebook=False,
        select_menu=False,
        filter_menu=False,
    )

    # Hitung frekuensi tipe node untuk hirarki ukuran
    type_counts = {}
    for _, attrs in graph.nodes(data=True):
        t = attrs.get("type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    max_count = max(type_counts.values()) if type_counts else 1

    # ── Tambahkan node ─────────────────────────────────────────
    for node_id, attrs in graph.nodes(data=True):
        node_type   = attrs.get("type", "Unknown")
        color       = NODE_COLORS.get(node_type, "#808080")
        degree      = graph.degree(node_id)

        # Ukuran node hirarkis: semakin sedikit jumlah tipenya, semakin besar base size-nya
        base_size = 60 - (type_counts.get(node_type, 1) / max_count) * 40
        size = base_size + (degree * 1.5)
        # Cap the maximum size to prevent physics engine issues with hub nodes
        size = min(size, 250)

        # Tooltip plain text (pyvis escape HTML di title, jadi pakai newline)
        source = attrs.get("source_paper", "")
        tooltip_parts = [
            node_id,
            f"Type: {node_type}",
            f"Connections: {degree}",
        ]
        if source:
            tooltip_parts.append(f"Paper: {source[:70]}")
        tooltip = "\n".join(tooltip_parts)

        net.add_node(
            node_id,
            label=_truncate(node_id, 28),
            color={
                "background": color,
                "border":     _darken_hex(color),
                "highlight":  {"background": color, "border": color},
                "hover":      {"background": color, "border": color},
            },
            size=size,
            title=tooltip,
            shape="dot",
            font={"size": 1, "color": "#e0e0e0", "strokeWidth": 3, "strokeColor": "#000"},
            entity_type=node_type
        )

    # ── Tambahkan edge ─────────────────────────────────────────
    for source, target, attrs in graph.edges(data=True):
        rel_type    = attrs.get("type", "")
        description = attrs.get("description", "")
        edge_color  = _EDGE_COLORS.get(rel_type, _DEFAULT_EDGE_COLOR)

        label_text = rel_type.replace("_", " ").title()
        tooltip_parts = [label_text]
        if description:
            tooltip_parts.append(description[:120])
        tooltip = "\n".join(tooltip_parts)

        net.add_edge(
            source,
            target,
            title=tooltip,
            label="",
            color={"color": edge_color, "highlight": "#ffffff", "hover": "#ffffff"},
            width=3.5,
            smooth={"type": "continuous"},
            rel_type=rel_type
        )

    # ── Physics & interaksi ────────────────────────────────────
    net.repulsion(
        node_distance=150,
        central_gravity=0.1,
        spring_length=200,
        spring_strength=0.05,
        damping=0.09
    )

    net.set_options("""
    {
      "physics": {
        "enabled": true,
        "solver": "forceAtlas2Based",
        "forceAtlas2Based": {
          "gravitationalConstant": -1500,
          "centralGravity": 0.005,
          "springLength": 500,
          "springConstant": 0.05,
          "damping": 0.8,
          "avoidOverlap": 1.0
        },
        "stabilization": {
          "enabled": true,
          "iterations": 400,
          "updateInterval": 25,
          "fit": true
        },
        "minVelocity": 0.75
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 80,
        "hideEdgesOnDrag": false,
        "hideNodesOnDrag": false,
        "navigationButtons": true,
        "keyboard": {"enabled": true}
      },
      "nodes": {
        "borderWidth": 1.5,
        "shadow": {"enabled": true, "color": "rgba(0,0,0,0.6)", "size": 8, "x": 2, "y": 2},
        "font": {
            "size": 30,
            "color": "#e0e0e0",
            "strokeWidth": 4,
            "strokeColor": "#0f0f1a"
        }
      },
      "edges": {
        "shadow": false,
        "selectionWidth": 3,
        "hoverWidth": 2
      }
    }
    """)

    # Generate HTML dan inject komponen tambahan
    html_content = net.generate_html()
    html_content = _inject_ui(html_content, graph)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info(f"Visualisasi disimpan ke: {output_path}")


# ─── Private helpers ──────────────────────────────────────────

def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[:max_len - 2] + "…"


def _darken_hex(hex_color: str, factor: float = 0.7) -> str:
    """Gelapkan warna hex untuk border node."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r, g, b = int(r * factor), int(g * factor), int(b * factor)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


def _inject_ui(html: str, graph: nx.Graph) -> str:
    """
    Inject legend panel dan stats bar ke dalam HTML output Pyvis.
    """
    # Hitung statistik
    type_counts: dict[str, int] = {}
    for _, attrs in graph.nodes(data=True):
        t = attrs.get("type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    # Build legend items
    legend_items = ""
    for entity_type, color in NODE_COLORS.items():
        count = type_counts.get(entity_type, 0)
        if count == 0:
            continue
        legend_items += f"""
        <div id="legend-btn-{entity_type}" class="legend-item" onclick="highlightType('{entity_type}')" title="Klik untuk highlight semua node {entity_type}">
            <div class="legend-dot" style="background:{color}"></div>
            <span>{entity_type} <span class="count">({count})</span></span>
        </div>"""

    edge_counts: dict[str, int] = {}
    for _, _, attrs in graph.edges(data=True):
        t = attrs.get("type", "Unknown")
        edge_counts[t] = edge_counts.get(t, 0) + 1

    edge_options = ""
    # Sort edges by count descending
    for edge_type, count in sorted(edge_counts.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            label = edge_type.replace("_", " ").title()
            edge_options += f'<option value="{edge_type}">{label} ({count})</option>'

    stats_html = (
        f"{graph.number_of_nodes()} nodes &nbsp;•&nbsp; "
        f"{graph.number_of_edges()} edges"
    )

    injected = f"""
<style>
  body {{ margin: 0; overflow: hidden; }}
  
  /* Override PyVis default loading screen */
  #loadingBar {{
      background-color: #0f0f1a !important;
  }}
  div.outerBorder {{
      border: 1px solid rgba(255,255,255,0.2) !important;
      background: rgba(0,0,0,0.5) !important;
      border-radius: 20px !important;
      box-shadow: 0 4px 15px rgba(0,0,0,0.5) !important;
      top: 50% !important;
      transform: translateY(-50%) !important;
      margin: 0 auto !important;
  }}
  #text {{
      position: absolute !important;
      top: -30px !important;
      left: 0 !important;
      width: 100% !important;
      text-align: center !important;
      color: #a0c4ff !important;
      font-size: 16px !important;
      margin: 0 !important;
  }}
  #bar {{
      background-color: #a0c4ff !important;
  }}

  #right-panel {{
    position: fixed;
    top: 16px;
    right: 16px;
    width: 220px;
    max-height: calc(100vh - 32px);
    background: rgba(15,15,26,0.92);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 12px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.6);
    z-index: 9999;
    overflow-y: auto;
    font-family: 'Segoe UI', Arial, sans-serif;
    color: #e0e0e0;
    backdrop-filter: blur(10px);
    pointer-events: all;
  }}
  #right-panel::-webkit-scrollbar {{ width: 6px; }}
  #right-panel::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.2); border-radius: 3px; }}
  
  .rp-section {{
    border-bottom: 1px solid rgba(255,255,255,0.1);
  }}
  .rp-section:last-child {{ border-bottom: none; }}
  .rp-summary {{
    padding: 12px 16px;
    font-size: 13px;
    font-weight: bold;
    color: #a0c4ff;
    cursor: pointer;
    user-select: none;
    display: flex;
    align-items: center;
    list-style: none;
    outline: none;
    transition: background 0.2s;
  }}
  .rp-summary::-webkit-details-marker {{ display: none; }}
  .rp-summary:hover {{ background: rgba(255,255,255,0.05); }}
  .rp-summary::after {{
    content: '▼';
    font-size: 10px;
    margin-left: auto;
    transition: transform 0.2s;
    color: #888;
  }}
  details[open] .rp-summary::after {{ transform: rotate(180deg); }}
  .rp-content {{
    padding: 0 16px 16px 16px;
    font-size: 13px;
  }}
  .rp-summary-icon {{
    margin-right: 8px;
  }}
  .info-icon {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    background: rgba(255,255,255,0.1);
    color: #a0c4ff;
    border-radius: 50%;
    font-size: 11px;
    font-weight: bold;
    margin-left: 8px;
    cursor: help;
    position: relative;
  }}

  .legend-item {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
    font-size: 14px;
    cursor: pointer;
    padding: 6px;
    border-radius: 6px;
    transition: background 0.2s, transform 0.1s;
  }}
  .legend-item:hover {{
    background: rgba(255,255,255,0.15);
  }}
  .legend-item:active {{
    transform: scale(0.97);
  }}
  .legend-item.active-filter {{
    background: rgba(160,196,255,0.2);
    box-shadow: inset 0 2px 5px rgba(0,0,0,0.6);
    border-left: 3px solid #a0c4ff;
    border-radius: 4px;
  }}
  .legend-dot {{
    width: 14px;
    height: 14px;
    border-radius: 50%;
    flex-shrink: 0;
    box-shadow: 0 0 4px rgba(0,0,0,0.4);
  }}
  .count {{ color: #888; font-size: 11px; }}
  
  /* Sembunyikan navigasi selain tombol Fit/Center */
  .vis-button.vis-zoomIn, 
  .vis-button.vis-zoomOut, 
  .vis-button.vis-up, 
  .vis-button.vis-down, 
  .vis-button.vis-left, 
  .vis-button.vis-right {{
    display: none !important;
  }}
  
  /* Percantik tombol Fit (Center) agar kelihatan di Dark Mode */
  .vis-button.vis-zoomExtends {{
    background-color: #e0e0e0 !important;
    border: 2px solid #333 !important;
    border-radius: 6px !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.6) !important;
    opacity: 0.8;
    transition: opacity 0.2s, transform 0.1s;
  }}
  .vis-button.vis-zoomExtends:hover {{
    opacity: 1.0;
    transform: scale(1.05);
  }}
  
  #stats-bar {{
    background: rgba(15,15,26,0.85);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    padding: 8px 12px;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 12px;
    color: #888;
    text-align: center;
    pointer-events: all;
  }}
  #hint {{
    font-size: 11px;
    color: rgba(255,255,255,0.3);
    text-align: center;
    margin-top: 8px;
    line-height: 1.5;
    pointer-events: none;
  }}
  /* Hilangkan tombol Pyvis default yang mengganggu */
  #config {{ display: none !important; }}
  
  /* --- Search UI --- */
  #search-container {{
    position: absolute;
    top: 20px !important;
    left: 20px !important;
    width: 320px;
    z-index: 9999;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    pointer-events: auto;
  }}
  #search-input {{
    width: 100%;
    padding: 12px 35px 12px 16px;
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.2);
    background: rgba(15,15,26,0.85);
    color: #e0e0e0;
    font-size: 14px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    outline: none;
    transition: all 0.2s;
    backdrop-filter: blur(5px);
    box-sizing: border-box;
  }}
  #search-input:focus {{
    border-color: #a0c4ff;
    box-shadow: 0 4px 20px rgba(160,196,255,0.2);
    background: rgba(20,20,32,0.95);
  }}
  #clear-search {{
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    color: #888;
    font-size: 18px;
    cursor: pointer;
    padding: 0;
    line-height: 1;
  }}
  #clear-search:hover {{ color: #fff; }}
  #search-dropdown {{
    display: none;
    position: absolute;
    top: calc(100% + 8px);
    left: 0;
    right: 0;
    background: rgba(20,20,32,0.95);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    max-height: 350px;
    overflow-y: auto;
    box-shadow: 0 8px 25px rgba(0,0,0,0.7);
    backdrop-filter: blur(10px);
  }}
  .search-item {{
    padding: 10px 16px;
    cursor: pointer;
    font-size: 13px;
    color: #ccc;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: background 0.1s;
  }}
  .search-item:last-child {{ border-bottom: none; }}
  .search-item:hover {{
    background: rgba(160,196,255,0.15);
    color: #fff;
  }}
  .search-item-type {{
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 4px;
    background: rgba(255,255,255,0.1);
    color: #a0c4ff;
  }}
  
  /* --- Info Panel --- */
  #info-panel {{
    position: absolute;
    left: -400px;
    top: 80px;
    width: 320px;
    background: rgba(15,15,26,0.95);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 8px;
    box-shadow: 0 8px 30px rgba(0,0,0,0.7);
    backdrop-filter: blur(10px);
    z-index: 9998;
    transition: left 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    color: #e0e0e0;
    pointer-events: auto;
    display: flex;
    flex-direction: column;
    max-height: calc(100vh - 100px);
  }}
  #info-panel.open {{
    left: 20px;
  }}
  #close-info {{
    position: absolute;
    top: 10px;
    right: 12px;
    background: none;
    border: none;
    color: #888;
    font-size: 24px;
    cursor: pointer;
    line-height: 1;
  }}
  #close-info:hover {{ color: #fff; }}
  #info-header {{
    padding: 20px 20px 10px 20px;
    border-bottom: 1px solid rgba(255,255,255,0.05);
  }}
  #info-badge {{
    display: inline-block;
    font-size: 10px;
    padding: 3px 8px;
    border-radius: 4px;
    background: rgba(255,255,255,0.1);
    margin-bottom: 8px;
    text-transform: uppercase;
    font-weight: bold;
    letter-spacing: 0.5px;
    color: #fff;
  }}
  #info-title {{
    margin: 0;
    font-size: 18px;
    color: #fff;
    line-height: 1.3;
  }}
  #info-content {{
    padding: 15px 20px 20px 20px;
    overflow-y: auto;
    font-size: 12px;
  }}
  .info-group {{ margin-bottom: 16px; }}
  .info-group:last-child {{ margin-bottom: 0; }}
  .info-group-title {{
    color: #a0c4ff;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    padding-bottom: 6px;
    font-weight: bold;
  }}
  .info-tag {{
    display: inline-block;
    padding: 4px 8px;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 4px;
    margin: 3px 3px 0 0;
    cursor: pointer;
    transition: all 0.1s;
    color: #ccc;
  }}
  .info-tag:hover {{
    background: rgba(160,196,255,0.2);
    border-color: #a0c4ff;
    color: #fff;
  }}

  .analytics-category {{
    margin-bottom: 20px;
  }}
  .analytics-category:last-child {{
    margin-bottom: 0;
  }}
  .analytics-category h4 {{
    margin: 0 0 10px 0;
    font-size: 12px;
    text-transform: uppercase;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    padding-bottom: 5px;
  }}
  .analytics-item {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 8px;
    background: rgba(255,255,255,0.03);
    border-radius: 4px;
    margin-bottom: 6px;
    cursor: pointer;
    border: 1px solid transparent;
    transition: all 0.2s;
  }}
  .analytics-item:hover {{
    background: rgba(160,196,255,0.15);
    border-color: rgba(160,196,255,0.3);
  }}
  .analytics-item-name {{
    font-size: 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 140px;
  }}
  .analytics-item-score {{
    font-size: 11px;
    color: #ffd700;
    font-weight: bold;
    background: rgba(255,215,0,0.1);
    padding: 2px 6px;
    border-radius: 10px;
    white-space: nowrap;
    flex-shrink: 0;
  }}

  .tab-btn {{
      flex: 1;
      background: none;
      border: none;
      color: #888;
      padding: 8px 0;
      cursor: pointer;
      font-size: 13px;
      border-bottom: 2px solid transparent;
      outline: none;
  }}
  .tab-btn.active {{
      color: #a0c4ff;
      border-bottom-color: #a0c4ff;
  }}
  .mh-input {{
      width: 100%;
      box-sizing: border-box;
      padding: 8px 10px;
      margin-top: 5px;
      background: rgba(0,0,0,0.3);
      border: 1px solid #444;
      color: #fff;
      border-radius: 4px;
      font-size: 13px;
      outline: none;
  }}
  .mh-input:focus {{
      border-color: #a0c4ff;
  }}
  .mh-action-btn {{
      width: 100%;
      margin-top: 15px;
      padding: 8px;
      background: #4A90D9;
      color: #fff;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-weight: bold;
      transition: background 0.2s;
  }}
  .mh-action-btn:hover {{
      background: #357ABD;
  }}
</style>

<div id="search-container">
  <input type="text" id="search-input" placeholder="🔍 Search Node" autocomplete="off">
  <button id="clear-search" style="display: none;">&times;</button>
  <div id="search-dropdown"></div>
</div>

<div id="info-panel">
  <button id="close-info" title="Tutup">&times;</button>
  <div id="info-header">
      <span id="info-badge"></span>
      <h3 id="info-title"></h3>
      <div id="info-connections" style="font-size: 11px; color: #888; margin-top: 6px;"></div>
  </div>
  <div id="info-content"></div>
</div>

<div id="right-panel">
  <details class="rp-section" open>
    <summary class="rp-summary">
      <span class="rp-summary-icon">📊</span> Entity Types
    </summary>
    <div class="rp-content">
      <div style="margin-bottom:12px; display:flex; align-items:center;">
        <span style="font-size:12px; color:#a0c4ff; font-weight:bold;">Legend</span>
        <div class="info-icon" id="legend-info-icon">?</div>
      </div>
      {legend_items}
      <div id="hint" style="margin-top:15px; text-align:center; color:#888; font-size:11px;">Hover untuk detail<br>Drag &amp; scroll to navigate</div>
      <div id="stats-bar" style="margin-top:15px; padding-top:10px; border-top:1px solid rgba(255,255,255,0.1); text-align:center;">{stats_html}</div>
    </div>
  </details>

  <details class="rp-section" id="details-insights">
    <summary class="rp-summary">
      <span class="rp-summary-icon">📈</span> Network Insights
    </summary>
    <div class="rp-content" id="analytics-content">
      <!-- Generated by JS -->
    </div>
  </details>

  <details class="rp-section" id="details-edge-filter">
    <summary class="rp-summary">
      <span class="rp-summary-icon">🔍</span> Edge Filters
    </summary>
    <div class="rp-content">
      <label style="font-size:12px; color:#aaa;">Highlight Relasi Spesifik:</label>
      <select id="edge-type-select" style="width: 100%; margin-top: 8px; padding: 8px; background: rgba(15,15,26,0.85); color: #e0e0e0; border: 1px solid rgba(255,255,255,0.2); border-radius: 6px; font-size: 13px; outline: none; cursor: pointer;">
        <option value="all">-- Tampilkan Semua --</option>
        {edge_options}
      </select>
      <div id="edge-filter-desc" style="display:none; margin-top: 10px; font-size: 11px; color: #a0c4ff; line-height: 1.4; padding: 8px; background: rgba(160,196,255,0.1); border-left: 3px solid #a0c4ff; border-radius: 0 4px 4px 0;"></div>
    </div>
  </details>

  <details class="rp-section" id="details-multihop">
    <summary class="rp-summary">
      <span class="rp-summary-icon">🔗</span> Path Discovery
    </summary>
    <div class="rp-content">
      <label style="font-size:12px; color:#aaa;">Titik Awal (Node A)</label>
      <input type="text" id="mh-node-a" class="mh-input" list="mh-nodelist" autocomplete="off" placeholder="Pilih Node A...">
      
      <label style="font-size:12px; color:#aaa; margin-top:10px; display:block;">Titik Tujuan (Node B)</label>
      <input type="text" id="mh-node-b" class="mh-input" list="mh-nodelist" autocomplete="off" placeholder="Pilih Node B...">
      
      <button id="mh-run-dijkstra" class="mh-action-btn">Temukan Jalur</button>
      <div id="mh-dijkstra-result" style="margin-top:15px; font-size:13px; color:#ccc;"></div>
    </div>
  </details>
</div>
<datalist id="mh-nodelist"></datalist>

<div id="global-legend-tooltip" style="display:none; position:fixed; width:230px; background:rgba(15,15,26,0.98); color:#ccc; border:1px solid rgba(255,255,255,0.2); border-radius:8px; padding:12px; font-size:12px; line-height:1.5; z-index:10000; box-shadow:0 4px 15px rgba(0,0,0,0.8); pointer-events:none;">
    <strong style="color:#a0c4ff;">Paper:</strong> Dokumen paper utama.<br>
    <strong style="color:#a0c4ff;">Author:</strong> Penulis paper.<br>
    <strong style="color:#a0c4ff;">Institution:</strong> Afiliasi tempat penulis bernaung.<br>
    <strong style="color:#a0c4ff;">Method:</strong> Algoritma, model arsitektur, teknik, atau pendekatan spesifik.<br>
    <strong style="color:#a0c4ff;">Dataset:</strong> Kumpulan data untuk melatih/menguji model.<br>
    <strong style="color:#a0c4ff;">Metric:</strong> Tolak ukur atau standar perhitungan untuk mengevaluasi.<br>
    <strong style="color:#a0c4ff;">Finding:</strong> Kesimpulan, hasil utama, atau penemuan.<br>
    <strong style="color:#a0c4ff;">Limitation:</strong> Kelemahan, batasan, atau kekurangan.
</div>

<script>
  var currentHighlightedType = null;
  var currentSearchNodeId = null;
  
  function hexToRgba(hex, alpha) {{
      if (!hex || typeof hex !== 'string') return 'rgba(128,128,128,' + alpha + ')';
      var r = parseInt(hex.slice(1, 3), 16),
          g = parseInt(hex.slice(3, 5), 16),
          b = parseInt(hex.slice(5, 7), 16);
      return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
  }}

  function resetHighlight() {{
      if (typeof nodes === 'undefined' || typeof edges === 'undefined') return;
      
      // Hapus status aktif dari semua tombol legend
      var legends = document.getElementsByClassName('legend-item');
      for (var k = 0; k < legends.length; k++) {{
          legends[k].classList.remove('active-filter');
      }}
      
      // Tutup panel info
      var infoPanel = document.getElementById('info-panel');
      if (infoPanel) infoPanel.classList.remove('open');
      
      var allNodesData = nodes.get();
      var updates = [];
      for (var i = 0; i < allNodesData.length; i++) {{
          var bg = allNodesData[i].original_bg || (allNodesData[i].color ? allNodesData[i].color.background : '#888');
          var bd = allNodesData[i].original_border || (allNodesData[i].color ? allNodesData[i].color.border : '#666');
          updates.push({{
              id: allNodesData[i].id, 
              color: {{ background: bg, border: bd }}, 
              font: {{ color: "#e0e0e0" }},
              shadow: false
          }});
      }}
      nodes.update(updates);
      
      var allEdgesData = edges.get();
      var edgeUpdates = [];
      for (var j = 0; j < allEdgesData.length; j++) {{
          edgeUpdates.push({{id: allEdgesData[j].id, color: {{ opacity: 1.0 }}, hidden: false}});
      }}
      edges.update(edgeUpdates);
      network.unselectAll();
  }}

  function highlightType(type) {{
    if (typeof network === 'undefined' || typeof nodes === 'undefined' || typeof edges === 'undefined') return;
    
    // Clear search jika aktif
    if (currentSearchNodeId !== null) {{
        document.getElementById('search-input').value = '';
        document.getElementById('clear-search').style.display = 'none';
        currentSearchNodeId = null;
    }}
    
    if (currentHighlightedType === type) {{
        currentHighlightedType = null;
        resetHighlight();
    }} else {{
        currentHighlightedType = type;
        
        // Update visual tombol legend
        var legends = document.getElementsByClassName('legend-item');
        for (var k = 0; k < legends.length; k++) {{
            legends[k].classList.remove('active-filter');
        }}
        var activeBtn = document.getElementById('legend-btn-' + type);
        if (activeBtn) activeBtn.classList.add('active-filter');
        
        var allNodesData = nodes.get();
        var allEdgesData = edges.get();
        var nodesToSelect = [];
        var selectedNodeIds = new Set();
        var connectedNodeIds = new Set();
        
        // 1. Kumpulkan semua node utama yang sesuai tipe
        for (var i = 0; i < allNodesData.length; i++) {{
            if (allNodesData[i].entity_type === type) {{
                nodesToSelect.push(allNodesData[i].id);
                selectedNodeIds.add(allNodesData[i].id);
            }}
        }}
        
        // 2. Kumpulkan semua node yang terhubung langsung (1st-degree)
        for (var j = 0; j < allEdgesData.length; j++) {{
            var e = allEdgesData[j];
            if (selectedNodeIds.has(e.from)) connectedNodeIds.add(e.to);
            if (selectedNodeIds.has(e.to)) connectedNodeIds.add(e.from);
        }}
        
        // 3. Terapkan efek visual
        var updates = [];
        for (var i = 0; i < allNodesData.length; i++) {{
            var n = allNodesData[i];
            if (!n.original_bg) n.original_bg = n.color.background;
            if (!n.original_border) n.original_border = n.color.border;
            
            if (selectedNodeIds.has(n.id)) {{
                // Node Utama: Glow terang benderang
                updates.push({{
                    id: n.id, 
                    color: {{ background: n.original_bg, border: '#ffffff' }},
                    font: {{ color: "#ffffff" }},
                    shadow: {{enabled: true, color: n.original_bg, size: 30, x: 0, y: 0}}
                }});
            }} else if (connectedNodeIds.has(n.id)) {{
                // Node Terhubung: Tetap jelas terlihat, tapi tidak glow
                updates.push({{
                    id: n.id, 
                    color: {{ background: n.original_bg, border: n.original_border }},
                    font: {{ color: "#e0e0e0" }},
                    shadow: false
                }});
            }} else {{
                // Node Tidak Terhubung: Sangat redup
                updates.push({{
                    id: n.id, 
                    color: {{ 
                        background: hexToRgba(n.original_bg, 0.15), 
                        border: hexToRgba(n.original_border, 0.15) 
                    }},
                    font: {{ color: "rgba(224,224,224,0.15)" }},
                    shadow: false
                }});
            }}
        }}
        nodes.update(updates);
        
        // 4. Update Edges
        var edgeUpdates = [];
        for (var j = 0; j < allEdgesData.length; j++) {{
            var e = allEdgesData[j];
            if (selectedNodeIds.has(e.from) || selectedNodeIds.has(e.to)) {{
                // Edge terhubung -> Jelas
                edgeUpdates.push({{id: e.id, color: {{ opacity: 1.0 }}, hidden: false}});
            }} else {{
                // Edge tidak terhubung -> Redup
                edgeUpdates.push({{id: e.id, color: {{ opacity: 0.02 }}, hidden: false}});
            }}
        }}
        edges.update(edgeUpdates);
        
        network.selectNodes(nodesToSelect, false);
    }}
  }}
  
  // Jika user klik tempat kosong, reset highlight
  setTimeout(function() {{
      if (typeof network !== 'undefined') {{
          network.on("click", function(params) {{
              if (params.nodes.length === 0) {{
                  if (currentHighlightedType !== null || currentSearchNodeId !== null) {{
                      currentHighlightedType = null;
                      currentSearchNodeId = null;
                      document.getElementById('search-input').value = '';
                      document.getElementById('clear-search').style.display = 'none';
                      resetHighlight();
                  }}
              }} else if (params.nodes.length > 0) {{
                  // Sinkronisasi click native dengan UI pencarian
                  var clickedId = params.nodes[0];
                  var n = nodes.get(clickedId);
                  if (n) {{
                      document.getElementById('search-input').value = n.label;
                      document.getElementById('clear-search').style.display = 'block';
                      currentSearchNodeId = clickedId;
                      currentHighlightedType = null;
                  }}
              }}
          }});
          network.on("doubleClick", function(params) {{
              if (params.nodes.length > 0) {{
                  executeSearchSelection(params.nodes[0]);
              }}
          }});
      }}
  }}, 1000);
  
  // --- SEARCH JAVASCRIPT ---
  var searchInput = document.getElementById('search-input');
  var searchDropdown = document.getElementById('search-dropdown');
  var clearSearchBtn = document.getElementById('clear-search');

  function renderSearchDropdown(query) {{
      if (!query) {{
          searchDropdown.style.display = 'none';
          return;
      }}
      
      var allNodesData = nodes.get();
      var matches = [];
      var q = query.toLowerCase();
      
      for (var i = 0; i < allNodesData.length; i++) {{
          var n = allNodesData[i];
          if (n.id && n.id.toLowerCase().includes(q)) {{
              matches.push(n);
          }}
      }}
      
      if (matches.length === 0) {{
          searchDropdown.innerHTML = '<div style="padding: 10px; color: #888; font-size: 12px; text-align: center;">Tidak ditemukan.</div>';
          searchDropdown.style.display = 'block';
          return;
      }}
      
      // Sort: Exact match > Starts with > Alphabetical
      matches.sort(function(a, b) {{
          var aLbl = a.id.toLowerCase();
          var bLbl = b.id.toLowerCase();
          if (aLbl === q && bLbl !== q) return -1;
          if (bLbl === q && aLbl !== q) return 1;
          if (aLbl.startsWith(q) && !bLbl.startsWith(q)) return -1;
          if (bLbl.startsWith(q) && !aLbl.startsWith(q)) return 1;
          return aLbl.localeCompare(bLbl);
      }});
      
      matches = matches.slice(0, 50); // Limit 50 results
      
      var html = '';
      for (var i = 0; i < matches.length; i++) {{
          html += '<div class="search-item" data-id="' + matches[i].id.replace(/"/g, '&quot;') + '">' + 
                  '<span>' + matches[i].id + '</span>' + 
                  '<span class="search-item-type">' + matches[i].entity_type + '</span>' + 
                  '</div>';
      }}
      
      searchDropdown.innerHTML = html;
      searchDropdown.style.display = 'block';
      
      var items = searchDropdown.getElementsByClassName('search-item');
      for (var i = 0; i < items.length; i++) {{
          items[i].addEventListener('click', function(e) {{
              var nodeId = this.getAttribute('data-id');
              executeSearchSelection(nodeId);
          }});
      }}
  }}

  function executeSearchSelection(nodeId) {{
      searchDropdown.style.display = 'none';
      var n = nodes.get(nodeId);
      if (!n) return;
      
      searchInput.value = n.id;
      clearSearchBtn.style.display = 'block';
      currentSearchNodeId = nodeId;
      
      if (currentHighlightedType !== null) {{
          currentHighlightedType = null;
      }}
      
      var allNodesData = nodes.get();
      var allEdgesData = edges.get();
      var connectedNodeMap = new Map();
      
      for (var j = 0; j < allEdgesData.length; j++) {{
          var e = allEdgesData[j];
          if (e.from == nodeId) connectedNodeMap.set(e.to, e.rel_type || '');
          if (e.to == nodeId) connectedNodeMap.set(e.from, e.rel_type || '');
      }}
      
      var updates = [];
      for (var i = 0; i < allNodesData.length; i++) {{
          var node = allNodesData[i];
          if (!node.original_bg) node.original_bg = node.color.background;
          if (!node.original_border) node.original_border = node.color.border;
          
          if (node.id == nodeId) {{
              updates.push({{
                  id: node.id, 
                  color: {{ background: node.original_bg, border: '#ffffff' }},
                  font: {{ color: "#ffffff" }},
                  shadow: {{enabled: true, color: node.original_bg, size: 30, x: 0, y: 0}}
              }});
          }} else if (connectedNodeMap.has(node.id)) {{
              updates.push({{
                  id: node.id, 
                  color: {{ background: node.original_bg, border: node.original_border }},
                  font: {{ color: "#e0e0e0" }},
                  shadow: false
              }});
          }} else {{
              updates.push({{
                  id: node.id, 
                  color: {{ 
                      background: hexToRgba(node.original_bg, 0.15), 
                      border: hexToRgba(node.original_border, 0.15) 
                  }},
                  font: {{ color: "rgba(224,224,224,0.15)" }},
                  shadow: false
              }});
          }}
      }}
      nodes.update(updates);
      
      var edgeUpdates = [];
      for (var j = 0; j < allEdgesData.length; j++) {{
          var e = allEdgesData[j];
          if (e.from == nodeId || e.to == nodeId) {{
              edgeUpdates.push({{id: e.id, color: {{ opacity: 1.0 }}, hidden: false}});
          }} else {{
              edgeUpdates.push({{id: e.id, color: {{ opacity: 0.02 }}, hidden: false}});
          }}
      }}
      edges.update(edgeUpdates);
      
      network.selectNodes([nodeId], false);
      network.focus(nodeId, {{
          scale: 0.25,
          animation: {{ duration: 1000, easingFunction: "easeInOutQuad" }}
      }});
      
      // --- POPULATE INFO PANEL ---
      var infoPanel = document.getElementById('info-panel');
      var infoTitle = document.getElementById('info-title');
      var infoBadge = document.getElementById('info-badge');
      var infoContent = document.getElementById('info-content');
      var infoConnections = document.getElementById('info-connections');
      
      if (infoPanel && infoTitle && infoBadge && infoContent) {{
          infoTitle.innerText = n.id;
          infoBadge.innerText = n.entity_type || 'Unknown';
          
          if (infoConnections) {{
              infoConnections.innerText = "Total Koneksi: " + connectedNodeMap.size + " relasi";
          }}
          
          var bgColor = n.original_bg || '#666';
          infoBadge.style.background = bgColor;
          
          var connectionsByType = {{}};
          var crossPapers = [];
          
          connectedNodeMap.forEach(function(relLabel, cid) {{
              var cn = nodes.get(cid);
              if (cn) {{
                  if (n.entity_type !== 'Paper' && cn.entity_type === 'Paper') {{
                      crossPapers.push({{ node: cn, rel: relLabel }});
                  }} else {{
                      var t = cn.entity_type || 'Other';
                      if (!connectionsByType[t]) connectionsByType[t] = [];
                      connectionsByType[t].push({{ node: cn, rel: relLabel }});
                  }}
              }}
          }});
          
          var htmlContent = '';
          
          if (n.source_paper && n.entity_type !== 'Paper') {{
              htmlContent += '<div class="info-group">';
              htmlContent += '<div class="info-group-title">Source Paper</div>';
              htmlContent += '<span class="info-tag" style="cursor:default;">' + n.source_paper + '</span>';
              htmlContent += '</div>';
          }}
          
          if (crossPapers.length > 0) {{
              htmlContent += '<div class="info-group">';
              htmlContent += '<div class="info-group-title">';
              htmlContent += '<div style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#4A90D9; margin-right:6px; box-shadow: 0 0 3px rgba(0,0,0,0.5); vertical-align:middle;"></div>';
              htmlContent += '<span style="vertical-align:middle;">Ditemukan di Paper (' + crossPapers.length + ')</span></div>';
              crossPapers.forEach(function(item) {{
                  var labelDisplay = item.node.label;
                  htmlContent += '<span class="info-tag conn-tag" data-id="' + item.node.id.replace(/"/g, '&quot;') + '">' + labelDisplay + '</span>';
              }});
              htmlContent += '</div>';
          }}
          
          for (var t in connectionsByType) {{
              var groupColor = connectionsByType[t][0].node.original_bg || connectionsByType[t][0].node.color.background || '#666';
              htmlContent += '<div class="info-group">';
              htmlContent += '<div class="info-group-title">';
              htmlContent += '<div style="display:inline-block; width:10px; height:10px; border-radius:50%; background:' + groupColor + '; margin-right:6px; box-shadow: 0 0 3px rgba(0,0,0,0.5); vertical-align:middle;"></div>';
              htmlContent += '<span style="vertical-align:middle;">Terkoneksi dengan ' + t + ' (' + connectionsByType[t].length + ')</span></div>';
              connectionsByType[t].forEach(function(item) {{
                  var labelDisplay = item.node.label;
                  htmlContent += '<span class="info-tag conn-tag" data-id="' + item.node.id.replace(/"/g, '&quot;') + '">' + labelDisplay + '</span>';
              }});
              htmlContent += '</div>';
          }}
          
          infoContent.innerHTML = htmlContent;
          
          // Bind event listener untuk navigasi antar node
          var connTags = infoPanel.getElementsByClassName('conn-tag');
          for (var k = 0; k < connTags.length; k++) {{
              connTags[k].addEventListener('click', function(e) {{
                  executeSearchSelection(this.getAttribute('data-id'));
              }});
          }}
          
          infoPanel.classList.add('open');
      }}
  }}

  searchInput.addEventListener('input', function(e) {{
      if (this.value) clearSearchBtn.style.display = 'block';
      else clearSearchBtn.style.display = 'none';
      renderSearchDropdown(this.value);
  }});
  
  clearSearchBtn.addEventListener('click', function(e) {{
      searchInput.value = '';
      this.style.display = 'none';
      searchDropdown.style.display = 'none';
      currentSearchNodeId = null;
      resetHighlight();
      document.getElementById('info-panel').classList.remove('open');
      
      // Kembalikan zoom ke awal jika dibatalkan
      network.fit({{ animation: {{ duration: 800, easingFunction: "easeInOutQuad" }} }});
  }});

  document.getElementById('close-info').addEventListener('click', function() {{
      document.getElementById('info-panel').classList.remove('open');
  }});

  // Global Legend Tooltip Logic
  var legendIcon = document.getElementById('legend-info-icon');
  var globalTooltip = document.getElementById('global-legend-tooltip');
  if (legendIcon && globalTooltip) {{
      legendIcon.addEventListener('mouseenter', function() {{
          var rect = this.getBoundingClientRect();
          globalTooltip.style.top = Math.max(16, rect.top - 20) + 'px';
          globalTooltip.style.right = (window.innerWidth - rect.left + 15) + 'px';
          globalTooltip.style.display = 'block';
      }});
      legendIcon.addEventListener('mouseleave', function() {{
          globalTooltip.style.display = 'none';
      }});
  }}

  // Edge Filter Logic
  var edgeSelect = document.getElementById('edge-type-select');
  if (edgeSelect) {{
      var edgeDescriptions = {{
          'written_by': '<b>[Paper ➔ Author]</b><br>Menunjukkan penulis dari sebuah paper.',
          'affiliated_with': '<b>[Author ➔ Institution]</b><br>Menunjukkan institusi tempat penulis bernaung.',
          'uses_method': '<b>[Paper ➔ Method]</b><br>Menunjukkan bahwa paper tersebut menggunakan metode atau algoritma ini.',
          'proposes_method': '<b>[Paper ➔ Method]</b><br>Menunjukkan bahwa paper tersebut menciptakan metode ini perdana.',
          'uses_dataset': '<b>[Paper ➔ Dataset]</b><br>Menunjukkan bahwa paper mengevaluasi modelnya di dataset ini.',
          'uses_metric': '<b>[Paper ➔ Metric]</b><br>Menunjukkan bahwa paper menggunakan metrik ini untuk tolak ukur.',
          'finds': '<b>[Paper ➔ Finding]</b><br>Menunjukkan hasil temuan, kesimpulan, atau klaim dari paper.',
          'has_limitation': '<b>[Method/Dataset ➔ Limitation]</b><br>Menunjukkan batasan atau kelemahan (kegagalan) yang diakui.',
          'criticizes': '<b>[Paper ➔ Method/Metric]</b><br>Menunjukkan paper memberikan kritik tajam atau menemukan kecacatan fatal pada entitas tersebut.',
          'builds_on': '<b>[Method ➔ Method]</b><br>Menunjukkan metode ini adalah perbaikan/pengembangan dari metode lain.',
          'compares': '<b>[Method/Paper ➔ Method]</b><br>Menunjukkan perbandingan performa atau efisiensi (A vs B).',
          'same_author': '<b>[Paper ➔ Paper]</b><br>Menunjukkan dua paper ini memiliki penulis yang sama (Cross-research).'
      }};
      
      edgeSelect.addEventListener('change', function(e) {{
          var selectedType = e.target.value;
          
          var descBox = document.getElementById('edge-filter-desc');
          if (descBox) {{
              if (selectedType === 'all') {{
                  descBox.style.display = 'none';
              }} else {{
                  descBox.innerHTML = edgeDescriptions[selectedType] || 'Menampilkan relasi ' + selectedType;
                  descBox.style.display = 'block';
              }}
          }}
          
          var allEdgesData = edges.get();
          var edgeUpdates = [];
          var activeNodes = new Set();
          
          for (var j = 0; j < allEdgesData.length; j++) {{
              var edge = allEdgesData[j];
              if (selectedType === 'all' || edge.rel_type === selectedType) {{
                  edgeUpdates.push({{id: edge.id, color: {{ opacity: 1.0 }}, hidden: false}});
                  if (selectedType !== 'all') {{
                      activeNodes.add(edge.from);
                      activeNodes.add(edge.to);
                  }}
              }} else {{
                  edgeUpdates.push({{id: edge.id, color: {{ opacity: 0.03 }}, hidden: false}});
              }}
          }}
          edges.update(edgeUpdates);

          var allNodesData = nodes.get();
          var nodeUpdates = [];
          for (var i = 0; i < allNodesData.length; i++) {{
              var node = allNodesData[i];
              if (!node.original_bg) node.original_bg = node.color ? node.color.background : '#888';
              if (!node.original_border) node.original_border = node.color ? node.color.border : '#666';

              if (selectedType === 'all' || activeNodes.has(node.id)) {{
                  nodeUpdates.push({{
                      id: node.id, 
                      color: {{ background: node.original_bg, border: node.original_border }},
                      font: {{ color: "#e0e0e0" }},
                      shadow: false
                  }});
              }} else {{
                  nodeUpdates.push({{
                      id: node.id, 
                      color: {{ 
                          background: hexToRgba(node.original_bg, 0.15), 
                          border: hexToRgba(node.original_border, 0.15) 
                      }},
                      font: {{ color: "rgba(224,224,224,0.15)" }},
                      shadow: false
                  }});
              }}
          }}
          nodes.update(nodeUpdates);
      }});
  }}

  document.addEventListener('click', function(e) {{
      var container = document.getElementById('search-container');
      if (container && !container.contains(e.target)) {{
          searchDropdown.style.display = 'none';
      }}
  }});
  
  searchInput.addEventListener('keypress', function(e) {{
      if (e.key === 'Enter') {{
          var items = searchDropdown.getElementsByClassName('search-item');
          if (items.length > 0) executeSearchSelection(items[0].getAttribute('data-id'));
      }}
  }});

  // --- Analytics Dashboard ---
  var analyticsGenerated = false;
  document.getElementById('details-insights').addEventListener('toggle', function(e) {{
      if (e.target.open && !analyticsGenerated) {{
          generateAnalytics();
          analyticsGenerated = true;
      }}
  }});
  var analyticsContent = document.getElementById('analytics-content');

  function generateAnalytics() {{
      var allNodes = nodes.get();
      var allEdges = edges.get();

      var degreeMap = {{}};
      for (var i = 0; i < allEdges.length; i++) {{
          var e = allEdges[i];
          degreeMap[e.from] = (degreeMap[e.from] || 0) + 1;
          degreeMap[e.to] = (degreeMap[e.to] || 0) + 1;
      }}
      
      var grouped = {{
          'Method': [],
          'Dataset': [],
          'Metric': [],
          'Author': []
      }};
      
      for (var i = 0; i < allNodes.length; i++) {{
          var n = allNodes[i];
          if (grouped[n.entity_type] !== undefined) {{
              grouped[n.entity_type].push({{
                  id: n.id,
                  label: n.label,
                  degree: degreeMap[n.id] || 0
              }});
          }}
      }}
      
      var html = '';
      var categories = ['Method', 'Dataset', 'Metric', 'Author'];
      var categoryColors = {{
          'Method': '#2ECC71',
          'Dataset': '#F39C12',
          'Metric': '#00BCD4',
          'Author': '#E74C3C'
      }};
      
      for (var c = 0; c < categories.length; c++) {{
          var cat = categories[c];
          var items = grouped[cat];
          items.sort(function(a, b) {{ return b.degree - a.degree; }});
          
          var topItems = items.slice(0, 5);
          if (topItems.length > 0) {{
              html += '<div class="analytics-category">';
              html += '<h4 style="color:' + categoryColors[cat] + ';">Top ' + cat + '</h4>';
              for (var j = 0; j < topItems.length; j++) {{
                  var item = topItems[j];
                  if (item.degree > 0) {{
                      html += '<div class="analytics-item" data-id="' + item.id.replace(/"/g, '&quot;') + '">';
                      html += '<span class="analytics-item-name" title="' + item.id + '">' + item.label + '</span>';
                      html += '<span class="analytics-item-score">⭐ ' + item.degree + '</span>';
                      html += '</div>';
                  }}
              }}
              html += '</div>';
          }}
      }}
      
      analyticsContent.innerHTML = html;
      
      var itemEls = analyticsContent.getElementsByClassName('analytics-item');
      for (var k = 0; k < itemEls.length; k++) {{
          itemEls[k].addEventListener('click', function() {{
              var nodeId = this.getAttribute('data-id');
              document.getElementById('details-insights').removeAttribute('open');
              executeSearchSelection(nodeId);
          }});
      }}
  }}

  
  var datalistsPopulated = false;
  document.getElementById('details-multihop').addEventListener('toggle', function(e) {{
      if (e.target.open && !datalistsPopulated) {{
          populateDatalists();
          datalistsPopulated = true;
      }}
  }});
  
  function populateDatalists() {{
      var mhNodeList = document.getElementById('mh-nodelist');
      if (!mhNodeList) return;
      if (mhNodeList.children.length > 0) return;
      var allNodes = nodes.get();
      var nodeOpts = '';
      for (var i = 0; i < allNodes.length; i++) {{
          var n = allNodes[i];
          nodeOpts += '<option value="' + n.id.replace(/"/g, '&quot;') + '">';
      }}
      mhNodeList.innerHTML = nodeOpts;
  }}
  

  
  // Dijkstra Shortest Path
  document.getElementById('mh-run-dijkstra').addEventListener('click', function() {{
      var startId = document.getElementById('mh-node-a').value;
      var endId = document.getElementById('mh-node-b').value;
      var resDiv = document.getElementById('mh-dijkstra-result');
      
      if (!startId || !endId) {{
          resDiv.innerHTML = '<span style="color:#E74C3C;">Pilih kedua node terlebih dahulu.</span>';
          return;
      }}
      if (!nodes.get(startId) || !nodes.get(endId)) {{
          resDiv.innerHTML = '<span style="color:#E74C3C;">Node tidak valid. Pastikan dari dropdown.</span>';
          return;
      }}
      
      var allEdges = edges.get();
      var adj = {{}};
      for (var i = 0; i < allEdges.length; i++) {{
          var e = allEdges[i];
          if (!adj[e.from]) adj[e.from] = [];
          if (!adj[e.to]) adj[e.to] = [];
          adj[e.from].push(e.to);
          adj[e.to].push(e.from);
      }}
      
      var queue = [startId];
      var visited = new Set([startId]);
      var parent = {{}};
      var found = false;
      
      while (queue.length > 0) {{
          var curr = queue.shift();
          if (curr === endId) {{
              found = true;
              break;
          }}
          var neighbors = adj[curr] || [];
          for (var i = 0; i < neighbors.length; i++) {{
              var n = neighbors[i];
              if (!visited.has(n)) {{
                  visited.add(n);
                  parent[n] = curr;
                  queue.push(n);
              }}
          }}
      }}
      
      if (!found) {{
          resDiv.innerHTML = '<span style="color:#F39C12;">Tidak ada jalur yang menghubungkan kedua node ini.</span>';
          return;
      }}
      
      var path = [];
      var trace = endId;
      while (trace) {{
          path.push(trace);
          trace = parent[trace];
      }}
      path.reverse();
      
      resDiv.innerHTML = '<span style="color:#2ECC71;">Jalur ditemukan! (' + (path.length - 1) + ' lompatan)</span>';
      highlightPathInGraph(path);
  }});
  

  
  function highlightPathInGraph(pathIds, highlightOnlyNodes = false) {{
      var pathSet = new Set(pathIds);
      var allNodes = nodes.get();
      var allEdges = edges.get();
      
      var nodeUpdates = [];
      for (var i = 0; i < allNodes.length; i++) {{
          var n = allNodes[i];
          if (!n.original_bg) n.original_bg = n.color.background;
          if (!n.original_border) n.original_border = n.color.border;
          
          if (pathSet.has(n.id)) {{
              nodeUpdates.push({{
                  id: n.id,
                  color: {{ background: n.original_bg, border: '#ffffff' }},
                  font: {{ color: '#ffffff' }},
                  shadow: {{enabled: true, color: '#ffffff', size: 20, x: 0, y: 0}}
              }});
          }} else {{
              nodeUpdates.push({{
                  id: n.id,
                  color: {{ background: hexToRgba(n.original_bg, 0.1), border: hexToRgba(n.original_border, 0.1) }},
                  font: {{ color: 'rgba(255,255,255,0.1)' }},
                  shadow: false
              }});
          }}
      }}
      nodes.update(nodeUpdates);
      
      var edgeUpdates = [];
      for (var i = 0; i < allEdges.length; i++) {{
          var e = allEdges[i];
          if (highlightOnlyNodes) {{
              if (pathSet.has(e.from) || pathSet.has(e.to)) {{
                  edgeUpdates.push({{id: e.id, color: {{ opacity: 0.8 }}, width: 2}});
              }} else {{
                  edgeUpdates.push({{id: e.id, color: {{ opacity: 0.05 }}, width: 1}});
              }}
          }} else {{
              var isPathEdge = false;
              for (var j = 0; j < pathIds.length - 1; j++) {{
                  if ((e.from === pathIds[j] && e.to === pathIds[j+1]) || (e.to === pathIds[j] && e.from === pathIds[j+1])) {{
                      isPathEdge = true;
                      break;
                  }}
              }}
              if (isPathEdge) {{
                  edgeUpdates.push({{id: e.id, color: {{ opacity: 1.0, color: '#ffffff' }}, width: 4}});
              }} else {{
                  edgeUpdates.push({{id: e.id, color: {{ opacity: 0.05 }}, width: 1}});
              }}
          }}
      }}
      edges.update(edgeUpdates);
      
      network.fit({{nodes: pathIds, animation: {{duration: 800}}}});
  }}

  // Handle double click on empty canvas to reset all filters
  if (typeof network !== 'undefined') {{
      network.on("doubleClick", function(params) {{
          if (params.nodes.length === 0 && params.edges.length === 0) {{
              // Reset Edge Filter
              var edgeSelect = document.getElementById('edge-type-select');
              if (edgeSelect && edgeSelect.value !== 'all') {{
                  edgeSelect.value = 'all';
                  var evt = document.createEvent("HTMLEvents");
                  evt.initEvent("change", false, true);
                  edgeSelect.dispatchEvent(evt);
              }}
              
              // Reset Search Node
              var clearBtn = document.getElementById('clear-search');
              if (clearBtn && clearBtn.style.display !== 'none') {{
                  clearBtn.click();
              }}
              
              // Reset Legend Highlight
              resetHighlight();
          }}
      }});
  }}

</script>
"""

    return html.replace("</body>", injected + "\n</body>")
