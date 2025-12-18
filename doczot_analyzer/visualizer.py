"""HTML visualizer for DocZot product surface graphs.

Generates interactive HTML visualizations using vis.js to display:
- Topic nodes (nouns, verbs, concepts)
- Coverage status (documented vs undocumented)
- Quality scores
- Relationships between topics
"""

import json
from pathlib import Path
from typing import Optional

from doczot_analyzer.manifest import TopicManifest, NodeType


HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>DocZot - {product_name} Product Surface</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
        }}
        .container {{
            display: flex;
            height: 100vh;
        }}
        #graph {{
            flex: 1;
            background: #16213e;
        }}
        .sidebar {{
            width: 350px;
            background: #0f3460;
            padding: 20px;
            overflow-y: auto;
            border-left: 2px solid #e94560;
        }}
        h1 {{
            font-size: 1.5rem;
            margin-bottom: 10px;
            color: #e94560;
        }}
        h2 {{
            font-size: 1.1rem;
            margin: 20px 0 10px 0;
            color: #e94560;
        }}
        .stats {{
            background: #1a1a2e;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .stat-row {{
            display: flex;
            justify-content: space-between;
            margin: 5px 0;
        }}
        .stat-label {{
            color: #888;
        }}
        .stat-value {{
            font-weight: bold;
        }}
        .coverage-bar {{
            height: 8px;
            background: #333;
            border-radius: 4px;
            margin-top: 10px;
            overflow: hidden;
        }}
        .coverage-fill {{
            height: 100%;
            background: linear-gradient(90deg, #e94560, #0f3460);
            transition: width 0.3s;
        }}
        .legend {{
            margin-top: 20px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 8px 0;
        }}
        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 50%;
            margin-right: 10px;
        }}
        .node-details {{
            background: #1a1a2e;
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
        }}
        .node-details h3 {{
            color: #e94560;
            margin-bottom: 10px;
        }}
        .detail-row {{
            margin: 5px 0;
            font-size: 0.9rem;
        }}
        .detail-label {{
            color: #888;
        }}
        .quality-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 5px;
            margin-top: 10px;
        }}
        .quality-item {{
            background: #0f3460;
            padding: 8px;
            border-radius: 4px;
            font-size: 0.8rem;
        }}
        .quality-yes {{ color: #4ade80; }}
        .quality-partial {{ color: #fbbf24; }}
        .quality-no {{ color: #f87171; }}
        .filter-section {{
            margin-top: 20px;
        }}
        .filter-btn {{
            background: #1a1a2e;
            border: 1px solid #e94560;
            color: #eee;
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            margin: 2px;
            font-size: 0.85rem;
        }}
        .filter-btn:hover {{
            background: #e94560;
        }}
        .filter-btn.active {{
            background: #e94560;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div id="graph"></div>
        <div class="sidebar">
            <h1>{product_name}</h1>

            <div class="stats">
                <div class="stat-row">
                    <span class="stat-label">Coverage</span>
                    <span class="stat-value">{coverage_percent:.1f}%</span>
                </div>
                <div class="coverage-bar">
                    <div class="coverage-fill" style="width: {coverage_percent}%"></div>
                </div>
                <div class="stat-row" style="margin-top: 15px">
                    <span class="stat-label">Documented</span>
                    <span class="stat-value">{documented}/{total_topics}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Undocumented</span>
                    <span class="stat-value">{undocumented}</span>
                </div>
            </div>

            <h2>By Type</h2>
            <div class="stats">
                <div class="stat-row">
                    <span class="stat-label">Verbs (actions)</span>
                    <span class="stat-value">{verb_count}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Nouns (entities)</span>
                    <span class="stat-value">{noun_count}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Concepts</span>
                    <span class="stat-value">{concept_count}</span>
                </div>
            </div>

            <div class="legend">
                <h2>Legend</h2>
                <div class="legend-item">
                    <div class="legend-color" style="background: #4ade80"></div>
                    <span>Documented</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #f87171"></div>
                    <span>Undocumented</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #60a5fa; border-radius: 4px"></div>
                    <span>Verb (action)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #c084fc"></div>
                    <span>Noun (entity)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #fbbf24; transform: rotate(45deg)"></div>
                    <span>Concept</span>
                </div>
            </div>

            <div class="filter-section">
                <h2>Filter</h2>
                <button class="filter-btn active" onclick="filterNodes('all')">All</button>
                <button class="filter-btn" onclick="filterNodes('verb')">Verbs</button>
                <button class="filter-btn" onclick="filterNodes('noun')">Nouns</button>
                <button class="filter-btn" onclick="filterNodes('documented')">Documented</button>
                <button class="filter-btn" onclick="filterNodes('undocumented')">Undocumented</button>
            </div>

            <div id="nodeDetails" class="node-details" style="display: none">
                <h3 id="detailName">-</h3>
                <div class="detail-row">
                    <span class="detail-label">Type:</span>
                    <span id="detailType">-</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Status:</span>
                    <span id="detailStatus">-</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Location:</span>
                    <span id="detailLocation">-</span>
                </div>
                <div id="qualitySection" style="display: none">
                    <h3 style="margin-top: 15px">Quality</h3>
                    <div class="quality-grid" id="qualityGrid"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Graph data
        const graphData = {graph_data_json};

        // Create nodes and edges for vis.js
        const nodes = new vis.DataSet(graphData.nodes.map(n => ({{
            id: n.id,
            label: n.name,
            title: `${{n.name}}\\n${{n.type}}\\n${{n.documented ? 'Documented' : 'Undocumented'}}`,
            shape: n.type === 'verb' ? 'box' : n.type === 'noun' ? 'ellipse' : 'diamond',
            color: {{
                background: n.documented ? '#4ade80' : '#f87171',
                border: n.type === 'verb' ? '#60a5fa' : n.type === 'noun' ? '#c084fc' : '#fbbf24',
                highlight: {{ background: '#e94560', border: '#fff' }}
            }},
            borderWidth: 3,
            font: {{ color: '#1a1a2e', size: 14 }},
            // Store original data for filtering
            nodeType: n.type,
            documented: n.documented,
            location: n.location,
            quality: n.quality
        }})));

        const edges = new vis.DataSet(graphData.edges.map(e => ({{
            from: e.source,
            to: e.target,
            label: e.relationship,
            arrows: 'to',
            color: {{ color: '#888', highlight: '#e94560' }},
            font: {{ color: '#888', size: 10 }}
        }})));

        // Network options
        const options = {{
            physics: {{
                stabilization: {{ iterations: 100 }},
                barnesHut: {{
                    gravitationalConstant: -2000,
                    springLength: 150,
                    springConstant: 0.04
                }}
            }},
            interaction: {{
                hover: true,
                tooltipDelay: 100
            }},
            layout: {{
                improvedLayout: true
            }}
        }};

        // Create network
        const container = document.getElementById('graph');
        const network = new vis.Network(container, {{ nodes, edges }}, options);

        // Store original nodes for filtering
        const originalNodes = graphData.nodes;

        // Node click handler
        network.on('click', function(params) {{
            if (params.nodes.length > 0) {{
                const nodeId = params.nodes[0];
                const node = originalNodes.find(n => n.id === nodeId);
                showNodeDetails(node);
            }} else {{
                document.getElementById('nodeDetails').style.display = 'none';
            }}
        }});

        function showNodeDetails(node) {{
            document.getElementById('nodeDetails').style.display = 'block';
            document.getElementById('detailName').textContent = node.name;
            document.getElementById('detailType').textContent = node.type;
            document.getElementById('detailStatus').textContent = node.documented ? 'Documented' : 'Undocumented';
            document.getElementById('detailStatus').className = node.documented ? 'quality-yes' : 'quality-no';
            document.getElementById('detailLocation').textContent = node.location || '-';

            if (node.quality) {{
                document.getElementById('qualitySection').style.display = 'block';
                const grid = document.getElementById('qualityGrid');
                grid.innerHTML = '';

                const tech = node.quality.technical || {{}};
                const sem = node.quality.semantic || {{}};

                const items = [
                    ['Params', tech.has_parameters_docs],
                    ['Returns', tech.has_return_docs],
                    ['Errors', tech.has_error_docs],
                    ['Warnings', tech.has_warnings ? 'yes' : 'no'],
                    ['Description', sem.has_description ? 'yes' : 'no'],
                    ['Use Cases', sem.has_use_cases ? 'yes' : 'no'],
                    ['Anti-patterns', sem.has_anti_patterns ? 'yes' : 'no'],
                    ['Context', sem.has_context ? 'yes' : 'no'],
                ];

                items.forEach(([label, value]) => {{
                    const div = document.createElement('div');
                    div.className = 'quality-item';
                    const cls = value === 'yes' ? 'quality-yes' : value === 'partial' ? 'quality-partial' : 'quality-no';
                    div.innerHTML = `${{label}}: <span class="${{cls}}">${{value || 'no'}}</span>`;
                    grid.appendChild(div);
                }});
            }} else {{
                document.getElementById('qualitySection').style.display = 'none';
            }}
        }}

        function filterNodes(filter) {{
            // Update button states
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');

            // Filter nodes
            const filtered = originalNodes.filter(n => {{
                if (filter === 'all') return true;
                if (filter === 'verb') return n.type === 'verb';
                if (filter === 'noun') return n.type === 'noun';
                if (filter === 'documented') return n.documented;
                if (filter === 'undocumented') return !n.documented;
                return true;
            }});

            const filteredIds = new Set(filtered.map(n => n.id));

            nodes.forEach(n => {{
                nodes.update({{
                    id: n.id,
                    hidden: !filteredIds.has(n.id)
                }});
            }});
        }}
    </script>
</body>
</html>
"""


def generate_visualization(
    manifest: TopicManifest,
    output_path: str | Path | None = None
) -> str:
    """Generate an interactive HTML visualization of the product surface.

    Args:
        manifest: The TopicManifest to visualize
        output_path: Optional path to write HTML file

    Returns:
        The generated HTML string
    """
    stats = manifest.coverage_stats()

    # Build graph data
    graph_nodes = []
    for node in manifest.nodes:
        coverage = manifest.get_coverage(node.id)
        node_data = {
            "id": node.id,
            "name": node.name,
            "type": node.type.value,
            "documented": coverage.is_documented,
            "location": node.source_location,
        }

        if coverage.is_documented:
            node_data["quality"] = {
                "technical": {
                    "has_parameters_docs": coverage.quality.technical.has_parameters_docs,
                    "has_return_docs": coverage.quality.technical.has_return_docs,
                    "has_error_docs": coverage.quality.technical.has_error_docs,
                    "has_warnings": coverage.quality.technical.has_warnings,
                },
                "semantic": {
                    "has_description": coverage.quality.semantic.has_description,
                    "has_use_cases": coverage.quality.semantic.has_use_cases,
                    "has_anti_patterns": coverage.quality.semantic.has_anti_patterns,
                    "has_context": coverage.quality.semantic.has_context,
                },
            }

        graph_nodes.append(node_data)

    graph_edges = [
        {
            "source": edge.source_id,
            "target": edge.target_id,
            "relationship": edge.relationship.value,
        }
        for edge in manifest.edges
    ]

    graph_data = {
        "nodes": graph_nodes,
        "edges": graph_edges,
    }

    # Generate HTML
    html = HTML_TEMPLATE.format(
        product_name=manifest.product_name,
        coverage_percent=stats.get("coverage_percentage", 0),
        documented=stats.get("documented", 0),
        total_topics=stats.get("total_topics", 0),
        undocumented=stats.get("undocumented", 0),
        verb_count=stats.get("by_type", {}).get("verb", 0),
        noun_count=stats.get("by_type", {}).get("noun", 0),
        concept_count=stats.get("by_type", {}).get("concept", 0),
        graph_data_json=json.dumps(graph_data),
    )

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html)

    return html
