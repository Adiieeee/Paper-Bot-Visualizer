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
          "gravitationalConstant": -500,
          "centralGravity": 0.005,
          "springLength": 300,
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

    stats_html = (
        f"{graph.number_of_nodes()} nodes &nbsp;•&nbsp; "
        f"{graph.number_of_edges()} edges"
    )

    injected = f"""
<style>
  body {{ margin: 0; overflow: hidden; }}
  #graph-ui {{
    position: fixed;
    top: 16px;
    right: 16px;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 10px;
    pointer-events: none;
  }}
  #legend-panel {{
    background: rgba(15,15,26,0.92);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 12px;
    padding: 18px 22px;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 14px;
    color: #e0e0e0;
    min-width: 200px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.6);
    pointer-events: all;
  }}
  #legend-panel h3 {{
    margin: 0 0 12px 0;
    font-size: 15px;
    font-weight: 700;
    color: #a0c4ff;
    letter-spacing: 0.5px;
    display: flex;
    align-items: center;
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
  .info-tooltip {{
    visibility: hidden;
    position: absolute;
    top: -10px;
    right: 120%;
    width: 250px;
    background: rgba(15,15,26,0.98);
    color: #ccc;
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 8px;
    padding: 12px;
    font-size: 12px;
    font-weight: normal;
    box-shadow: 0 4px 15px rgba(0,0,0,0.8);
    opacity: 0;
    transition: opacity 0.2s;
    pointer-events: none;
    z-index: 10000;
    line-height: 1.5;
    text-align: left;
  }}
  .info-icon:hover .info-tooltip {{
    visibility: visible;
    opacity: 1;
  }}
  .info-tooltip strong {{
    color: #a0c4ff;
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
</style>

<div id="search-container">
  <input type="text" id="search-input" placeholder="🔍 Search Node" autocomplete="off">
  <button id="clear-search" style="display: none;">&times;</button>
  <div id="search-dropdown"></div>
</div>

<div id="graph-ui">
  <div id="legend-panel">
    <h3>
      📊 Entity Types
      <div class="info-icon">?
        <div class="info-tooltip">
          <strong>Paper:</strong> Dokumen paper utama.<br>
          <strong>Author:</strong> Penulis paper.<br>
          <strong>Institution:</strong> Afiliasi tempat penulis bernaung.<br>
          <strong>Method:</strong> Algoritma, model arsitektur, teknik, atau pendekatan spesifik.<br>
          <strong>Dataset:</strong> Kumpulan data untuk melatih/menguji model.<br>
          <strong>Metric:</strong> Tolak ukur atau standar perhitungan untuk mengevaluasi.<br>
          <strong>Finding:</strong> Kesimpulan, hasil utama, atau penemuan.<br>
          <strong>Limitation:</strong> Kelemahan, batasan, atau kekurangan.
        </div>
      </div>
    </h3>
    {legend_items}
    <div id="hint">Hover untuk detail<br>Drag &amp; scroll to navigate</div>
  </div>
  <div id="stats-bar">{stats_html}</div>
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
          if (n.label && n.label.toLowerCase().includes(q)) {{
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
          var aLbl = a.label.toLowerCase();
          var bLbl = b.label.toLowerCase();
          if (aLbl === q && bLbl !== q) return -1;
          if (bLbl === q && aLbl !== q) return 1;
          if (aLbl.startsWith(q) && !bLbl.startsWith(q)) return -1;
          if (bLbl.startsWith(q) && !aLbl.startsWith(q)) return 1;
          return aLbl.localeCompare(bLbl);
      }});
      
      matches = matches.slice(0, 50); // Limit 50 results
      
      var html = '';
      for (var i = 0; i < matches.length; i++) {{
          html += '<div class="search-item" data-id="' + matches[i].id + '">' + 
                  '<span>' + matches[i].label + '</span>' + 
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
      
      searchInput.value = n.label;
      clearSearchBtn.style.display = 'block';
      currentSearchNodeId = nodeId;
      
      if (currentHighlightedType !== null) {{
          currentHighlightedType = null;
      }}
      
      var allNodesData = nodes.get();
      var allEdgesData = edges.get();
      var connectedNodeIds = new Set();
      
      for (var j = 0; j < allEdgesData.length; j++) {{
          var e = allEdgesData[j];
          if (e.from == nodeId) connectedNodeIds.add(e.to);
          if (e.to == nodeId) connectedNodeIds.add(e.from);
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
          }} else if (connectedNodeIds.has(node.id)) {{
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
          scale: 0.3,
          animation: {{ duration: 1000, easingFunction: "easeInOutQuad" }}
      }});
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
      
      // Kembalikan zoom ke awal jika dibatalkan
      network.fit({{ animation: {{ duration: 800, easingFunction: "easeInOutQuad" }} }});
  }});

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

</script>
"""

    return html.replace("</body>", injected + "\n</body>")
