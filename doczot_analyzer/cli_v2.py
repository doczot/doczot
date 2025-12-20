"""DocZot v2 CLI - Four Layer Documentation Analysis.

Commands:
    analyze     Run full analysis (surface, ITM, ATM, gaps)
    surface     Explore the product surface graph
    itm         View/edit the intended topic manifest
    atm         View the actual topic manifest
    gaps        View the gap report and sprint plan
    visualize   Interactive HTML visualization
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from doczot_analyzer.analyzer_v2 import (
    build_surface_graph,
    discover_atm,
    analyze_repository,
    print_analysis_summary,
)
from doczot_analyzer.models_v2 import (
    SurfaceGraph,
    TopicManifest,
    Topic,
    TopicType,
    ManifestType,
    GapReport,
    generate_default_itm,
    compute_gap_report,
)


# =============================================================================
# ANALYZE COMMAND
# =============================================================================

def cmd_analyze(args):
    """Run full analysis on a repository."""
    repo_path = args.repo_path or "."
    repo_path = str(Path(repo_path).resolve())

    print(f"Analyzing: {repo_path}")
    print()

    surface, itm, atm, gap_report = analyze_repository(repo_path, args.name)

    print_analysis_summary(surface, itm, atm, gap_report)

    # Save artifacts if requested
    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

        with open(output_dir / "surface.json", 'w') as f:
            json.dump(surface.model_dump(), f, indent=2, default=str)
        with open(output_dir / "itm.json", 'w') as f:
            json.dump(itm.model_dump(), f, indent=2, default=str)
        with open(output_dir / "atm.json", 'w') as f:
            json.dump(atm.model_dump(), f, indent=2, default=str)
        with open(output_dir / "gaps.json", 'w') as f:
            json.dump(gap_report.model_dump(), f, indent=2, default=str)

        print(f"\nArtifacts saved to: {output_dir}/")

    return 0


# =============================================================================
# SURFACE COMMAND
# =============================================================================

def cmd_surface(args):
    """Explore the product surface graph."""
    repo_path = args.repo_path or "."
    repo_path = str(Path(repo_path).resolve())

    print(f"Building surface graph for: {repo_path}")
    surface = build_surface_graph(repo_path, args.name)

    print(f"\n{'=' * 60}")
    print(f"SURFACE GRAPH: {surface.product_name}")
    print(f"{'=' * 60}")

    # Show nodes by type
    if args.type == "all" or args.type == "verbs":
        print(f"\n--- Verbs ({len(surface.verbs)}) ---")
        for node in surface.verbs[:20]:  # Limit display
            noun = surface.noun_for_verb(node.id)
            noun_info = f" -> {noun.name}" if noun else " (orphan)"
            print(f"  {node.name:<30} {node.code_signature or ''}{noun_info}")
        if len(surface.verbs) > 20:
            print(f"  ... and {len(surface.verbs) - 20} more")

    if args.type == "all" or args.type == "nouns":
        print(f"\n--- Nouns ({len(surface.nouns)}) ---")
        for node in surface.nouns:
            verbs = surface.verbs_for_noun(node.id)
            print(f"  {node.name:<20} ({len(verbs)} verbs)")

    if args.type == "all" or args.type == "concepts":
        print(f"\n--- Concepts ({len(surface.concepts)}) ---")
        for node in surface.concepts:
            print(f"  {node.name}")

    # Show orphans
    orphans = surface.orphan_verbs()
    if orphans and (args.type == "all" or args.type == "orphans"):
        print(f"\n--- Orphan Verbs ({len(orphans)}) ---")
        print("  (These endpoints aren't connected to any entity)")
        for node in orphans[:10]:
            print(f"  {node.name:<30} {node.code_signature or ''}")
        if len(orphans) > 10:
            print(f"  ... and {len(orphans) - 10} more")

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(surface.model_dump(), f, indent=2, default=str)
        print(f"\nSaved to: {args.output}")

    return 0


# =============================================================================
# ITM COMMAND
# =============================================================================

def cmd_itm(args):
    """View or manage the intended topic manifest."""
    repo_path = args.repo_path or "."
    repo_path = str(Path(repo_path).resolve())

    # Build surface first
    surface = build_surface_graph(repo_path, args.name)

    # Load or generate ITM
    if args.load:
        with open(args.load) as f:
            itm = TopicManifest.model_validate(json.load(f))
        print(f"Loaded ITM from: {args.load}")
    else:
        itm = generate_default_itm(surface)
        print("Generated default ITM from surface")

    print(f"\n{'=' * 60}")
    print(f"INTENDED TOPIC MANIFEST: {itm.product_name}")
    print(f"{'=' * 60}")
    print(f"Topics: {len(itm.topics)}")

    # Group by type
    by_type: dict[str, list[Topic]] = {}
    for topic in itm.topics:
        key = topic.topic_type.value
        if key not in by_type:
            by_type[key] = []
        by_type[key].append(topic)

    for topic_type, topics in by_type.items():
        print(f"\n--- {topic_type.title()} Topics ({len(topics)}) ---")
        for topic in topics:
            cover_count = len(topic.covers)
            print(f"  [{topic.id}] {topic.name:<25} (covers {cover_count} elements)")

    # Check for uncovered surface elements
    uncovered = itm.uncovered_surface_ids(surface)
    if uncovered:
        print(f"\n--- Uncovered Surface Elements ({len(uncovered)}) ---")
        for node_id in uncovered[:10]:
            node = surface.get_node(node_id)
            if node:
                print(f"  {node.name} ({node.type.value})")
        if len(uncovered) > 10:
            print(f"  ... and {len(uncovered) - 10} more")

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(itm.model_dump(), f, indent=2, default=str)
        print(f"\nSaved to: {args.output}")

    return 0


# =============================================================================
# ATM COMMAND
# =============================================================================

def cmd_atm(args):
    """View the actual topic manifest (discovered from docs)."""
    repo_path = args.repo_path or "."
    repo_path = str(Path(repo_path).resolve())

    print(f"Discovering documentation in: {repo_path}")

    # Build surface
    surface = build_surface_graph(repo_path, args.name)

    # Discover ATM
    atm = discover_atm(repo_path, surface)

    print(f"\n{'=' * 60}")
    print(f"ACTUAL TOPIC MANIFEST: {atm.product_name}")
    print(f"{'=' * 60}")
    print(f"Topics discovered: {len(atm.topics)}")

    covered = atm.covered_surface_ids()
    total = len(surface.user_facing_nodes())
    print(f"Surface coverage: {len(covered)}/{total} elements")

    print(f"\n--- Discovered Topics ---")
    for topic in atm.topics:
        quality = atm.quality.get(topic.id)
        score = f"{quality.coverage_score:.0%}" if quality else "N/A"
        print(f"  {topic.name:<30} [{score}] (covers {len(topic.covers)} elements)")
        if topic.source_file:
            print(f"    Source: {topic.source_file}")

    # Show what's not covered
    uncovered = [n for n in surface.user_facing_nodes() if n.id not in covered]
    if uncovered:
        print(f"\n--- Undocumented Surface Elements ({len(uncovered)}) ---")
        for node in uncovered[:10]:
            print(f"  {node.name} ({node.type.value})")
        if len(uncovered) > 10:
            print(f"  ... and {len(uncovered) - 10} more")

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(atm.model_dump(), f, indent=2, default=str)
        print(f"\nSaved to: {args.output}")

    return 0


# =============================================================================
# GAPS COMMAND
# =============================================================================

def cmd_gaps(args):
    """View the gap report between ITM and ATM."""
    repo_path = args.repo_path or "."
    repo_path = str(Path(repo_path).resolve())

    print(f"Analyzing gaps in: {repo_path}")

    surface, itm, atm, gap_report = analyze_repository(repo_path, args.name)

    print(f"\n{'=' * 60}")
    print(f"GAP REPORT: {gap_report.product_name}")
    print(f"{'=' * 60}")

    stats = gap_report.coverage_stats()
    print(f"\nCoverage: {stats['coverage_percentage']:.1f}%")
    print(f"  Complete: {stats['complete']}")
    print(f"  Partial: {stats['partial']}")
    print(f"  Missing: {stats['missing']}")

    if gap_report.extra_topics:
        print(f"\n--- Extra Topics (in docs but not in ITM) ---")
        print("  These might indicate undocumented features or outdated docs:")
        for topic_id in gap_report.extra_topics:
            topic = atm.get_topic(topic_id)
            if topic:
                print(f"  - {topic.name} ({topic.source_file})")

    print(f"\n--- Sprint Plan ---")
    plan = gap_report.sprint_plan()
    if not plan:
        print("  No gaps to address!")
    else:
        for item in plan:
            status_icon = "!" if item['status'] == 'missing' else "~"
            print(f"  [{status_icon}] {item['topic']}")
            print(f"      Action: {item['action']}")
            if item['quality_gaps']:
                print(f"      Quality: {', '.join(item['quality_gaps'])}")

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(gap_report.model_dump(), f, indent=2, default=str)
        print(f"\nSaved to: {args.output}")

    return 0


# =============================================================================
# VISUALIZE COMMAND
# =============================================================================

def cmd_visualize(args):
    """Generate interactive HTML visualization."""
    import webbrowser

    repo_path = args.repo_path or "."
    repo_path = str(Path(repo_path).resolve())

    print(f"Analyzing: {repo_path}")
    surface, itm, atm, gap_report = analyze_repository(repo_path, args.name)

    # Generate HTML
    html = generate_visualization_html(surface, itm, atm, gap_report)

    output_path = Path(args.output)
    output_path.write_text(html)
    print(f"Visualization saved to: {output_path}")

    if args.open:
        webbrowser.open(f"file://{output_path.resolve()}")
        print("Opened in browser")

    return 0


def generate_visualization_html(
    surface: SurfaceGraph,
    itm: TopicManifest,
    atm: TopicManifest,
    gap_report: GapReport,
) -> str:
    """Generate interactive HTML visualization."""

    # Build graph data
    nodes_data = []
    for node in surface.nodes:
        # Find which ITM topics cover this node
        itm_topics = itm.topics_covering(node.id)
        atm_topics = atm.topics_covering(node.id)

        nodes_data.append({
            "id": node.id,
            "name": node.name,
            "type": node.type.value,
            "signature": node.code_signature,
            "source": f"{node.source_file}:{node.source_line}" if node.source_file else None,
            "itm_topics": [t.name for t in itm_topics],
            "atm_topics": [t.name for t in atm_topics],
            "is_covered": node.id in atm.covered_surface_ids(),
        })

    edges_data = [
        {
            "source": e.source_id,
            "target": e.target_id,
            "type": e.edge_type.value,
        }
        for e in surface.edges
    ]

    itm_topics_data = [
        {
            "id": t.id,
            "name": t.name,
            "type": t.topic_type.value,
            "covers": t.covers,
            "auto_generated": t.auto_generated,
        }
        for t in itm.topics
    ]

    atm_topics_data = [
        {
            "id": t.id,
            "name": t.name,
            "type": t.topic_type.value,
            "covers": t.covers,
            "source_file": t.source_file,
            "quality": atm.quality.get(t.id, {}).model_dump() if t.id in atm.quality else None,
        }
        for t in atm.topics
    ]

    gaps_data = [
        {
            "topic": g.itm_topic_name,
            "status": g.status,
            "action": g.action,
            "missing": g.missing_surface_ids,
            "quality_gaps": g.quality_gaps,
        }
        for g in gap_report.gaps
    ]

    stats = gap_report.coverage_stats()

    graph_data = {
        "product_name": surface.product_name,
        "surface": {"nodes": nodes_data, "edges": edges_data},
        "itm": itm_topics_data,
        "atm": atm_topics_data,
        "gaps": gaps_data,
        "stats": stats,
        "extra_topics": gap_report.extra_topics,
    }

    return HTML_TEMPLATE.format(
        product_name=surface.product_name,
        coverage_percent=stats.get('coverage_percentage', 0),
        complete=stats.get('complete', 0),
        partial=stats.get('partial', 0),
        missing=stats.get('missing', 0),
        extra=stats.get('extra', 0),
        total_surface=len(surface.nodes),
        total_verbs=len(surface.verbs),
        total_nouns=len(surface.nouns),
        total_itm=len(itm.topics),
        total_atm=len(atm.topics),
        graph_data_json=json.dumps(graph_data),
    )


HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>DocZot - {product_name}</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; }}
        .container {{ display: flex; height: 100vh; }}
        #graph {{ flex: 1; background: #1e293b; }}
        .sidebar {{ width: 400px; background: #1e293b; border-left: 2px solid #3b82f6; overflow-y: auto; }}
        .panel {{ padding: 20px; border-bottom: 1px solid #334155; }}
        h1 {{ font-size: 1.4rem; color: #3b82f6; margin-bottom: 15px; }}
        h2 {{ font-size: 1.1rem; color: #60a5fa; margin: 15px 0 10px 0; }}
        h3 {{ font-size: 0.95rem; color: #93c5fd; margin: 10px 0 5px 0; }}
        .stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
        .stat {{ background: #334155; padding: 12px; border-radius: 8px; }}
        .stat-value {{ font-size: 1.5rem; font-weight: bold; color: #3b82f6; }}
        .stat-label {{ font-size: 0.8rem; color: #94a3b8; }}
        .coverage-bar {{ height: 8px; background: #334155; border-radius: 4px; margin-top: 10px; }}
        .coverage-fill {{ height: 100%; border-radius: 4px; background: linear-gradient(90deg, #ef4444, #f59e0b, #22c55e); }}
        .tabs {{ display: flex; border-bottom: 1px solid #334155; }}
        .tab {{ flex: 1; padding: 12px; text-align: center; cursor: pointer; color: #94a3b8; }}
        .tab:hover {{ background: #334155; }}
        .tab.active {{ color: #3b82f6; border-bottom: 2px solid #3b82f6; }}
        .tab-content {{ display: none; padding: 15px; }}
        .tab-content.active {{ display: block; }}
        .topic-item {{ background: #334155; padding: 10px; border-radius: 6px; margin: 8px 0; }}
        .topic-name {{ font-weight: 500; }}
        .topic-meta {{ font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }}
        .gap-item {{ padding: 10px; border-left: 3px solid; margin: 8px 0; background: #334155; }}
        .gap-missing {{ border-color: #ef4444; }}
        .gap-partial {{ border-color: #f59e0b; }}
        .gap-complete {{ border-color: #22c55e; }}
        .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; }}
        .badge-missing {{ background: #ef4444; }}
        .badge-partial {{ background: #f59e0b; color: #000; }}
        .badge-complete {{ background: #22c55e; color: #000; }}
        .badge-extra {{ background: #8b5cf6; }}
        .legend {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 15px; }}
        .legend-item {{ display: flex; align-items: center; font-size: 0.85rem; }}
        .legend-color {{ width: 16px; height: 16px; border-radius: 4px; margin-right: 6px; }}
        #details {{ display: none; }}
        #details.visible {{ display: block; }}
        .detail-row {{ margin: 5px 0; }}
        .detail-label {{ color: #94a3b8; }}
    </style>
</head>
<body>
    <div class="container">
        <div id="graph"></div>
        <div class="sidebar">
            <div class="panel">
                <h1>{product_name}</h1>
                <div class="stats">
                    <div class="stat">
                        <div class="stat-value">{coverage_percent:.0f}%</div>
                        <div class="stat-label">Coverage</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{total_surface}</div>
                        <div class="stat-label">Surface Elements</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{total_itm}</div>
                        <div class="stat-label">ITM Topics</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{total_atm}</div>
                        <div class="stat-label">ATM Topics</div>
                    </div>
                </div>
                <div class="coverage-bar">
                    <div class="coverage-fill" style="width: {coverage_percent}%"></div>
                </div>
            </div>

            <div class="tabs">
                <div class="tab active" onclick="showTab('surface')">Surface</div>
                <div class="tab" onclick="showTab('itm')">ITM</div>
                <div class="tab" onclick="showTab('atm')">ATM</div>
                <div class="tab" onclick="showTab('gaps')">Gaps</div>
            </div>

            <div id="tab-surface" class="tab-content active">
                <div class="legend">
                    <div class="legend-item"><div class="legend-color" style="background:#22c55e"></div>Covered</div>
                    <div class="legend-item"><div class="legend-color" style="background:#ef4444"></div>Uncovered</div>
                    <div class="legend-item"><div class="legend-color" style="background:#3b82f6;border-radius:2px"></div>Verb</div>
                    <div class="legend-item"><div class="legend-color" style="background:#8b5cf6;border-radius:50%"></div>Noun</div>
                </div>
                <div id="details">
                    <h3 id="detail-name">-</h3>
                    <div class="detail-row"><span class="detail-label">Type:</span> <span id="detail-type">-</span></div>
                    <div class="detail-row"><span class="detail-label">Signature:</span> <span id="detail-sig">-</span></div>
                    <div class="detail-row"><span class="detail-label">Source:</span> <span id="detail-source">-</span></div>
                    <div class="detail-row"><span class="detail-label">ITM Topics:</span> <span id="detail-itm">-</span></div>
                    <div class="detail-row"><span class="detail-label">ATM Topics:</span> <span id="detail-atm">-</span></div>
                </div>
            </div>

            <div id="tab-itm" class="tab-content">
                <h3>Intended Topics</h3>
                <div id="itm-list"></div>
            </div>

            <div id="tab-atm" class="tab-content">
                <h3>Actual Topics (from docs)</h3>
                <div id="atm-list"></div>
            </div>

            <div id="tab-gaps" class="tab-content">
                <h3>Sprint Plan</h3>
                <div class="stats" style="margin-bottom:15px">
                    <div class="stat"><div class="stat-value" style="color:#22c55e">{complete}</div><div class="stat-label">Complete</div></div>
                    <div class="stat"><div class="stat-value" style="color:#f59e0b">{partial}</div><div class="stat-label">Partial</div></div>
                    <div class="stat"><div class="stat-value" style="color:#ef4444">{missing}</div><div class="stat-label">Missing</div></div>
                    <div class="stat"><div class="stat-value" style="color:#8b5cf6">{extra}</div><div class="stat-label">Extra</div></div>
                </div>
                <div id="gaps-list"></div>
            </div>
        </div>
    </div>

    <script>
        const data = {graph_data_json};

        // Build vis.js nodes
        const visNodes = new vis.DataSet(data.surface.nodes.map(n => ({{
            id: n.id,
            label: n.name,
            shape: n.type === 'verb' ? 'box' : n.type === 'noun' ? 'ellipse' : 'diamond',
            color: {{
                background: n.is_covered ? '#22c55e' : '#ef4444',
                border: n.type === 'verb' ? '#3b82f6' : '#8b5cf6',
            }},
            borderWidth: 2,
            font: {{ color: '#1e293b', size: 12 }},
            data: n,
        }})));

        const visEdges = new vis.DataSet(data.surface.edges.map(e => ({{
            from: e.source,
            to: e.target,
            arrows: 'to',
            color: {{ color: '#475569' }},
        }})));

        const network = new vis.Network(
            document.getElementById('graph'),
            {{ nodes: visNodes, edges: visEdges }},
            {{
                physics: {{ barnesHut: {{ gravitationalConstant: -2000, springLength: 120 }} }},
                interaction: {{ hover: true }},
            }}
        );

        network.on('click', params => {{
            if (params.nodes.length) {{
                const node = data.surface.nodes.find(n => n.id === params.nodes[0]);
                showDetails(node);
            }}
        }});

        function showDetails(node) {{
            document.getElementById('details').classList.add('visible');
            document.getElementById('detail-name').textContent = node.name;
            document.getElementById('detail-type').textContent = node.type;
            document.getElementById('detail-sig').textContent = node.signature || '-';
            document.getElementById('detail-source').textContent = node.source || '-';
            document.getElementById('detail-itm').textContent = node.itm_topics.join(', ') || 'None';
            document.getElementById('detail-atm').textContent = node.atm_topics.join(', ') || 'None';
        }}

        function showTab(name) {{
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tab-' + name).classList.add('active');
        }}

        // Populate ITM list
        const itmList = document.getElementById('itm-list');
        data.itm.forEach(t => {{
            itmList.innerHTML += `
                <div class="topic-item">
                    <div class="topic-name">${{t.name}}</div>
                    <div class="topic-meta">${{t.type}} · covers ${{t.covers.length}} elements</div>
                </div>
            `;
        }});

        // Populate ATM list
        const atmList = document.getElementById('atm-list');
        data.atm.forEach(t => {{
            const score = t.quality ? Math.round(t.quality.coverage_score * 100) + '%' : 'N/A';
            atmList.innerHTML += `
                <div class="topic-item">
                    <div class="topic-name">${{t.name}} <span class="badge">${{score}}</span></div>
                    <div class="topic-meta">${{t.source_file || 'Unknown source'}}</div>
                </div>
            `;
        }});

        // Populate gaps list
        const gapsList = document.getElementById('gaps-list');
        data.gaps.filter(g => g.status !== 'complete').forEach(g => {{
            gapsList.innerHTML += `
                <div class="gap-item gap-${{g.status}}">
                    <div class="topic-name">${{g.topic}} <span class="badge badge-${{g.status}}">${{g.status}}</span></div>
                    <div class="topic-meta">${{g.action}}</div>
                </div>
            `;
        }});

        if (data.extra_topics.length) {{
            gapsList.innerHTML += '<h3 style="margin-top:20px">Extra Topics (not in ITM)</h3>';
            data.extra_topics.forEach(id => {{
                const topic = data.atm.find(t => t.id === id);
                if (topic) {{
                    gapsList.innerHTML += `
                        <div class="gap-item" style="border-color:#8b5cf6">
                            <div class="topic-name">${{topic.name}} <span class="badge badge-extra">extra</span></div>
                            <div class="topic-meta">${{topic.source_file}}</div>
                        </div>
                    `;
                }}
            }});
        }}
    </script>
</body>
</html>
"""


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="doczot",
        description="Documentation coverage analysis with ITM/ATM model",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 2.0.0")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # analyze
    p = subparsers.add_parser("analyze", help="Run full analysis")
    p.add_argument("repo_path", nargs="?", default=".")
    p.add_argument("--name", help="Product name")
    p.add_argument("--output", "-o", help="Output directory for artifacts")
    p.set_defaults(func=cmd_analyze)

    # surface
    p = subparsers.add_parser("surface", help="Explore product surface")
    p.add_argument("repo_path", nargs="?", default=".")
    p.add_argument("--name", help="Product name")
    p.add_argument("--type", choices=["all", "verbs", "nouns", "concepts", "orphans"], default="all")
    p.add_argument("--output", "-o", help="Save to JSON")
    p.set_defaults(func=cmd_surface)

    # itm
    p = subparsers.add_parser("itm", help="View intended topic manifest")
    p.add_argument("repo_path", nargs="?", default=".")
    p.add_argument("--name", help="Product name")
    p.add_argument("--load", help="Load ITM from JSON file")
    p.add_argument("--output", "-o", help="Save to JSON")
    p.set_defaults(func=cmd_itm)

    # atm
    p = subparsers.add_parser("atm", help="View actual topic manifest")
    p.add_argument("repo_path", nargs="?", default=".")
    p.add_argument("--name", help="Product name")
    p.add_argument("--output", "-o", help="Save to JSON")
    p.set_defaults(func=cmd_atm)

    # gaps
    p = subparsers.add_parser("gaps", help="View gap report")
    p.add_argument("repo_path", nargs="?", default=".")
    p.add_argument("--name", help="Product name")
    p.add_argument("--output", "-o", help="Save to JSON")
    p.set_defaults(func=cmd_gaps)

    # visualize
    p = subparsers.add_parser("visualize", help="Interactive visualization")
    p.add_argument("repo_path", nargs="?", default=".")
    p.add_argument("--name", help="Product name")
    p.add_argument("--output", "-o", default="doczot-viz.html")
    p.add_argument("--open", action="store_true", help="Open in browser")
    p.set_defaults(func=cmd_visualize)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
