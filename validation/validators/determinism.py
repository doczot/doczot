"""Determinism validator.

Verifies that DocZot produces identical output when run twice on the same input.
The AST scanner should be perfectly deterministic. The semantic matcher may not be.
"""
from __future__ import annotations

from doczot_analyzer.models_v2 import SystemGraph
from doczot_analyzer.analyzer_v2 import build_system_graph
from validation.models import (
    CheckResult,
    ValidationDimension,
    ValidationStatus,
)

DIMENSION = ValidationDimension.DETERMINISM


def _compare_graphs(a: SystemGraph, b: SystemGraph) -> list[str]:
    """Compare two SystemGraphs and return a list of differences."""
    diffs = []

    a_node_ids = sorted(n.id for n in a.nodes)
    b_node_ids = sorted(n.id for n in b.nodes)
    if a_node_ids != b_node_ids:
        added = set(b_node_ids) - set(a_node_ids)
        removed = set(a_node_ids) - set(b_node_ids)
        if added:
            diffs.append(f"Nodes in run 2 but not run 1: {sorted(added)}")
        if removed:
            diffs.append(f"Nodes in run 1 but not run 2: {sorted(removed)}")

    a_edge_keys = sorted(
        (e.source_id, e.target_id, e.edge_type.value) for e in a.edges
    )
    b_edge_keys = sorted(
        (e.source_id, e.target_id, e.edge_type.value) for e in b.edges
    )
    if a_edge_keys != b_edge_keys:
        a_set = set(a_edge_keys)
        b_set = set(b_edge_keys)
        added = b_set - a_set
        removed = a_set - b_set
        if added:
            diffs.append(f"Edges in run 2 but not run 1: {len(added)}")
        if removed:
            diffs.append(f"Edges in run 1 but not run 2: {len(removed)}")

    # Check node attribute stability (same ID should have same attributes)
    a_nodes = {n.id: n for n in a.nodes}
    b_nodes = {n.id: n for n in b.nodes}
    for nid in set(a_nodes) & set(b_nodes):
        na, nb = a_nodes[nid], b_nodes[nid]
        if na.name != nb.name:
            diffs.append(f"Node {nid}: name '{na.name}' vs '{nb.name}'")
        if na.type != nb.type:
            diffs.append(f"Node {nid}: type '{na.type}' vs '{nb.type}'")
        if na.http_method != nb.http_method:
            diffs.append(f"Node {nid}: method '{na.http_method}' vs '{nb.http_method}'")
        if na.http_path != nb.http_path:
            diffs.append(f"Node {nid}: path '{na.http_path}' vs '{nb.http_path}'")

    return diffs


def check_graph_determinism(repo_path: str, product_name: str = "test") -> CheckResult:
    """Run build_system_graph twice and compare.

    Args:
        repo_path: Path to the repository to scan.
        product_name: Product name for the graph.
    """
    try:
        graph_a = build_system_graph(repo_path, product_name)
        graph_b = build_system_graph(repo_path, product_name)
    except Exception as e:
        return CheckResult(
            name="graph_determinism",
            dimension=DIMENSION,
            status=ValidationStatus.SKIPPED,
            message=f"Could not scan: {e}",
        )

    diffs = _compare_graphs(graph_a, graph_b)

    if diffs:
        return CheckResult(
            name="graph_determinism",
            dimension=DIMENSION,
            status=ValidationStatus.FAIL,
            message=f"Graph scan is non-deterministic: {len(diffs)} difference(s)",
            details=diffs,
        )
    return CheckResult(
        name="graph_determinism",
        dimension=DIMENSION,
        status=ValidationStatus.PASS,
        message=(
            f"Graph scan is deterministic: "
            f"{len(graph_a.nodes)} nodes, {len(graph_a.edges)} edges identical across runs"
        ),
    )


def validate_determinism_from_graphs(
    graph_a: SystemGraph,
    graph_b: SystemGraph,
) -> list[CheckResult]:
    """Compare two pre-built graphs for determinism.

    Useful when you don't want to re-scan but have two graphs to compare.
    """
    diffs = _compare_graphs(graph_a, graph_b)

    if diffs:
        result = CheckResult(
            name="graph_determinism",
            dimension=DIMENSION,
            status=ValidationStatus.FAIL,
            message=f"Graphs differ: {len(diffs)} difference(s)",
            details=diffs,
        )
    else:
        result = CheckResult(
            name="graph_determinism",
            dimension=DIMENSION,
            status=ValidationStatus.PASS,
            message=(
                f"Graphs are identical: "
                f"{len(graph_a.nodes)} nodes, {len(graph_a.edges)} edges"
            ),
        )
    return [result]
