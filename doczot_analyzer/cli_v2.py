"""DocZot v2 CLI - Four Layer Documentation Analysis.

Commands:
    analyze          Run full analysis (graph, checklist, inventory, drift)
    surface          Explore the System Graph (code structure)
    itm              View/edit the Coverage Checklist
    atm              View the Content Inventory
    gaps             View the Drift Report and sprint plan
    visualize        Interactive HTML visualization
    diff             Compare two System Graph scans
    export           Export for AI agents (MCP, llms.txt, JSON-LD)
    export-ontology  Export to RDF/OWL ontology formats
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from doczot_analyzer.analyzer_v2 import (
    build_system_graph,
    discover_content_inventory,
    analyze_repository,
    print_analysis_summary,
    diff_system_graphs,
    # Backward compatibility aliases
    build_surface_graph,
    discover_atm,
    diff_surface_graphs,
)
from doczot_analyzer.models_v2 import (
    SystemGraph,
    TopicManifest,
    Topic,
    TopicType,
    ManifestType,
    DriftReport,
    MatchEvidence,
    generate_default_itm,
    compute_drift_report,
    # Backward compatibility aliases
    SurfaceGraph,
    GapReport,
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

    # v3: Persist System Graph to database (always, for diff capability)
    db_path = args.db_path or ".doczot/manifests.db"
    store = ManifestStore(db_path)
    scan_id = store.save_system_graph(surface)
    print(f"\nSystem graph saved to database: {scan_id}")

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
    """Explore the System Graph (code structure)."""
    repo_path = args.repo_path or "."
    repo_path = str(Path(repo_path).resolve())

    print(f"Building system graph for: {repo_path}")
    surface = build_system_graph(repo_path, args.name)

    print(f"\n{'=' * 60}")
    print(f"SYSTEM GRAPH: {surface.product_name}")
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

    # Build system graph first
    surface = build_system_graph(repo_path, args.name)

    # Load or generate ITM
    if args.load:
        with open(args.load) as f:
            itm = TopicManifest.model_validate(json.load(f))
        print(f"Loaded ITM from: {args.load}")
    else:
        itm = generate_default_itm(surface)
        print("Generated default Coverage Checklist from system graph")

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

    # Check for uncovered graph elements
    uncovered = itm.uncovered_surface_ids(surface)
    if uncovered:
        print(f"\n--- Uncovered Graph Elements ({len(uncovered)}) ---")
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

    # Build system graph
    surface = build_system_graph(repo_path, args.name)

    # Discover Content Inventory
    atm = discover_content_inventory(repo_path, surface)

    print(f"\n{'=' * 60}")
    print(f"ACTUAL TOPIC MANIFEST: {atm.product_name}")
    print(f"{'=' * 60}")
    print(f"Topics discovered: {len(atm.topics)}")

    covered = atm.covered_surface_ids()
    total = len(surface.user_facing_nodes())
    print(f"Documentation coverage: {len(covered)}/{total} elements")

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
        print(f"\n--- Undocumented Graph Elements ({len(uncovered)}) ---")
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
            if item['quality_issues']:
                print(f"      Quality: {', '.join(item['quality_issues'])}")

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


# =============================================================================
# SERVE COMMAND
# =============================================================================

def cmd_serve(args):
    """Launch interactive dashboard for documentation analysis."""
    try:
        import uvicorn
    except ImportError:
        print("Dashboard requires extra dependencies. Install with:")
        print("  pip install doczot-analyzer[dashboard]")
        return 1

    from doczot_analyzer.dashboard import create_app

    repo_path = args.repo_path or "."
    repo_path = str(Path(repo_path).resolve())
    db_path = args.db_path or ".doczot/manifests.db"

    app = create_app(db_path=db_path)

    print(f"DocZot Dashboard")
    print(f"  Repository: {repo_path}")
    print(f"  Database:   {db_path}")
    print(f"  URL:        http://{args.host}:{args.port}")
    print()

    if args.open:
        import webbrowser
        import threading
        threading.Timer(1.5, lambda: webbrowser.open(f"http://{args.host}:{args.port}")).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
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

    # Build evidence lookup: node_id -> list of evidence records
    evidence_by_node: dict[str, list[dict]] = {}
    for topic in atm.topics:
        for ev in topic.match_evidence:
            if ev.node_id not in evidence_by_node:
                evidence_by_node[ev.node_id] = []
            evidence_by_node[ev.node_id].append({
                "topic_name": topic.name,
                "topic_id": topic.id,
                "strategy": ev.strategy,
                "confidence": ev.confidence,
                "doc_file": ev.doc_file,
                "doc_section": ev.doc_section,
                "doc_snippet": ev.doc_snippet,
                "match_detail": ev.match_detail,
            })

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
            "match_evidence": evidence_by_node.get(node.id, []),
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
            "match_evidence": [
                {
                    "node_id": ev.node_id,
                    "strategy": ev.strategy,
                    "confidence": ev.confidence,
                    "doc_file": ev.doc_file,
                    "doc_section": ev.doc_section,
                    "doc_snippet": ev.doc_snippet,
                    "match_detail": ev.match_detail,
                }
                for ev in t.match_evidence
            ],
        }
        for t in atm.topics
    ]

    # Build evidence lookup for drift items: find evidence for covered nodes
    # by matching inventory topics to drift items via inventory_topic_id
    drift_evidence: dict[str, list[dict]] = {}
    for item in gap_report.drift_items:
        if item.inventory_topic_id:
            inv_topic = atm.get_topic(item.inventory_topic_id)
            if inv_topic:
                drift_evidence[item.matrix_topic_id] = [
                    {
                        "node_id": ev.node_id,
                        "strategy": ev.strategy,
                        "confidence": ev.confidence,
                        "doc_file": ev.doc_file,
                        "doc_section": ev.doc_section,
                        "doc_snippet": ev.doc_snippet,
                        "match_detail": ev.match_detail,
                    }
                    for ev in inv_topic.match_evidence
                ]

    gaps_data = [
        {
            "topic": g.matrix_topic_name,
            "topic_id": g.matrix_topic_id,
            "status": g.status,
            "action": g.action,
            "missing": g.missing_node_ids,
            "quality_gaps": g.quality_issues,
            "evidence": drift_evidence.get(g.matrix_topic_id, []),
        }
        for g in gap_report.drift_items
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
        .evidence-card {{ background: #1e293b; border: 1px solid #475569; border-radius: 8px; padding: 12px; margin: 8px 0; }}
        .evidence-card.direct {{ border-left: 3px solid #22c55e; }}
        .evidence-card.semantic {{ border-left: 3px solid #f59e0b; }}
        .evidence-card .ev-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }}
        .evidence-card .ev-strategy {{ font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }}
        .evidence-card .ev-strategy.direct {{ color: #22c55e; }}
        .evidence-card .ev-strategy.semantic {{ color: #f59e0b; }}
        .evidence-card .ev-confidence {{ font-size: 0.75rem; color: #94a3b8; }}
        .evidence-card .ev-doc {{ font-size: 0.8rem; color: #60a5fa; margin-bottom: 4px; }}
        .evidence-card .ev-snippet {{ font-size: 0.75rem; color: #cbd5e1; background: #0f172a; padding: 8px; border-radius: 4px; font-family: monospace; white-space: pre-wrap; word-break: break-word; max-height: 80px; overflow-y: auto; }}
        .evidence-card .ev-detail {{ font-size: 0.7rem; color: #64748b; margin-top: 4px; }}
        .evidence-card .ev-actions {{ display: flex; gap: 8px; margin-top: 8px; }}
        .evidence-card .ev-actions button {{ font-size: 0.7rem; padding: 2px 10px; border-radius: 4px; border: 1px solid #475569; background: transparent; color: #94a3b8; cursor: pointer; }}
        .evidence-card .ev-actions button:hover {{ background: #334155; }}
        .evidence-card .ev-actions .btn-accept:hover {{ border-color: #22c55e; color: #22c55e; }}
        .evidence-card .ev-actions .btn-reject:hover {{ border-color: #ef4444; color: #ef4444; }}
        .no-evidence {{ color: #64748b; font-size: 0.85rem; font-style: italic; padding: 10px 0; }}
        .drift-evidence {{ margin-top: 6px; }}
        .drift-evidence-toggle {{ font-size: 0.75rem; color: #60a5fa; cursor: pointer; background: none; border: none; padding: 0; }}
        .drift-evidence-toggle:hover {{ text-decoration: underline; }}
        .drift-evidence-body {{ display: none; margin-top: 6px; }}
        .drift-evidence-body.open {{ display: block; }}

        /* Review overlay */
        #review-overlay {{ position: fixed; inset: 0; z-index: 2000; background: #0f172a; display: none; flex-direction: column; }}
        #review-overlay.active {{ display: flex; }}
        .review-header {{ display: flex; align-items: center; gap: 16px; padding: 12px 20px; background: #1e293b; border-bottom: 1px solid #334155; flex-shrink: 0; }}
        .review-header h2 {{ font-size: 1.1rem; color: #3b82f6; white-space: nowrap; }}
        .review-progress {{ font-size: 0.85rem; color: #94a3b8; white-space: nowrap; }}
        .review-nav {{ display: flex; gap: 6px; }}
        .review-nav button {{ padding: 4px 12px; border-radius: 4px; border: 1px solid #475569; background: #334155; color: #e2e8f0; cursor: pointer; font-size: 0.8rem; }}
        .review-nav button:hover {{ background: #475569; }}
        .review-header-actions {{ margin-left: auto; display: flex; gap: 8px; }}
        .review-header-actions button {{ padding: 4px 12px; border-radius: 4px; border: 1px solid #475569; background: transparent; color: #94a3b8; cursor: pointer; font-size: 0.8rem; }}
        .review-header-actions button:hover {{ background: #334155; color: #e2e8f0; }}
        .review-body {{ display: flex; flex: 1; overflow: hidden; }}
        .review-left {{ width: 320px; padding: 20px; overflow-y: auto; background: #1e293b; border-right: 1px solid #334155; flex-shrink: 0; }}
        .review-left h3 {{ font-size: 1.2rem; color: #e2e8f0; margin-bottom: 12px; word-break: break-word; }}
        .review-left .rl-type {{ display: inline-block; padding: 2px 10px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; margin-bottom: 10px; }}
        .review-left .rl-type.verb {{ background: #3b82f6; color: #fff; }}
        .review-left .rl-type.noun {{ background: #8b5cf6; color: #fff; }}
        .review-left .rl-type.concept {{ background: #f59e0b; color: #000; }}
        .review-left .rl-type.constraint {{ background: #ef4444; color: #fff; }}
        .review-left .rl-meta {{ margin: 8px 0; font-size: 0.85rem; color: #94a3b8; }}
        .review-left .rl-meta strong {{ color: #cbd5e1; }}
        .review-left .rl-coverage {{ display: inline-block; padding: 4px 12px; border-radius: 4px; font-size: 0.8rem; font-weight: 600; margin-top: 8px; }}
        .review-left .rl-coverage.documented {{ background: rgba(34,197,94,0.2); color: #22c55e; border: 1px solid #22c55e; }}
        .review-left .rl-coverage.undocumented {{ background: rgba(239,68,68,0.2); color: #ef4444; border: 1px solid #ef4444; }}
        .review-left .rl-topics {{ margin-top: 12px; font-size: 0.8rem; }}
        .review-left .rl-topics div {{ margin: 4px 0; color: #94a3b8; }}
        .review-left .rl-topics span {{ color: #cbd5e1; }}
        .review-main {{ flex: 1; padding: 20px; overflow-y: auto; }}
        .review-main .rev-card {{ background: #1e293b; border: 1px solid #475569; border-radius: 10px; padding: 16px; margin-bottom: 14px; }}
        .review-main .rev-card.direct {{ border-left: 4px solid #22c55e; }}
        .review-main .rev-card.semantic {{ border-left: 4px solid #f59e0b; }}
        .review-main .rev-card .rc-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
        .review-main .rev-card .rc-strategy {{ font-size: 0.8rem; font-weight: 700; text-transform: uppercase; }}
        .review-main .rev-card .rc-strategy.direct {{ color: #22c55e; }}
        .review-main .rev-card .rc-strategy.semantic {{ color: #f59e0b; }}
        .review-main .rev-card .rc-confidence {{ font-size: 0.8rem; color: #94a3b8; }}
        .review-main .rev-card .rc-doc {{ font-size: 0.9rem; color: #60a5fa; margin-bottom: 6px; }}
        .review-main .rev-card .rc-snippet {{ font-size: 0.85rem; color: #cbd5e1; background: #0f172a; padding: 12px; border-radius: 6px; font-family: monospace; white-space: pre-wrap; word-break: break-word; max-height: 300px; overflow-y: auto; line-height: 1.5; }}
        .review-main .rev-card .rc-detail {{ font-size: 0.8rem; color: #64748b; margin-top: 6px; }}
        .review-main .rev-card .rc-actions {{ display: flex; gap: 10px; margin-top: 10px; }}
        .review-main .rev-card .rc-actions button {{ padding: 5px 16px; border-radius: 5px; border: 2px solid #475569; background: transparent; color: #94a3b8; cursor: pointer; font-size: 0.8rem; font-weight: 600; transition: all 0.15s; }}
        .review-main .rev-card .rc-actions .btn-accept:hover, .review-main .rev-card .rc-actions .btn-accept.active {{ background: rgba(34,197,94,0.2); border-color: #22c55e; color: #22c55e; }}
        .review-main .rev-card .rc-actions .btn-reject:hover, .review-main .rev-card .rc-actions .btn-reject.active {{ background: rgba(239,68,68,0.2); border-color: #ef4444; color: #ef4444; }}
        .review-main .no-ev {{ color: #64748b; font-size: 0.9rem; font-style: italic; padding: 30px 0; text-align: center; }}
        .review-footer {{ display: flex; align-items: center; padding: 10px 20px; background: #1e293b; border-top: 1px solid #334155; flex-shrink: 0; }}
        .review-filter {{ font-size: 0.8rem; color: #94a3b8; display: flex; align-items: center; gap: 6px; }}
        .review-filter button {{ padding: 3px 10px; border-radius: 4px; border: 1px solid #475569; background: transparent; color: #94a3b8; cursor: pointer; font-size: 0.75rem; }}
        .review-filter button:hover {{ background: #334155; }}
        .review-filter button.active {{ background: #3b82f6; color: #fff; border-color: #3b82f6; }}

        /* Review tab queue */
        .review-queue-summary {{ font-size: 0.85rem; color: #94a3b8; margin-bottom: 12px; }}
        .review-queue-summary strong {{ color: #e2e8f0; }}
        .review-queue-filters {{ display: flex; gap: 6px; margin-bottom: 12px; }}
        .review-queue-filters button {{ padding: 4px 10px; border-radius: 4px; border: 1px solid #475569; background: transparent; color: #94a3b8; cursor: pointer; font-size: 0.75rem; }}
        .review-queue-filters button:hover {{ background: #334155; }}
        .review-queue-filters button.active {{ background: #3b82f6; color: #fff; border-color: #3b82f6; }}
        .rq-item {{ display: flex; align-items: center; gap: 10px; background: #334155; padding: 10px 12px; border-radius: 6px; margin: 6px 0; cursor: pointer; }}
        .rq-item:hover {{ background: #3b4a5e; }}
        .rq-item .rq-dot {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}
        .rq-item .rq-dot.covered {{ background: #22c55e; }}
        .rq-item .rq-dot.uncovered {{ background: #ef4444; }}
        .rq-item .rq-name {{ flex: 1; font-size: 0.85rem; font-weight: 500; }}
        .rq-item .rq-type {{ font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; }}
        .rq-item .rq-ev-count {{ font-size: 0.7rem; color: #64748b; }}
        .rq-item .rq-judgment {{ font-size: 0.7rem; padding: 1px 6px; border-radius: 3px; }}
        .rq-item .rq-judgment.reviewed {{ background: rgba(34,197,94,0.2); color: #22c55e; }}
        .rq-item .rq-judgment.pending {{ background: rgba(148,163,184,0.15); color: #64748b; }}
        .rq-start-btn {{ display: block; width: 100%; padding: 10px; margin-top: 12px; border-radius: 6px; border: 1px solid #3b82f6; background: rgba(59,130,246,0.15); color: #3b82f6; cursor: pointer; font-size: 0.85rem; font-weight: 600; text-align: center; }}
        .rq-start-btn:hover {{ background: rgba(59,130,246,0.3); }}
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
                        <div class="stat-label">Graph Elements</div>
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
                <div class="tab active" onclick="showTab('surface')">Graph</div>
                <div class="tab" onclick="showTab('itm')">Checklist</div>
                <div class="tab" onclick="showTab('atm')">Inventory</div>
                <div class="tab" onclick="showTab('gaps')">Drift</div>
                <div class="tab" onclick="showTab('review')">Review</div>
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
                    <h3 style="margin-top:12px">Match Evidence</h3>
                    <div id="detail-evidence"></div>
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

            <div id="tab-review" class="tab-content">
                <div class="review-queue-summary" id="review-queue-summary"></div>
                <div class="review-queue-filters">
                    <button class="active" data-rq-filter="all" onclick="filterReviewQueue('all', this)">All</button>
                    <button data-rq-filter="covered" onclick="filterReviewQueue('covered', this)">Covered</button>
                    <button data-rq-filter="uncovered" onclick="filterReviewQueue('uncovered', this)">Uncovered</button>
                    <button data-rq-filter="pending" onclick="filterReviewQueue('pending', this)">Unreviewed</button>
                </div>
                <button class="rq-start-btn" onclick="openReviewAll()">Start Review</button>
                <div id="review-queue-list"></div>
            </div>
        </div>
    </div>

    <div id="review-overlay">
        <div class="review-header">
            <h2>Match Review</h2>
            <span class="review-progress" id="review-progress">0 / 0</span>
            <div class="review-nav">
                <button onclick="reviewPrev()" title="Previous (Left arrow or P)">&#8592; Prev</button>
                <button onclick="reviewNext()" title="Next (Right arrow or N)">Next &#8594;</button>
            </div>
            <div class="review-header-actions">
                <button onclick="exportJudgments()">Export Judgments</button>
                <button onclick="closeReview()">&#10005; Close</button>
            </div>
        </div>
        <div class="review-body">
            <div class="review-left">
                <div id="review-node-info"></div>
            </div>
            <div class="review-main">
                <div id="review-evidence"></div>
            </div>
        </div>
        <div class="review-footer">
            <span class="review-filter">
                Show:
                <button class="active" data-rov-filter="all" onclick="setReviewFilter('all', this)">All</button>
                <button data-rov-filter="covered" onclick="setReviewFilter('covered', this)">Covered</button>
                <button data-rov-filter="uncovered" onclick="setReviewFilter('uncovered', this)">Uncovered</button>
                <button data-rov-filter="pending" onclick="setReviewFilter('pending', this)">Unreviewed</button>
            </span>
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

            // Render match evidence
            const evContainer = document.getElementById('detail-evidence');
            const evidence = node.match_evidence || [];
            const judgments = loadJudgments();
            if (evidence.length === 0) {{
                evContainer.innerHTML = (node.is_covered
                    ? '<div class="no-evidence">Covered (no detailed evidence recorded)</div>'
                    : '<div class="no-evidence">No match found in documentation</div>')
                    + `<div style="margin-top:8px"><button class="drift-evidence-toggle" onclick="openReview('${{node.id.replace(/'/g, "\\\\'")}}')">Open in Review &#8599;</button></div>`;
            }} else {{
                evContainer.innerHTML = evidence.map((ev, idx) => {{
                    const stratClass = ev.strategy === 'direct_reference' ? 'direct' : 'semantic';
                    const stratLabel = ev.strategy === 'direct_reference' ? 'Direct Ref' : 'Semantic';
                    const confPct = Math.round(ev.confidence * 100);
                    const section = ev.doc_section ? ` > ${{ev.doc_section}}` : '';
                    const jKey = node.id + '::' + idx;
                    const j = judgments[jKey];
                    const accClass = j && j.verdict === 'accepted' ? ' active' : '';
                    const rejClass = j && j.verdict === 'rejected' ? ' active' : '';
                    return `
                        <div class="evidence-card ${{stratClass}}">
                            <div class="ev-header">
                                <span class="ev-strategy ${{stratClass}}">${{stratLabel}} (${{confPct}}%)</span>
                                <span class="ev-confidence">${{ev.match_detail}}</span>
                            </div>
                            <div class="ev-doc">${{ev.doc_file}}${{section}}</div>
                            <div class="ev-snippet">${{ev.doc_snippet}}</div>
                            <div class="ev-actions">
                                <button class="btn-accept${{accClass}}" onclick="sidebarJudge('${{node.id.replace(/'/g, "\\\\'")}}', ${{idx}}, 'accepted', this)">&#10003; Accept</button>
                                <button class="btn-reject${{rejClass}}" onclick="sidebarJudge('${{node.id.replace(/'/g, "\\\\'")}}', ${{idx}}, 'rejected', this)">&#10007; Reject</button>
                            </div>
                        </div>
                    `;
                }}).join('')
                + `<div style="margin-top:8px"><button class="drift-evidence-toggle" onclick="openReview('${{node.id.replace(/'/g, "\\\\'")}}')">Open in Review &#8599;</button></div>`;
            }}
        }}

        function sidebarJudge(nodeId, evidenceIdx, verdict, btn) {{
            const jKey = nodeId + '::' + evidenceIdx;
            const judgments = loadJudgments();
            if (judgments[jKey] && judgments[jKey].verdict === verdict) {{
                // Toggle off
                saveJudgment(nodeId, evidenceIdx, null);
                btn.classList.remove('active');
            }} else {{
                saveJudgment(nodeId, evidenceIdx, verdict);
                // Update button states
                const actions = btn.parentElement;
                actions.querySelector('.btn-accept').classList.toggle('active', verdict === 'accepted');
                actions.querySelector('.btn-reject').classList.toggle('active', verdict === 'rejected');
            }}
        }}

        function showTab(name) {{
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            // Find the tab button that corresponds to this name
            const tabs = document.querySelectorAll('.tab');
            const tabNames = ['surface', 'itm', 'atm', 'gaps', 'review'];
            const idx = tabNames.indexOf(name);
            if (idx >= 0 && tabs[idx]) tabs[idx].classList.add('active');
            document.getElementById('tab-' + name).classList.add('active');
            if (name === 'review') renderReviewQueue();
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

        // Render evidence cards for drift items
        function renderDriftEvidence(evidence) {{
            if (!evidence || evidence.length === 0) return '';
            return evidence.map(ev => {{
                const stratClass = ev.strategy === 'direct_reference' ? 'direct' : 'semantic';
                const stratLabel = ev.strategy === 'direct_reference' ? 'Direct' : 'Semantic';
                const confPct = Math.round(ev.confidence * 100);
                return `<div class="evidence-card ${{stratClass}}" style="margin:4px 0;padding:8px;">
                    <div class="ev-header">
                        <span class="ev-strategy ${{stratClass}}">${{stratLabel}} (${{confPct}}%)</span>
                        <span class="ev-confidence">${{ev.match_detail}}</span>
                    </div>
                    <div class="ev-doc" style="font-size:0.75rem">${{ev.doc_file}}</div>
                    <div class="ev-snippet" style="font-size:0.7rem;max-height:50px">${{ev.doc_snippet.substring(0, 120)}}</div>
                </div>`;
            }}).join('');
        }}

        // Populate gaps list
        let driftCounter = 0;
        const gapsList = document.getElementById('gaps-list');

        // Show complete items first (collapsed)
        data.gaps.filter(g => g.status === 'complete').forEach(g => {{
            const id = 'drift-ev-' + (driftCounter++);
            const evHtml = g.evidence && g.evidence.length > 0
                ? `<div class="drift-evidence">
                       <button class="drift-evidence-toggle" onclick="const b=document.getElementById('${{id}}');b.classList.toggle('open');this.textContent=b.classList.contains('open')?'Hide evidence':'Show evidence (${{g.evidence.length}})'">Show evidence (${{g.evidence.length}})</button>
                       <div id="${{id}}" class="drift-evidence-body">${{renderDriftEvidence(g.evidence)}}</div>
                   </div>`
                : '';
            gapsList.innerHTML += `
                <div class="gap-item gap-complete">
                    <div class="topic-name">${{g.topic}} <span class="badge badge-complete">complete</span></div>
                    ${{evHtml}}
                </div>
            `;
        }});

        // Then missing/partial items
        data.gaps.filter(g => g.status !== 'complete').forEach(g => {{
            const id = 'drift-ev-' + (driftCounter++);
            const missingInfo = g.missing && g.missing.length > 0
                ? `<div class="topic-meta" style="margin-top:4px">Missing: ${{g.missing.map(m => m.split(':').pop()).join(', ')}}</div>`
                : '';
            const evHtml = g.evidence && g.evidence.length > 0
                ? `<div class="drift-evidence">
                       <button class="drift-evidence-toggle" onclick="const b=document.getElementById('${{id}}');b.classList.toggle('open');this.textContent=b.classList.contains('open')?'Hide evidence':'Show evidence (${{g.evidence.length}})'">Show evidence (${{g.evidence.length}})</button>
                       <div id="${{id}}" class="drift-evidence-body">${{renderDriftEvidence(g.evidence)}}</div>
                   </div>`
                : '';
            gapsList.innerHTML += `
                <div class="gap-item gap-${{g.status}}">
                    <div class="topic-name">${{g.topic}} <span class="badge badge-${{g.status}}">${{g.status}}</span></div>
                    <div class="topic-meta">${{g.action}}</div>
                    ${{missingInfo}}
                    ${{evHtml}}
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

        // =====================================================================
        // REVIEW MODE - Judgment persistence & full-screen review overlay
        // =====================================================================

        const STORAGE_KEY = 'doczot-judgments-' + data.product_name;

        function loadJudgments() {{
            try {{
                const stored = localStorage.getItem(STORAGE_KEY);
                return stored ? JSON.parse(stored) : {{}};
            }} catch (e) {{
                return {{}};
            }}
        }}

        function saveJudgment(nodeId, evidenceIdx, verdict) {{
            const judgments = loadJudgments();
            const key = nodeId + '::' + evidenceIdx;
            if (verdict === null) {{
                delete judgments[key];
            }} else {{
                judgments[key] = {{
                    verdict: verdict,
                    timestamp: new Date().toISOString(),
                    nodeId: nodeId,
                    evidenceIdx: evidenceIdx,
                }};
            }}
            localStorage.setItem(STORAGE_KEY, JSON.stringify(judgments));
            updateReviewProgress();
        }}

        function exportJudgments() {{
            const judgments = loadJudgments();
            const enriched = Object.entries(judgments).map(function(entry) {{
                const j = entry[1];
                const node = data.surface.nodes.find(function(n) {{ return n.id === j.nodeId; }});
                const ev = node && node.match_evidence ? node.match_evidence[j.evidenceIdx] : null;
                return {{
                    verdict: j.verdict,
                    timestamp: j.timestamp,
                    nodeId: j.nodeId,
                    evidenceIdx: j.evidenceIdx,
                    node_name: node ? node.name : null,
                    node_type: node ? node.type : null,
                    evidence: ev || null,
                }};
            }});
            const blob = new Blob([JSON.stringify(enriched, null, 2)], {{type: 'application/json'}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'doczot-judgments-' + data.product_name + '.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }}

        // --- Review queue and overlay ---

        let reviewQueue = [];
        let reviewIndex = 0;
        let reviewFilterMode = 'all';

        function getNodeJudgmentStatus(node) {{
            // Returns 'reviewed' if all evidence items have a judgment, 'pending' otherwise
            const judgments = loadJudgments();
            const evidence = node.match_evidence || [];
            if (evidence.length === 0) return 'pending';
            for (let i = 0; i < evidence.length; i++) {{
                if (!judgments[node.id + '::' + i]) return 'pending';
            }}
            return 'reviewed';
        }}

        function buildReviewQueue(filter) {{
            filter = filter || reviewFilterMode;
            const nodes = data.surface.nodes;
            reviewQueue = nodes.filter(function(n) {{
                if (filter === 'covered') return n.is_covered;
                if (filter === 'uncovered') return !n.is_covered;
                if (filter === 'pending') return getNodeJudgmentStatus(n) === 'pending';
                return true;
            }});
        }}

        function openReview(nodeId) {{
            buildReviewQueue();
            reviewIndex = reviewQueue.findIndex(function(n) {{ return n.id === nodeId; }});
            if (reviewIndex < 0) reviewIndex = 0;
            if (reviewQueue.length === 0) return;
            renderReviewItem();
            document.getElementById('review-overlay').classList.add('active');
        }}

        function openReviewAll() {{
            buildReviewQueue();
            reviewIndex = 0;
            if (reviewQueue.length === 0) return;
            renderReviewItem();
            document.getElementById('review-overlay').classList.add('active');
        }}

        function reviewNext() {{
            if (reviewIndex < reviewQueue.length - 1) {{
                reviewIndex++;
                renderReviewItem();
            }}
        }}

        function reviewPrev() {{
            if (reviewIndex > 0) {{
                reviewIndex--;
                renderReviewItem();
            }}
        }}

        function closeReview() {{
            document.getElementById('review-overlay').classList.remove('active');
            // Refresh the review queue tab if it's visible
            renderReviewQueue();
        }}

        function setReviewFilter(filter, btn) {{
            reviewFilterMode = filter;
            // Update overlay footer filter buttons
            document.querySelectorAll('.review-footer .review-filter button').forEach(function(b) {{
                b.classList.toggle('active', b.getAttribute('data-rov-filter') === filter);
            }});
            const currentNodeId = reviewQueue[reviewIndex] ? reviewQueue[reviewIndex].id : null;
            buildReviewQueue(filter);
            if (reviewQueue.length === 0) {{
                reviewIndex = 0;
                document.getElementById('review-evidence').innerHTML = '<div class="no-ev">No nodes match this filter.</div>';
                document.getElementById('review-node-info').innerHTML = '';
                updateReviewProgress();
                return;
            }}
            // Try to stay on the same node
            if (currentNodeId) {{
                const idx = reviewQueue.findIndex(function(n) {{ return n.id === currentNodeId; }});
                reviewIndex = idx >= 0 ? idx : 0;
            }} else {{
                reviewIndex = 0;
            }}
            renderReviewItem();
        }}

        function updateReviewProgress() {{
            const el = document.getElementById('review-progress');
            if (el && reviewQueue.length > 0) {{
                el.textContent = (reviewIndex + 1) + ' / ' + reviewQueue.length;
            }} else if (el) {{
                el.textContent = '0 / 0';
            }}
        }}

        function escapeHtml(str) {{
            if (!str) return '';
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }}

        function renderReviewItem() {{
            if (reviewQueue.length === 0) return;
            const node = reviewQueue[reviewIndex];
            const judgments = loadJudgments();
            updateReviewProgress();

            // Left panel: node info
            const covClass = node.is_covered ? 'documented' : 'undocumented';
            const covLabel = node.is_covered ? 'Documented' : 'Undocumented';
            let leftHtml = '<h3>' + escapeHtml(node.name) + '</h3>';
            leftHtml += '<div class="rl-type ' + node.type + '">' + node.type + '</div>';
            if (node.signature) {{
                leftHtml += '<div class="rl-meta"><strong>Signature:</strong><br>' + escapeHtml(node.signature) + '</div>';
            }}
            if (node.source) {{
                leftHtml += '<div class="rl-meta"><strong>Source:</strong><br>' + escapeHtml(node.source) + '</div>';
            }}
            leftHtml += '<div class="rl-coverage ' + covClass + '">' + covLabel + '</div>';
            if (node.itm_topics && node.itm_topics.length > 0) {{
                leftHtml += '<div class="rl-topics"><div><strong>Checklist topics:</strong></div>';
                node.itm_topics.forEach(function(t) {{ leftHtml += '<div>&#8226; <span>' + escapeHtml(t) + '</span></div>'; }});
                leftHtml += '</div>';
            }}
            if (node.atm_topics && node.atm_topics.length > 0) {{
                leftHtml += '<div class="rl-topics"><div><strong>Inventory topics:</strong></div>';
                node.atm_topics.forEach(function(t) {{ leftHtml += '<div>&#8226; <span>' + escapeHtml(t) + '</span></div>'; }});
                leftHtml += '</div>';
            }}
            document.getElementById('review-node-info').innerHTML = leftHtml;

            // Main panel: evidence cards
            const evidence = node.match_evidence || [];
            let mainHtml = '';
            if (evidence.length === 0) {{
                mainHtml = '<div class="no-ev">' + (node.is_covered
                    ? 'This node is marked as covered, but no detailed match evidence was recorded.'
                    : 'No documentation match found for this node.') + '</div>';
            }} else {{
                evidence.forEach(function(ev, idx) {{
                    const stratClass = ev.strategy === 'direct_reference' ? 'direct' : 'semantic';
                    const stratLabel = ev.strategy === 'direct_reference' ? 'Direct Reference' : 'Semantic Match';
                    const confPct = Math.round(ev.confidence * 100);
                    const section = ev.doc_section ? ' &gt; ' + escapeHtml(ev.doc_section) : '';
                    const jKey = node.id + '::' + idx;
                    const j = judgments[jKey];
                    const accActive = j && j.verdict === 'accepted' ? ' active' : '';
                    const rejActive = j && j.verdict === 'rejected' ? ' active' : '';
                    mainHtml += '<div class="rev-card ' + stratClass + '">'
                        + '<div class="rc-header">'
                        + '<span class="rc-strategy ' + stratClass + '">' + stratLabel + ' (' + confPct + '%)</span>'
                        + '<span class="rc-confidence">' + escapeHtml(ev.match_detail) + '</span>'
                        + '</div>'
                        + '<div class="rc-doc">' + escapeHtml(ev.doc_file) + section + '</div>'
                        + '<div class="rc-snippet">' + escapeHtml(ev.doc_snippet) + '</div>'
                        + '<div class="rc-detail">' + escapeHtml(ev.match_detail) + '</div>'
                        + '<div class="rc-actions">'
                        + '<button class="btn-accept' + accActive + '" onclick="reviewJudge(\'' + node.id.replace(/'/g, "\\\\'") + '\', ' + idx + ', \'accepted\', this)">&#10003; Accept</button>'
                        + '<button class="btn-reject' + rejActive + '" onclick="reviewJudge(\'' + node.id.replace(/'/g, "\\\\'") + '\', ' + idx + ', \'rejected\', this)">&#10007; Reject</button>'
                        + '</div>'
                        + '</div>';
                }});
            }}
            document.getElementById('review-evidence').innerHTML = mainHtml;
        }}

        function reviewJudge(nodeId, evidenceIdx, verdict, btn) {{
            const jKey = nodeId + '::' + evidenceIdx;
            const judgments = loadJudgments();
            if (judgments[jKey] && judgments[jKey].verdict === verdict) {{
                saveJudgment(nodeId, evidenceIdx, null);
                btn.classList.remove('active');
            }} else {{
                saveJudgment(nodeId, evidenceIdx, verdict);
                const actions = btn.parentElement;
                actions.querySelector('.btn-accept').classList.toggle('active', verdict === 'accepted');
                actions.querySelector('.btn-reject').classList.toggle('active', verdict === 'rejected');
            }}
        }}

        // Keyboard navigation for review overlay
        document.addEventListener('keydown', function(e) {{
            const overlay = document.getElementById('review-overlay');
            if (!overlay.classList.contains('active')) return;
            if (e.key === 'ArrowRight' || e.key === 'n') {{ e.preventDefault(); reviewNext(); }}
            if (e.key === 'ArrowLeft' || e.key === 'p') {{ e.preventDefault(); reviewPrev(); }}
            if (e.key === 'Escape') {{ e.preventDefault(); closeReview(); }}
        }});

        // --- Review queue tab rendering ---

        let reviewQueueFilter = 'all';

        function filterReviewQueue(filter, btn) {{
            reviewQueueFilter = filter;
            document.querySelectorAll('.review-queue-filters button').forEach(function(b) {{
                b.classList.toggle('active', b.getAttribute('data-rq-filter') === filter);
            }});
            renderReviewQueue();
        }}

        function renderReviewQueue() {{
            const judgments = loadJudgments();
            const nodes = data.surface.nodes;
            let filtered = nodes;
            if (reviewQueueFilter === 'covered') filtered = nodes.filter(function(n) {{ return n.is_covered; }});
            else if (reviewQueueFilter === 'uncovered') filtered = nodes.filter(function(n) {{ return !n.is_covered; }});
            else if (reviewQueueFilter === 'pending') filtered = nodes.filter(function(n) {{ return getNodeJudgmentStatus(n) === 'pending'; }});

            // Compute stats
            let totalReviewed = 0;
            let totalRejected = 0;
            let totalCoveredNodes = nodes.filter(function(n) {{ return n.is_covered; }}).length;
            nodes.forEach(function(n) {{
                if (getNodeJudgmentStatus(n) === 'reviewed') totalReviewed++;
                const ev = n.match_evidence || [];
                for (let i = 0; i < ev.length; i++) {{
                    const j = judgments[n.id + '::' + i];
                    if (j && j.verdict === 'rejected') {{ totalRejected++; }}
                }}
            }});

            const summary = document.getElementById('review-queue-summary');
            summary.innerHTML = 'Reviewed <strong>' + totalReviewed + '</strong> / <strong>' + nodes.length + '</strong> nodes'
                + (totalRejected > 0 ? ', <strong style="color:#ef4444">' + totalRejected + '</strong> rejected' : '');

            const list = document.getElementById('review-queue-list');
            if (filtered.length === 0) {{
                list.innerHTML = '<div style="color:#64748b;font-style:italic;padding:12px 0">No nodes match this filter.</div>';
                return;
            }}

            let html = '';
            filtered.forEach(function(n) {{
                const covClass = n.is_covered ? 'covered' : 'uncovered';
                const evCount = (n.match_evidence || []).length;
                const jStatus = getNodeJudgmentStatus(n);
                const jLabel = jStatus === 'reviewed' ? 'Reviewed' : 'Pending';
                const jClass = jStatus === 'reviewed' ? 'reviewed' : 'pending';
                const safeId = n.id.replace(/'/g, "\\\\'");
                html += '<div class="rq-item" onclick="openReview(\'' + safeId + '\')">'
                    + '<span class="rq-dot ' + covClass + '"></span>'
                    + '<span class="rq-name">' + escapeHtml(n.name) + '</span>'
                    + '<span class="rq-type">' + n.type + '</span>'
                    + (evCount > 0 ? '<span class="rq-ev-count">' + evCount + ' ev</span>' : '')
                    + '<span class="rq-judgment ' + jClass + '">' + jLabel + '</span>'
                    + '</div>';
            }});
            list.innerHTML = html;
        }}

        // Initial render of review queue
        renderReviewQueue();
    </script>
</body>
</html>
"""


# =============================================================================
# DIFF COMMAND
# =============================================================================

def cmd_diff(args):
    """Compare two System Graph scans and report changes."""
    db_path = args.db_path or ".doczot/manifests.db"
    store = ManifestStore(db_path)

    # Get product name (required)
    if not args.product:
        print("Error: --product is required for diff command")
        return 1

    # Load scans
    try:
        old_scan = store.load_system_graph(args.product, args.old_scan)
        new_scan = store.load_system_graph(args.product, args.new_scan)
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
    diff = diff_system_graphs(old_scan, new_scan)

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
# EXPORT COMMAND (MCP, llms.txt, JSON-LD)
# =============================================================================

def cmd_export(args):
    """Export system graph in agent-oriented formats."""
    from doczot_analyzer.exports import export_mcp_resources, export_llms_txt, export_jsonld

    repo_path = args.repo_path or "."
    repo_path = str(Path(repo_path).resolve())

    print(f"Analyzing: {repo_path}")
    surface, itm, atm, gap_report = analyze_repository(repo_path, args.name)

    fmt = args.format

    if fmt == "mcp":
        output = json.dumps(export_mcp_resources(surface), indent=2)
    elif fmt == "llms":
        output = export_llms_txt(surface, itm)
    elif fmt == "json-ld":
        output = json.dumps(export_jsonld(surface), indent=2)
    else:
        print(f"Unknown format: {fmt}")
        return 1

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output)
        print(f"\nExported {fmt} to: {output_path}")
    else:
        print(output)

    return 0


# =============================================================================
# EXPORT-ONTOLOGY COMMAND
# =============================================================================

def cmd_export_ontology(args):
    """Export System Graph and manifests to RDF/OWL ontology."""
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
        print("Converting System Graph to ontology...")
        onto = surface_graph_to_ontology(surface, include_schema=not args.no_schema)
    else:
        print("Converting full analysis (graph + checklist + inventory) to ontology...")
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

    # surface (System Graph)
    p = subparsers.add_parser("surface", help="Explore System Graph (code structure)")
    p.add_argument("repo_path", nargs="?", default=".")
    p.add_argument("--name", help="Product name")
    p.add_argument("--type", choices=["all", "verbs", "nouns", "concepts", "orphans"], default="all")
    p.add_argument("--output", "-o", help="Save to JSON")
    p.set_defaults(func=cmd_surface)

    # itm (Coverage Checklist)
    p = subparsers.add_parser("itm", help="View Coverage Checklist (what should be documented)")
    p.add_argument("repo_path", nargs="?", default=".")
    p.add_argument("--name", help="Product name")
    p.add_argument("--load", help="Load checklist from JSON file")
    p.add_argument("--output", "-o", help="Save to JSON")
    p.set_defaults(func=cmd_itm)

    # atm (Content Inventory)
    p = subparsers.add_parser("atm", help="View Content Inventory (what is documented)")
    p.add_argument("repo_path", nargs="?", default=".")
    p.add_argument("--name", help="Product name")
    p.add_argument("--output", "-o", help="Save to JSON")
    p.set_defaults(func=cmd_atm)

    # gaps (Drift Report)
    p = subparsers.add_parser("gaps", help="View Drift Report (code vs docs divergence)")
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

    # serve (dashboard)
    p = subparsers.add_parser("serve", help="Launch interactive dashboard")
    p.add_argument("repo_path", nargs="?", default=".")
    p.add_argument("--port", type=int, default=8456, help="Port to serve on")
    p.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    p.add_argument("--db-path", default=".doczot/manifests.db", help="Database path")
    p.add_argument("--open", action="store_true", default=True, help="Open browser automatically")
    p.add_argument("--no-open", dest="open", action="store_false", help="Don't open browser")
    p.set_defaults(func=cmd_serve)

    # diff
    p = subparsers.add_parser("diff", help="Compare two System Graph scans")
    p.add_argument("--product", required=True, help="Product name")
    p.add_argument("--old-scan", help="Old scan ID (default: previous)")
    p.add_argument("--new-scan", help="New scan ID (default: latest)")
    p.add_argument("--db-path", default=".doczot/manifests.db", help="Database path")
    p.add_argument("--verbose", "-v", action="store_true", help="Show detailed changes")
    p.add_argument("--output", "-o", help="Save diff to JSON file")
    p.set_defaults(func=cmd_diff)

    # export (MCP, llms.txt, JSON-LD)
    p = subparsers.add_parser("export", help="Export for AI agents (MCP, llms.txt, JSON-LD)")
    p.add_argument("repo_path", nargs="?", default=".")
    p.add_argument("--name", help="Product name")
    p.add_argument("--format", "-f", required=True,
                   choices=["mcp", "llms", "json-ld"],
                   help="Export format: mcp (resource defs), llms (llms.txt), json-ld")
    p.add_argument("--output", "-o", help="Save to file (otherwise prints to stdout)")
    p.set_defaults(func=cmd_export)

    # export-ontology
    p = subparsers.add_parser("export-ontology", help="Export to RDF/OWL ontology")
    p.add_argument("repo_path", nargs="?", default=".")
    p.add_argument("--name", help="Product name")
    p.add_argument("--format", "-f", default="turtle",
                   choices=["turtle", "ttl", "json-ld", "jsonld", "xml", "rdf", "ntriples", "nt", "n3"],
                   help="Output format (default: turtle)")
    p.add_argument("--output", "-o", help="Save to file (otherwise prints to stdout)")
    p.add_argument("--surface-only", action="store_true",
                   help="Export only System Graph (not checklist/inventory)")
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

    # validate (validation framework)
    from validation.cli import register_validate_commands
    register_validate_commands(subparsers)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Handle validate subcommands
    if args.command == "validate":
        if not hasattr(args, "func") or not getattr(args, "validate_command", None):
            # Print validate help
            parser.parse_args(["validate", "--help"])
            return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
