"""Report generation for DocZot dashboard.

Generates formatted markdown reports from analysis session data:
- Coverage report: overall coverage summary
- Missing docs report: list of missing documentation with suggested outlines
- Sprint plan: prioritized task list for documentation work
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional


def generate_coverage_report(session: dict) -> str:
    """Generate a markdown coverage summary report.

    Args:
        session: Session dict from ManifestStore.load_session()

    Returns:
        Markdown string
    """
    product = session.get("product_name", "Unknown")
    drift = _parse_json(session.get("drift_json"))
    itm = _parse_json(session.get("itm_json"))
    atm = _parse_json(session.get("atm_json"))

    items = drift.get("drift_items", []) if drift else []
    complete = sum(1 for i in items if i["status"] == "complete")
    partial = sum(1 for i in items if i["status"] == "partial")
    missing = sum(1 for i in items if i["status"] == "missing")
    total = len(items) or 1
    pct = round((complete + partial * 0.5) / total * 100, 1)

    itm_topics = itm.get("topics", []) if itm else []
    atm_topics = atm.get("topics", []) if atm else []

    lines = [
        f"# Documentation Coverage Report: {product}",
        f"",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Overall Coverage | **{pct}%** |",
        f"| Complete Topics | {complete} |",
        f"| Partial Topics | {partial} |",
        f"| Missing Topics | {missing} |",
        f"| Total Checklist Topics | {len(itm_topics)} |",
        f"| Discovered Doc Topics | {len(atm_topics)} |",
        f"",
        f"## Coverage by Status",
        f"",
    ]

    # Complete topics
    complete_items = [i for i in items if i["status"] == "complete"]
    if complete_items:
        lines.append("### Complete")
        lines.append("")
        for item in complete_items:
            lines.append(f"- {item['matrix_topic_name']}")
        lines.append("")

    # Partial topics
    partial_items = [i for i in items if i["status"] == "partial"]
    if partial_items:
        lines.append("### Partial")
        lines.append("")
        for item in partial_items:
            missing_count = len(item.get("missing_node_ids", []))
            issues = item.get("quality_issues", [])
            detail = f" ({missing_count} missing elements" if missing_count else ""
            if issues:
                detail += ", " + ", ".join(issues)
            detail += ")" if detail else ""
            lines.append(f"- {item['matrix_topic_name']}{detail}")
        lines.append("")

    # Missing topics
    missing_items = [i for i in items if i["status"] == "missing"]
    if missing_items:
        lines.append("### Missing")
        lines.append("")
        for item in missing_items:
            lines.append(f"- {item['matrix_topic_name']}")
        lines.append("")

    return "\n".join(lines)


def generate_missing_docs_report(session: dict) -> str:
    """Generate a report of missing documentation with suggested outlines.

    Args:
        session: Session dict from ManifestStore.load_session()

    Returns:
        Markdown string
    """
    product = session.get("product_name", "Unknown")
    drift = _parse_json(session.get("drift_json"))

    items = drift.get("drift_items", []) if drift else []
    missing_items = [i for i in items if i["status"] in ("missing", "partial")]

    lines = [
        f"# Missing Documentation: {product}",
        f"",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"Found **{len(missing_items)}** topics needing documentation.",
        f"",
    ]

    for i, item in enumerate(sorted(missing_items, key=lambda x: x.get("priority", 0), reverse=True), 1):
        name = item["matrix_topic_name"]
        status = item["status"]
        action = item.get("action", "")
        missing_nodes = item.get("missing_node_ids", [])
        quality_issues = item.get("quality_issues", [])

        lines.append(f"## {i}. {name}")
        lines.append(f"")
        lines.append(f"**Status**: {status}")
        if action:
            lines.append(f"**Action**: {action}")
        lines.append(f"")

        if missing_nodes:
            lines.append("**Missing coverage for:**")
            for node_id in missing_nodes:
                lines.append(f"- `{node_id}`")
            lines.append("")

        if quality_issues:
            lines.append("**Quality issues:**")
            for issue in quality_issues:
                lines.append(f"- {issue}")
            lines.append("")

        # Suggested outline
        lines.append("**Suggested outline:**")
        lines.append("")
        lines.append(f"```markdown")
        lines.append(f"# {name}")
        lines.append(f"")
        lines.append(f"## Overview")
        lines.append(f"Brief description of {name.lower()}.")
        lines.append(f"")
        if missing_nodes:
            # Group by type
            verb_nodes = [n for n in missing_nodes if n.startswith("verb:")]
            noun_nodes = [n for n in missing_nodes if n.startswith("noun:")]

            if noun_nodes:
                for n in noun_nodes:
                    entity = n.split(":")[-1] if ":" in n else n
                    lines.append(f"## {entity.replace('_', ' ').title()}")
                    lines.append(f"Description of the {entity} entity.")
                    lines.append(f"")

            if verb_nodes:
                lines.append(f"## API Reference")
                lines.append(f"")
                for v in verb_nodes:
                    parts = v.split(":")
                    if len(parts) >= 3:
                        method = parts[1]
                        path = ":".join(parts[2:])
                        lines.append(f"### {method} {path}")
                    else:
                        lines.append(f"### {v}")
                    lines.append(f"Description, parameters, response, errors.")
                    lines.append(f"")

        lines.append(f"## Examples")
        lines.append(f"```")
        lines.append(f"")

    return "\n".join(lines)


def generate_sprint_plan(session: dict) -> str:
    """Generate a prioritized sprint plan for documentation work.

    Args:
        session: Session dict from ManifestStore.load_session()

    Returns:
        Markdown string
    """
    product = session.get("product_name", "Unknown")
    drift = _parse_json(session.get("drift_json"))

    items = drift.get("drift_items", []) if drift else []
    actionable = [i for i in items if i["status"] in ("missing", "partial")]

    # Sort by priority (higher first), then by status (missing before partial)
    actionable.sort(key=lambda x: (x.get("priority", 0), x["status"] == "missing"), reverse=True)

    lines = [
        f"# Documentation Sprint Plan: {product}",
        f"",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"**{len(actionable)} items** to address.",
        f"",
        f"## Priority Tasks",
        f"",
        f"| # | Topic | Status | Missing | Action |",
        f"|---|-------|--------|---------|--------|",
    ]

    for i, item in enumerate(actionable, 1):
        name = item["matrix_topic_name"]
        status = item["status"]
        missing_count = len(item.get("missing_node_ids", []))
        action = item.get("action", "")
        lines.append(f"| {i} | {name} | {status} | {missing_count} | {action} |")

    lines.append("")

    # Detailed breakdown
    lines.append("## Detailed Breakdown")
    lines.append("")

    for i, item in enumerate(actionable, 1):
        name = item["matrix_topic_name"]
        lines.append(f"### {i}. {name}")
        lines.append(f"")

        if item.get("action"):
            lines.append(f"- **Action**: {item['action']}")

        missing_nodes = item.get("missing_node_ids", [])
        if missing_nodes:
            lines.append(f"- **Missing nodes**: {', '.join(f'`{n}`' for n in missing_nodes)}")

        quality_issues = item.get("quality_issues", [])
        if quality_issues:
            lines.append(f"- **Quality issues**: {', '.join(quality_issues)}")

        lines.append("")

    return "\n".join(lines)


def _parse_json(value: Optional[str | dict]) -> Optional[dict]:
    """Parse a JSON string or return dict as-is."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None
