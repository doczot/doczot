"""DocZot v2 CLI - Four Layer Documentation Analysis.

Commands:
    analyze          Run full analysis (surface, ITM, ATM, gaps)
    surface          Explore the product surface graph
    itm              View/edit the intended topic manifest
    atm              View the actual topic manifest
    gaps             View the gap report and sprint plan
    visualize        Interactive HTML visualization
    diff             Compare two Surface Graph scans
    export-ontology  Export to RDF/OWL ontology formats
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
    diff_surface_graphs,
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
from doczot_analyzer.storage import ManifestStore


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

    # v3: Persist Surface Graph to database (always, for diff capability)
    db_path = args.db_path or ".doczot/manifests.db"
    store = ManifestStore(db_path)
    scan_id = store.save_surface_graph(surface)
    print(f"\nSurface graph saved to database: {scan_id}")

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

        print(f"Artifacts saved to: {output_dir}/")

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

    # Build edge lookup for finding which verbs reference each noun
    noun_to_verbs: dict[str, list[str]] = {}
    for edge in surface.edges:
        if edge.target_id.startswith("noun:"):
            if edge.target_id not in noun_to_verbs:
                noun_to_verbs[edge.target_id] = []
            # Find the verb name
            verb_node = next((n for n in surface.nodes if n.id == edge.source_id), None)
            if verb_node:
                noun_to_verbs[edge.target_id].append(verb_node.name)

    # Build graph data
    nodes_data = []
    for node in surface.nodes:
        # Find which ITM topics cover this node
        itm_topics = itm.topics_covering(node.id)
        atm_topics = atm.topics_covering(node.id)

        # For nouns, show which verbs reference them
        if node.type.value == "noun":
            referencing_verbs = noun_to_verbs.get(node.id, [])
            signature = f"Referenced by {len(referencing_verbs)} endpoints"
            source = ", ".join(referencing_verbs[:5])
            if len(referencing_verbs) > 5:
                source += f" (+{len(referencing_verbs) - 5} more)"
        else:
            signature = node.code_signature
            source = f"{node.source_file}:{node.source_line}" if node.source_file else None

        nodes_data.append({
            "id": node.id,
            "name": node.name,
            "type": node.type.value,
            "signature": signature,
            "source": source,
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
            "parent_id": t.parent_id,
            "children": t.children,
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
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; }}
        .container {{ display: flex; height: 100vh; width: 100vw; }}
        #graph {{ flex: 1; min-width: 400px; height: 100vh; background: #1e293b; position: relative; overflow: hidden; }}
        #graph svg {{ width: 100%; height: 100%; }}
        .graph-hint {{ position: fixed; bottom: 15px; left: 15px; font-size: 0.8rem; color: #e2e8f0; background: rgba(30, 41, 59, 0.9); padding: 8px 14px; border-radius: 6px; border: 1px solid #334155; pointer-events: none; z-index: 1000; }}
        .node {{ cursor: pointer; }}
        .node rect, .node ellipse {{ stroke-width: 3; }}
        .node text {{ font-size: 12px; font-weight: 500; pointer-events: none; }}
        .node:hover rect, .node:hover ellipse {{ stroke: #fbbf24; stroke-width: 4; }}
        .edge {{ stroke: #64748b; stroke-width: 2; fill: none; }}
        .edge-arrow {{ fill: #64748b; }}
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
        .surface-item {{ background: #334155; padding: 8px 10px; border-radius: 6px; margin: 6px 0; border-left: 3px solid; cursor: pointer; }}
        .surface-item:hover {{ background: #3b4a5e; }}
        .surface-item.verb {{ border-color: #3b82f6; }}
        .surface-item.noun {{ border-color: #8b5cf6; }}
        .surface-item.covered {{ opacity: 1; }}
        .surface-item.uncovered {{ opacity: 0.7; }}
        .surface-item .name {{ font-weight: 600; font-size: 0.9rem; }}
        .surface-item .signature {{ font-family: monospace; font-size: 0.75rem; color: #94a3b8; margin-top: 2px; }}
        .surface-item .source {{ font-size: 0.7rem; color: #64748b; margin-top: 2px; }}
        .surface-item .coverage-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }}
        .surface-item .coverage-dot.covered {{ background: #22c55e; }}
        .surface-item .coverage-dot.uncovered {{ background: #ef4444; }}
    </style>
</head>
<body>
    <div id="tooltip" style="display:none; position:fixed; background:#1e293b; border:1px solid #3b82f6; padding:8px 12px; border-radius:6px; font-size:12px; z-index:1000; pointer-events:none; max-width:300px;">
        <div id="tooltip-name" style="font-weight:600; color:#e2e8f0;"></div>
        <div id="tooltip-sig" style="color:#94a3b8; font-family:monospace; font-size:11px; margin-top:4px;"></div>
    </div>
    <div class="graph-hint">Scroll to zoom · Shift+drag to pan · Hover for details</div>
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
                    <div class="detail-row"><span class="detail-label" id="sig-label">Signature:</span> <span id="detail-sig">-</span></div>
                    <div class="detail-row"><span class="detail-label" id="source-label">Source:</span> <span id="detail-source">-</span></div>
                    <div class="detail-row"><span class="detail-label">ITM Topics:</span> <span id="detail-itm">-</span></div>
                    <div class="detail-row"><span class="detail-label">ATM Topics:</span> <span id="detail-atm">-</span></div>
                </div>
                <h3 style="margin-top:20px">Nouns ({total_nouns})</h3>
                <div id="noun-list"></div>
                <h3 style="margin-top:15px">Verbs ({total_verbs})</h3>
                <div id="verb-list"></div>
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

        // Simple force-directed layout (no external dependencies)
        function initGraph() {{
            const container = document.getElementById('graph');
            const width = container.clientWidth;
            const height = container.clientHeight;

            // Create SVG
            const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            svg.setAttribute('width', width);
            svg.setAttribute('height', height);
            svg.setAttribute('viewBox', `0 0 ${{width}} ${{height}}`);
            container.innerHTML = '';
            container.appendChild(svg);

            // Initialize node positions in a circle
            const nodes = data.surface.nodes;
            const edges = data.surface.edges;
            const nodeMap = {{}};

            const centerX = width / 2;
            const centerY = height / 2;
            const radius = Math.min(width, height) * 0.35;

            nodes.forEach((n, i) => {{
                const angle = (2 * Math.PI * i) / nodes.length;
                n.x = centerX + radius * Math.cos(angle);
                n.y = centerY + radius * Math.sin(angle);
                n.vx = 0;
                n.vy = 0;
                nodeMap[n.id] = n;
            }});

            // Create edge elements
            const edgeGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            svg.appendChild(edgeGroup);

            edges.forEach(e => {{
                const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                line.setAttribute('class', 'edge');
                line.setAttribute('stroke', '#64748b');
                line.setAttribute('stroke-width', '2');
                line.dataset.from = e.source;
                line.dataset.to = e.target;
                edgeGroup.appendChild(line);
            }});

            // Create node elements
            const nodeGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            svg.appendChild(nodeGroup);

            // Smart label truncation: keep start and end, ellipsis in middle
            function truncateLabel(name, maxLen = 18) {{
                if (name.length <= maxLen) return name;
                const keep = Math.floor((maxLen - 2) / 2);
                return name.slice(0, keep) + '..' + name.slice(-keep);
            }}

            nodes.forEach(n => {{
                const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                g.setAttribute('class', 'node');
                g.dataset.id = n.id;
                g.style.cursor = 'pointer';

                const bgColor = n.is_covered ? '#22c55e' : '#ef4444';
                const borderColor = n.type === 'verb' ? '#3b82f6' : '#8b5cf6';

                // Calculate width based on truncated text (max 18 chars)
                const displayName = truncateLabel(n.name);
                const textWidth = displayName.length * 7 + 20;
                const nodeWidth = Math.max(80, Math.min(160, textWidth));  // Cap at 160px
                const nodeHeight = 32;

                if (n.type === 'noun') {{
                    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'ellipse');
                    circle.setAttribute('rx', String(nodeWidth / 2));
                    circle.setAttribute('ry', String(nodeHeight / 2 + 4));
                    circle.setAttribute('fill', bgColor);
                    circle.setAttribute('stroke', borderColor);
                    circle.setAttribute('stroke-width', '3');
                    g.appendChild(circle);
                }} else {{
                    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                    rect.setAttribute('width', String(nodeWidth));
                    rect.setAttribute('height', String(nodeHeight));
                    rect.setAttribute('x', String(-nodeWidth / 2));
                    rect.setAttribute('y', String(-nodeHeight / 2));
                    rect.setAttribute('rx', '5');
                    rect.setAttribute('fill', bgColor);
                    rect.setAttribute('stroke', borderColor);
                    rect.setAttribute('stroke-width', '3');
                    g.appendChild(rect);
                }}

                const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                text.setAttribute('text-anchor', 'middle');
                text.setAttribute('dy', '4');
                text.setAttribute('fill', '#1e293b');
                text.setAttribute('font-size', '11');
                text.setAttribute('font-weight', '600');
                text.textContent = displayName;  // Show truncated name
                g.appendChild(text);

                // Hover tooltip
                g.addEventListener('mouseenter', e => {{
                    const tooltip = document.getElementById('tooltip');
                    document.getElementById('tooltip-name').textContent = n.name;
                    document.getElementById('tooltip-sig').textContent = n.signature || '';
                    tooltip.style.display = 'block';
                    tooltip.style.left = (e.clientX + 15) + 'px';
                    tooltip.style.top = (e.clientY + 15) + 'px';
                }});
                g.addEventListener('mousemove', e => {{
                    const tooltip = document.getElementById('tooltip');
                    tooltip.style.left = (e.clientX + 15) + 'px';
                    tooltip.style.top = (e.clientY + 15) + 'px';
                }});
                g.addEventListener('mouseleave', () => {{
                    document.getElementById('tooltip').style.display = 'none';
                }});

                g.addEventListener('click', () => showDetails(n));
                nodeGroup.appendChild(g);
                n.element = g;
                n.nodeWidth = nodeWidth;  // Store for collision detection
            }});

            // Zoom and pan state
            let scale = 1;
            let translateX = 0;
            let translateY = 0;
            const graphGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            graphGroup.setAttribute('id', 'graph-transform');
            svg.appendChild(graphGroup);
            graphGroup.appendChild(edgeGroup);
            graphGroup.appendChild(nodeGroup);

            function updateTransform() {{
                graphGroup.setAttribute('transform', `translate(${{translateX}}, ${{translateY}}) scale(${{scale}})`);
            }}

            // Mouse wheel zoom
            svg.addEventListener('wheel', e => {{
                e.preventDefault();
                const delta = e.deltaY > 0 ? 0.9 : 1.1;
                const newScale = Math.max(0.3, Math.min(3, scale * delta));
                // Zoom toward mouse position
                const rect = svg.getBoundingClientRect();
                const mx = e.clientX - rect.left;
                const my = e.clientY - rect.top;
                translateX = mx - (mx - translateX) * (newScale / scale);
                translateY = my - (my - translateY) * (newScale / scale);
                scale = newScale;
                updateTransform();
            }});

            // Pan with middle mouse or shift+drag
            let panning = false;
            let panStart = {{x: 0, y: 0}};
            svg.addEventListener('mousedown', e => {{
                if (e.button === 1 || (e.button === 0 && e.shiftKey)) {{
                    panning = true;
                    panStart = {{x: e.clientX - translateX, y: e.clientY - translateY}};
                    e.preventDefault();
                }}
            }});
            svg.addEventListener('mousemove', e => {{
                if (panning) {{
                    translateX = e.clientX - panStart.x;
                    translateY = e.clientY - panStart.y;
                    updateTransform();
                }}
            }});
            svg.addEventListener('mouseup', () => {{ panning = false; }});
            svg.addEventListener('mouseleave', () => {{ panning = false; }});

            // Simple force simulation
            function simulate() {{
                // Repulsion between nodes (much stronger for clusters)
                for (let i = 0; i < nodes.length; i++) {{
                    for (let j = i + 1; j < nodes.length; j++) {{
                        const dx = nodes[j].x - nodes[i].x;
                        const dy = nodes[j].y - nodes[i].y;
                        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                        // Stronger repulsion, especially when close
                        const minDist = (nodes[i].nodeWidth + nodes[j].nodeWidth) / 2 + 30;
                        const force = dist < minDist ? 15000 / (dist * dist) : 8000 / (dist * dist);
                        const fx = (dx / dist) * force;
                        const fy = (dy / dist) * force;
                        nodes[i].vx -= fx;
                        nodes[i].vy -= fy;
                        nodes[j].vx += fx;
                        nodes[j].vy += fy;
                    }}
                }}

                // Attraction along edges
                edges.forEach(e => {{
                    const source = nodeMap[e.source];
                    const target = nodeMap[e.target];
                    if (source && target) {{
                        const dx = target.x - source.x;
                        const dy = target.y - source.y;
                        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                        const force = dist * 0.01;
                        const fx = (dx / dist) * force;
                        const fy = (dy / dist) * force;
                        source.vx += fx;
                        source.vy += fy;
                        target.vx -= fx;
                        target.vy -= fy;
                    }}
                }});

                // Center gravity
                nodes.forEach(n => {{
                    n.vx += (centerX - n.x) * 0.001;
                    n.vy += (centerY - n.y) * 0.001;
                }});

                // Apply velocity with damping
                nodes.forEach(n => {{
                    n.vx *= 0.9;
                    n.vy *= 0.9;
                    n.x += n.vx;
                    n.y += n.vy;
                    // Keep in bounds (account for node width)
                    const halfWidth = (n.nodeWidth || 80) / 2 + 10;
                    n.x = Math.max(halfWidth, Math.min(width - halfWidth, n.x));
                    n.y = Math.max(25, Math.min(height - 25, n.y));
                }});

                // Update positions
                nodes.forEach(n => {{
                    n.element.setAttribute('transform', `translate(${{n.x}}, ${{n.y}})`);
                }});

                edgeGroup.querySelectorAll('line').forEach(line => {{
                    const source = nodeMap[line.dataset.from];
                    const target = nodeMap[line.dataset.to];
                    if (source && target) {{
                        line.setAttribute('x1', source.x);
                        line.setAttribute('y1', source.y);
                        line.setAttribute('x2', target.x);
                        line.setAttribute('y2', target.y);
                    }}
                }});
            }}

            // Run simulation
            let iterations = 0;
            function tick() {{
                simulate();
                iterations++;
                if (iterations < 200) {{
                    requestAnimationFrame(tick);
                }}
            }}
            tick();

            // Enable dragging
            let dragging = null;
            svg.addEventListener('mousedown', e => {{
                const node = e.target.closest('.node');
                if (node) {{
                    dragging = nodeMap[node.dataset.id];
                }}
            }});
            svg.addEventListener('mousemove', e => {{
                if (dragging) {{
                    const rect = svg.getBoundingClientRect();
                    dragging.x = e.clientX - rect.left;
                    dragging.y = e.clientY - rect.top;
                    dragging.vx = 0;
                    dragging.vy = 0;
                    simulate();
                }}
            }});
            svg.addEventListener('mouseup', () => {{ dragging = null; }});
            svg.addEventListener('mouseleave', () => {{ dragging = null; }});
        }}

        window.addEventListener('load', initGraph);
        window.addEventListener('resize', initGraph);

        function showDetails(node) {{
            document.getElementById('details').classList.add('visible');
            document.getElementById('detail-name').textContent = node.name;
            document.getElementById('detail-type').textContent = node.type;

            // Update labels based on node type
            if (node.type === 'noun') {{
                document.getElementById('sig-label').textContent = 'Usage:';
                document.getElementById('source-label').textContent = 'Endpoints:';
            }} else {{
                document.getElementById('sig-label').textContent = 'Signature:';
                document.getElementById('source-label').textContent = 'Source:';
            }}

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

        // Highlight surface nodes covered by a topic
        function highlightCoverage(covers, highlight) {{
            document.querySelectorAll('.node').forEach(node => {{
                const nodeId = node.dataset.id;
                const shape = node.querySelector('rect, ellipse');
                if (covers.includes(nodeId)) {{
                    if (highlight) {{
                        shape.setAttribute('stroke', '#fbbf24');
                        shape.setAttribute('stroke-width', '5');
                        node.style.opacity = '1';
                    }} else {{
                        // Restore original
                        const n = data.surface.nodes.find(n => n.id === nodeId);
                        const borderColor = n && n.type === 'verb' ? '#3b82f6' : '#8b5cf6';
                        shape.setAttribute('stroke', borderColor);
                        shape.setAttribute('stroke-width', '3');
                        node.style.opacity = '1';
                    }}
                }} else if (highlight) {{
                    node.style.opacity = '0.3';
                }}
            }});
        }}

        // Get all covers including children's covers
        function getAllCovers(topicId) {{
            const topic = data.itm.find(t => t.id === topicId);
            if (!topic) return [];
            let covers = [...(topic.covers || [])];
            (topic.children || []).forEach(childId => {{
                covers = covers.concat(getAllCovers(childId));
            }});
            return covers;
        }}

        // Build hierarchical ITM list
        function buildItmTree(parentId, indent) {{
            const children = data.itm.filter(t => t.parent_id === parentId);
            let html = '';
            children.forEach(t => {{
                const allCovers = getAllCovers(t.id);
                const hasChildren = data.itm.some(c => c.parent_id === t.id);
                const icon = hasChildren ? '▸ ' : '';
                html += `
                    <div class="topic-item" style="margin-left: ${{indent * 16}}px; cursor: pointer;"
                         data-topic-id="${{t.id}}"
                         onmouseenter="highlightCoverage(getAllCovers('${{t.id}}'), true)"
                         onmouseleave="highlightCoverage([], false)">
                        <div class="topic-name">${{icon}}${{t.name}}</div>
                        <div class="topic-meta">${{t.type}} · ${{allCovers.length}} elements</div>
                    </div>
                `;
                html += buildItmTree(t.id, indent + 1);
            }});
            return html;
        }}

        const itmList = document.getElementById('itm-list');
        itmList.innerHTML = buildItmTree(null, 0);

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

        // Populate surface lists (nouns and verbs)
        const nounList = document.getElementById('noun-list');
        const verbList = document.getElementById('verb-list');

        data.surface.nodes.filter(n => n.type === 'noun').forEach(n => {{
            const coveredClass = n.is_covered ? 'covered' : 'uncovered';
            nounList.innerHTML += `
                <div class="surface-item noun ${{coveredClass}}" onclick="highlightNode('${{n.id}}')">
                    <div class="name"><span class="coverage-dot ${{coveredClass}}"></span>${{n.name}}</div>
                </div>
            `;
        }});

        data.surface.nodes.filter(n => n.type === 'verb').forEach(n => {{
            const coveredClass = n.is_covered ? 'covered' : 'uncovered';
            verbList.innerHTML += `
                <div class="surface-item verb ${{coveredClass}}" onclick="highlightNode('${{n.id}}')">
                    <div class="name"><span class="coverage-dot ${{coveredClass}}"></span>${{n.name}}</div>
                    <div class="signature">${{n.signature || ''}}</div>
                    <div class="source">${{n.source || 'Unknown'}}</div>
                </div>
            `;
        }});

        // Highlight node in graph when clicking list item
        function highlightNode(nodeId) {{
            const nodeEl = document.querySelector(`.node[data-id="${{nodeId}}"]`);
            if (nodeEl) {{
                // Flash effect
                const shape = nodeEl.querySelector('rect, ellipse');
                const origStroke = shape.getAttribute('stroke');
                shape.setAttribute('stroke', '#fbbf24');
                shape.setAttribute('stroke-width', '5');
                setTimeout(() => {{
                    shape.setAttribute('stroke', origStroke);
                    shape.setAttribute('stroke-width', '3');
                }}, 1500);

                // Show details
                const node = data.surface.nodes.find(n => n.id === nodeId);
                if (node) showDetails(node);
            }}
        }}
    </script>
</body>
</html>
"""


# =============================================================================
# DIFF COMMAND
# =============================================================================

def cmd_diff(args):
    """Compare two Surface Graph scans and report changes."""
    db_path = args.db_path or ".doczot/manifests.db"
    store = ManifestStore(db_path)

    # Get product name (required)
    if not args.product:
        print("Error: --product is required for diff command")
        return 1

    # Load scans
    try:
        old_scan = store.load_surface_graph(args.product, args.old_scan)
        new_scan = store.load_surface_graph(args.product, args.new_scan)
    except Exception as e:
        print(f"Error loading scans: {e}")
        return 1

    if not old_scan or not new_scan:
        print("Error: Could not load one or both scans")
        print(f"Product: {args.product}")
        print(f"Old scan: {args.old_scan or 'previous'}")
        print(f"New scan: {args.new_scan or 'latest'}")

        # List available scans
        scans = store.list_scans(args.product)
        if scans:
            print(f"\nAvailable scans for {args.product}:")
            for scan in scans:
                print(f"  - {scan['id']} ({scan['scanned_at']})")
        else:
            print(f"\nNo scans found for product: {args.product}")

        return 1

    # Compute diff
    diff = diff_surface_graphs(old_scan, new_scan)

    # Print report
    print(f"\n{'='*60}")
    print(f"ONTOLOGY DIFF: {args.product}")
    print(f"{'='*60}")
    print(f"\nOld scan: {args.old_scan or 'previous'}")
    print(f"New scan: {args.new_scan or 'latest'}")

    print(f"\n--- Summary ---")
    print(f"Nodes added:   {diff['summary']['total_nodes_added']}")
    print(f"Nodes removed: {diff['summary']['total_nodes_removed']}")
    print(f"Edges added:   {diff['summary']['total_edges_added']}")
    print(f"Edges removed: {diff['summary']['total_edges_removed']}")

    if diff['summary'].get('nodes_added_by_type'):
        print(f"\n--- New Nodes by Type ---")
        for node_type, count in diff['summary']['nodes_added_by_type'].items():
            print(f"  {node_type:<15} +{count}")

    if diff['summary'].get('nodes_removed_by_type'):
        print(f"\n--- Removed Nodes by Type ---")
        for node_type, count in diff['summary']['nodes_removed_by_type'].items():
            print(f"  {node_type:<15} -{count}")

    # Show details if requested
    if args.verbose:
        if diff['nodes_added']:
            print(f"\n--- Nodes Added ({len(diff['nodes_added'])}) ---")
            for node_id in diff['nodes_added'][:20]:
                node = new_scan.get_node(node_id)
                if node:
                    print(f"  + {node.type.value:<12} {node.name}")
            if len(diff['nodes_added']) > 20:
                print(f"  ... and {len(diff['nodes_added']) - 20} more")

        if diff['nodes_removed']:
            print(f"\n--- Nodes Removed ({len(diff['nodes_removed'])}) ---")
            for node_id in diff['nodes_removed'][:20]:
                node = old_scan.get_node(node_id)
                if node:
                    print(f"  - {node.type.value:<12} {node.name}")
            if len(diff['nodes_removed']) > 20:
                print(f"  ... and {len(diff['nodes_removed']) - 20} more")

        if diff['edges_added']:
            print(f"\n--- Edges Added ({len(diff['edges_added'])}) ---")
            for source, target, edge_type in diff['edges_added'][:10]:
                print(f"  + {edge_type}: {source} -> {target}")
            if len(diff['edges_added']) > 10:
                print(f"  ... and {len(diff['edges_added']) - 10} more")

    # Save to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(diff, f, indent=2, default=str)
        print(f"\nDiff saved to: {args.output}")

    return 0


# =============================================================================
# EXPORT-ONTOLOGY COMMAND
# =============================================================================

def cmd_export_ontology(args):
    """Export surface graph and manifests to RDF/OWL ontology."""
    try:
        from doczot_analyzer.ontology import (
            full_analysis_to_ontology,
            surface_graph_to_ontology,
        )
    except ImportError:
        print("Error: Ontology export requires rdflib.")
        print("Install with: pip install 'doczot-analyzer[ontology]'")
        print("Or: pip install rdflib")
        return 1

    repo_path = args.repo_path or "."
    repo_path = str(Path(repo_path).resolve())

    print(f"Analyzing: {repo_path}")
    surface, itm, atm, gap_report = analyze_repository(repo_path, args.name)

    # Convert to ontology
    if args.surface_only:
        print("Converting surface graph to ontology...")
        onto = surface_graph_to_ontology(surface, include_schema=not args.no_schema)
    else:
        print("Converting full analysis (surface + ITM + ATM) to ontology...")
        onto = full_analysis_to_ontology(surface, itm, atm)

    # Run reasoning if requested
    if args.reason:
        print("Running inference...")
        if args.full_reason:
            result = onto.run_reasoner()
            if result['errors']:
                for err in result['errors']:
                    print(f"  Warning: {err}")
            else:
                print(f"  Inferred {result['inferred_triples']} new triples")
        else:
            inferred = onto.infer_transitive_closure()
            print(f"  Inferred {inferred} transitive/inverse triples")

    # Validate if requested
    if args.validate:
        print("Validating ontology...")
        validation = onto.validate_consistency()
        if validation['valid']:
            print("  Ontology is valid")
        else:
            print(f"  Found {validation['issue_count']} issues:")
            for issue in validation['issues'][:10]:
                print(f"    - {issue['message']}")
            if validation['issue_count'] > 10:
                print(f"    ... and {validation['issue_count'] - 10} more")

    # Show statistics
    if args.stats:
        stats = onto.get_statistics()
        print(f"\n--- Ontology Statistics ---")
        print(f"  Total triples: {stats['total_triples']}")
        print(f"  Verbs: {stats['verbs']}")
        print(f"  Nouns: {stats['nouns']}")
        print(f"  Concepts: {stats['concepts']}")
        print(f"  Constraints: {stats['constraints']}")
        print(f"  Topics: {stats['topics']}")
        print(f"  Relationships:")
        for rel_type, count in stats['relationships'].items():
            if count > 0:
                print(f"    {rel_type}: {count}")

    # Determine format
    format_map = {
        'turtle': 'turtle',
        'ttl': 'turtle',
        'json-ld': 'json-ld',
        'jsonld': 'json-ld',
        'xml': 'xml',
        'rdf': 'xml',
        'ntriples': 'nt',
        'nt': 'nt',
        'n3': 'n3',
    }
    output_format = format_map.get(args.format.lower(), 'turtle')

    # Serialize
    output = onto.serialize(output_format)

    # Write to file or stdout
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output)
        print(f"\nOntology saved to: {output_path}")
    else:
        print(f"\n--- Ontology ({output_format}) ---\n")
        # Limit output for large ontologies
        lines = output.split('\n')
        if len(lines) > 100 and not args.full:
            print('\n'.join(lines[:100]))
            print(f"\n... ({len(lines) - 100} more lines, use --full to show all or -o to save to file)")
        else:
            print(output)

    return 0


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
    p.add_argument("--db-path", default=".doczot/manifests.db", help="Database path")
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

    # diff
    p = subparsers.add_parser("diff", help="Compare two Surface Graph scans")
    p.add_argument("--product", required=True, help="Product name")
    p.add_argument("--old-scan", help="Old scan ID (default: previous)")
    p.add_argument("--new-scan", help="New scan ID (default: latest)")
    p.add_argument("--db-path", default=".doczot/manifests.db", help="Database path")
    p.add_argument("--verbose", "-v", action="store_true", help="Show detailed changes")
    p.add_argument("--output", "-o", help="Save diff to JSON file")
    p.set_defaults(func=cmd_diff)

    # export-ontology
    p = subparsers.add_parser("export-ontology", help="Export to RDF/OWL ontology")
    p.add_argument("repo_path", nargs="?", default=".")
    p.add_argument("--name", help="Product name")
    p.add_argument("--format", "-f", default="turtle",
                   choices=["turtle", "ttl", "json-ld", "jsonld", "xml", "rdf", "ntriples", "nt", "n3"],
                   help="Output format (default: turtle)")
    p.add_argument("--output", "-o", help="Save to file (otherwise prints to stdout)")
    p.add_argument("--surface-only", action="store_true",
                   help="Export only surface graph (not ITM/ATM)")
    p.add_argument("--no-schema", action="store_true",
                   help="Omit ontology schema (T-Box), only export instances")
    p.add_argument("--reason", action="store_true",
                   help="Run inference (transitive closure)")
    p.add_argument("--full-reason", action="store_true",
                   help="Run full OWL reasoning (requires owlready2 + Java)")
    p.add_argument("--validate", action="store_true",
                   help="Validate ontology consistency")
    p.add_argument("--stats", action="store_true",
                   help="Show ontology statistics")
    p.add_argument("--full", action="store_true",
                   help="Show full output (don't truncate)")
    p.set_defaults(func=cmd_export_ontology)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
