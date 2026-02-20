"""Graph consistency validator.

Checks that a SystemGraph is internally well-formed: no orphaned edges,
correct edge type semantics, valid node ID formats, no duplicates, and
required fields present.
"""
from __future__ import annotations

from datetime import datetime

from doczot_analyzer.models_v2 import (
    SystemGraph,
    NodeType,
    EdgeType,
)
from validation.models import (
    CheckResult,
    ValidationDimension,
    ValidationStatus,
)

DIMENSION = ValidationDimension.GRAPH_CONSISTENCY

# Expected edge type semantics: source_type -> target_type
EDGE_TYPE_RULES: dict[EdgeType, list[tuple[NodeType, NodeType]]] = {
    EdgeType.OPERATES_ON: [(NodeType.VERB, NodeType.NOUN)],
    EdgeType.PART_OF: [(NodeType.NOUN, NodeType.NOUN)],
    EdgeType.CONSTRAINED_BY: [(NodeType.VERB, NodeType.CONSTRAINT)],
    EdgeType.PREREQUISITE: [
        (NodeType.CONCEPT, NodeType.CONCEPT),
        (NodeType.VERB, NodeType.VERB),
    ],
    EdgeType.RELATED_TO: [],  # any -> any, no restrictions
}


def check_orphaned_edges(graph: SystemGraph) -> CheckResult:
    """Every edge must reference nodes that exist in the graph."""
    node_ids = {n.id for n in graph.nodes}
    orphaned = []
    for edge in graph.edges:
        if edge.source_id not in node_ids:
            orphaned.append(f"Edge source '{edge.source_id}' not found in nodes")
        if edge.target_id not in node_ids:
            orphaned.append(f"Edge target '{edge.target_id}' not found in nodes")

    if orphaned:
        return CheckResult(
            name="orphaned_edges",
            dimension=DIMENSION,
            status=ValidationStatus.FAIL,
            message=f"{len(orphaned)} orphaned edge reference(s) found",
            details=orphaned,
        )
    return CheckResult(
        name="orphaned_edges",
        dimension=DIMENSION,
        status=ValidationStatus.PASS,
        message=f"All {len(graph.edges)} edge(s) reference valid nodes",
    )


def check_edge_type_semantics(graph: SystemGraph) -> CheckResult:
    """Edge types should connect appropriate node types."""
    node_map = {n.id: n for n in graph.nodes}
    violations = []

    for edge in graph.edges:
        source = node_map.get(edge.source_id)
        target = node_map.get(edge.target_id)
        if not source or not target:
            continue  # orphaned_edges check handles this

        rules = EDGE_TYPE_RULES.get(edge.edge_type, [])
        if not rules:
            continue  # no restrictions (e.g., related_to)

        pair = (source.type, target.type)
        if pair not in rules:
            expected = " or ".join(f"{s.value}->{t.value}" for s, t in rules)
            violations.append(
                f"{edge.edge_type.value} edge {source.id} -> {target.id}: "
                f"got {source.type.value}->{target.type.value}, expected {expected}"
            )

    if violations:
        return CheckResult(
            name="edge_type_semantics",
            dimension=DIMENSION,
            status=ValidationStatus.FAIL,
            message=f"{len(violations)} edge type semantic violation(s)",
            details=violations,
        )
    return CheckResult(
        name="edge_type_semantics",
        dimension=DIMENSION,
        status=ValidationStatus.PASS,
        message="All edge types connect appropriate node types",
    )


def check_node_id_format(graph: SystemGraph) -> CheckResult:
    """Node IDs should follow the type:identifier pattern."""
    malformed = []
    for node in graph.nodes:
        expected_prefix = f"{node.type.value}:"
        if not node.id.startswith(expected_prefix):
            malformed.append(
                f"Node '{node.id}' (type={node.type.value}) "
                f"should start with '{expected_prefix}'"
            )

    if malformed:
        return CheckResult(
            name="node_id_format",
            dimension=DIMENSION,
            status=ValidationStatus.WARN,
            message=f"{len(malformed)} node(s) with non-standard ID format",
            details=malformed,
        )
    return CheckResult(
        name="node_id_format",
        dimension=DIMENSION,
        status=ValidationStatus.PASS,
        message=f"All {len(graph.nodes)} node ID(s) follow type:identifier format",
    )


def check_duplicates(graph: SystemGraph) -> CheckResult:
    """No duplicate node IDs or duplicate edges."""
    issues = []

    node_ids = [n.id for n in graph.nodes]
    seen_node_ids: set[str] = set()
    for nid in node_ids:
        if nid in seen_node_ids:
            issues.append(f"Duplicate node ID: '{nid}'")
        seen_node_ids.add(nid)

    edge_keys = [
        (e.source_id, e.target_id, e.edge_type) for e in graph.edges
    ]
    seen_edge_keys: set[tuple] = set()
    for ek in edge_keys:
        if ek in seen_edge_keys:
            issues.append(
                f"Duplicate edge: {ek[0]} --{ek[2].value}--> {ek[1]}"
            )
        seen_edge_keys.add(ek)

    if issues:
        return CheckResult(
            name="duplicates",
            dimension=DIMENSION,
            status=ValidationStatus.WARN,
            message=f"{len(issues)} duplicate(s) found",
            details=issues,
        )
    return CheckResult(
        name="duplicates",
        dimension=DIMENSION,
        status=ValidationStatus.PASS,
        message="No duplicate nodes or edges",
    )


def check_required_fields(graph: SystemGraph) -> CheckResult:
    """Verb nodes must have http_method and http_path. All nodes must have names."""
    issues = []

    for node in graph.nodes:
        if not node.name:
            issues.append(f"Node '{node.id}' has no name")

        if node.type == NodeType.VERB:
            if not node.http_method:
                issues.append(f"Verb node '{node.id}' missing http_method")
            if not node.http_path:
                issues.append(f"Verb node '{node.id}' missing http_path")

    if issues:
        return CheckResult(
            name="required_fields",
            dimension=DIMENSION,
            status=ValidationStatus.FAIL,
            message=f"{len(issues)} required field(s) missing",
            details=issues,
        )
    return CheckResult(
        name="required_fields",
        dimension=DIMENSION,
        status=ValidationStatus.PASS,
        message="All required fields present",
    )


def validate_graph_consistency(graph: SystemGraph) -> list[CheckResult]:
    """Run all graph consistency checks.

    Returns a list of CheckResult objects, one per check.
    """
    return [
        check_orphaned_edges(graph),
        check_edge_type_semantics(graph),
        check_node_id_format(graph),
        check_duplicates(graph),
        check_required_fields(graph),
    ]
