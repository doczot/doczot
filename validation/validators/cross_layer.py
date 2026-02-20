"""Cross-layer consistency validator.

Validates the full pipeline: Graph -> ITM -> ATM -> Drift.
Ensures node references are valid across layers and coverage math is correct.
"""
from __future__ import annotations

from doczot_analyzer.models_v2 import (
    SystemGraph,
    TopicManifest,
    DriftReport,
    NodeType,
    NodeClass,
)
from validation.models import (
    CheckResult,
    ValidationDimension,
    ValidationStatus,
)

DIMENSION = ValidationDimension.CROSS_LAYER


def check_itm_covers_valid_nodes(
    graph: SystemGraph,
    itm: TopicManifest,
) -> CheckResult:
    """Every ITM topic's covers list must reference valid graph node IDs."""
    node_ids = {n.id for n in graph.nodes}
    invalid_refs = []

    for topic in itm.topics:
        for covered_id in topic.covers:
            if covered_id not in node_ids:
                invalid_refs.append(
                    f"Topic '{topic.name}' covers '{covered_id}' "
                    f"which is not in the graph"
                )

    if invalid_refs:
        return CheckResult(
            name="itm_covers_valid_nodes",
            dimension=DIMENSION,
            status=ValidationStatus.FAIL,
            message=f"{len(invalid_refs)} invalid node reference(s) in ITM",
            details=invalid_refs,
        )
    return CheckResult(
        name="itm_covers_valid_nodes",
        dimension=DIMENSION,
        status=ValidationStatus.PASS,
        message="All ITM topic covers reference valid graph nodes",
    )


def check_no_vacuous_topics(itm: TopicManifest) -> CheckResult:
    """ITM topics should cover at least one graph node (no vacuous topics)."""
    vacuous = []
    for topic in itm.topics:
        # Skip container topics (parents with children)
        if topic.children:
            continue
        if not topic.covers:
            vacuous.append(f"Topic '{topic.name}' (id={topic.id}) covers no graph nodes")

    if vacuous:
        return CheckResult(
            name="no_vacuous_topics",
            dimension=DIMENSION,
            status=ValidationStatus.WARN,
            message=f"{len(vacuous)} leaf topic(s) cover no graph nodes",
            details=vacuous,
        )
    return CheckResult(
        name="no_vacuous_topics",
        dimension=DIMENSION,
        status=ValidationStatus.PASS,
        message="All leaf topics cover at least one graph node",
    )


def check_user_facing_coverage(
    graph: SystemGraph,
    itm: TopicManifest,
) -> CheckResult:
    """Every user-facing graph node should be covered by at least one ITM topic."""
    covered_ids = itm.covered_surface_ids()
    user_facing = [
        n for n in graph.nodes
        if n.node_class == NodeClass.USER_FACING
        and n.type in (NodeType.VERB, NodeType.NOUN)
    ]
    uncovered = [
        n.id for n in user_facing if n.id not in covered_ids
    ]

    if uncovered:
        return CheckResult(
            name="user_facing_coverage",
            dimension=DIMENSION,
            status=ValidationStatus.WARN,
            message=f"{len(uncovered)} user-facing node(s) not covered by any ITM topic",
            details=[f"Uncovered: {nid}" for nid in uncovered[:20]],
        )
    return CheckResult(
        name="user_facing_coverage",
        dimension=DIMENSION,
        status=ValidationStatus.PASS,
        message=f"All {len(user_facing)} user-facing nodes covered by ITM topics",
    )


def check_coverage_math(drift: DriftReport) -> CheckResult:
    """Coverage percentages from the drift report should be arithmetically correct."""
    stats = drift.coverage_stats()
    total = stats.get("total_topics", 0)
    reported_pct = stats.get("coverage_percentage", 0.0)

    if total == 0:
        if reported_pct == 0.0:
            return CheckResult(
                name="coverage_math",
                dimension=DIMENSION,
                status=ValidationStatus.PASS,
                message="No drift items, coverage correctly reported as 0%",
            )
        return CheckResult(
            name="coverage_math",
            dimension=DIMENSION,
            status=ValidationStatus.FAIL,
            message=f"No drift items but coverage reported as {reported_pct}%",
        )

    complete = stats.get("complete", 0)
    partial = stats.get("partial", 0)
    expected_pct = round((complete + partial * 0.5) / total * 100, 1)
    if abs(expected_pct - reported_pct) > 0.2:
        return CheckResult(
            name="coverage_math",
            dimension=DIMENSION,
            status=ValidationStatus.FAIL,
            message=(
                f"Coverage math mismatch: expected {expected_pct}% "
                f"but reported as {reported_pct}%"
            ),
        )
    return CheckResult(
        name="coverage_math",
        dimension=DIMENSION,
        status=ValidationStatus.PASS,
        message=f"Coverage math correct: {reported_pct}%",
    )


def check_atm_references_valid_nodes(
    graph: SystemGraph,
    atm: TopicManifest,
) -> CheckResult:
    """ATM topic covers lists should reference valid graph node IDs."""
    node_ids = {n.id for n in graph.nodes}
    invalid_refs = []

    for topic in atm.topics:
        for covered_id in topic.covers:
            if covered_id not in node_ids:
                invalid_refs.append(
                    f"ATM topic '{topic.name}' covers '{covered_id}' "
                    f"which is not in the graph"
                )

    if invalid_refs:
        return CheckResult(
            name="atm_references_valid_nodes",
            dimension=DIMENSION,
            status=ValidationStatus.FAIL,
            message=f"{len(invalid_refs)} invalid node reference(s) in ATM",
            details=invalid_refs,
        )
    return CheckResult(
        name="atm_references_valid_nodes",
        dimension=DIMENSION,
        status=ValidationStatus.PASS,
        message="All ATM topic covers reference valid graph nodes",
    )


def validate_cross_layer(
    graph: SystemGraph,
    itm: TopicManifest,
    atm: TopicManifest | None = None,
    drift: DriftReport | None = None,
) -> list[CheckResult]:
    """Run all cross-layer consistency checks.

    Args:
        graph: The SystemGraph.
        itm: The Intended Topic Manifest (Coverage Checklist).
        atm: The Actual Topic Manifest (Content Inventory), optional.
        drift: The DriftReport, optional. Used for coverage math validation.
    """
    results = [
        check_itm_covers_valid_nodes(graph, itm),
        check_no_vacuous_topics(itm),
        check_user_facing_coverage(graph, itm),
    ]
    if atm is not None:
        results.append(check_atm_references_valid_nodes(graph, atm))
    if drift is not None:
        results.append(check_coverage_math(drift))
    return results
