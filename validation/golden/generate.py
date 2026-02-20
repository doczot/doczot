"""Generate golden files from known fixtures.

Golden files capture the expected SystemGraph output for test fixtures,
enabling regression detection when scanner or analyzer behavior changes.
"""
from __future__ import annotations

import json
from pathlib import Path

from doczot_analyzer.scanner import scan_python_file
from doczot_analyzer.analyzer_v2 import build_system_graph_python
from doczot_analyzer.models_v2 import SystemGraph, SystemNode, SystemEdge, NodeType, EdgeType

GOLDEN_DIR = Path(__file__).parent
FIXTURES_DIR = Path(__file__).parent.parent.parent / "doczot_analyzer" / "tests" / "fixtures"


def _graph_to_stable_dict(graph: SystemGraph) -> dict:
    """Convert a SystemGraph to a JSON-serializable dict with stable ordering.

    Strips the scanned_at timestamp and sorts nodes/edges for deterministic output.
    Also normalizes source_paths to be relative.
    """
    data = graph.model_dump(mode="json")
    data.pop("scanned_at", None)
    # Normalize source paths to relative
    data["source_paths"] = [
        str(Path(p).name) if "/" in p else p
        for p in data.get("source_paths", [])
    ]
    data["nodes"] = sorted(data["nodes"], key=lambda n: n["id"])
    data["edges"] = sorted(
        data["edges"],
        key=lambda e: (e["source_id"], e["target_id"], e["edge_type"]),
    )
    return data


def generate_simple_test_app_golden() -> dict:
    """Generate golden file for the simple_test_app fixture.

    Uses scan_python_file directly (since the fixture lives under tests/
    which scan_directory intentionally skips).
    """
    fixture_dir = FIXTURES_DIR / "simple_test_app"
    source = (fixture_dir / "main.py").read_text()
    endpoints = scan_python_file(source, "main.py")

    # Build graph using the same logic as build_system_graph_python
    # but from pre-scanned endpoints
    from doczot_analyzer.analyzer_v2 import (
        extract_nouns_from_path,
        HTTP_METHOD_TO_VERB,
    )
    from doczot_analyzer.models_v2 import NodeClass, ConfidenceLevel

    nodes: list[SystemNode] = []
    edges: list[SystemEdge] = []
    seen_nouns: set[str] = set()

    for ep in endpoints:
        base_verb = HTTP_METHOD_TO_VERB.get(ep.method, ep.method.lower())
        path_segments = [s for s in ep.path.split("/") if s and not s.startswith("{")]
        resource = path_segments[-1] if path_segments else "resource"
        verb_name = f"{base_verb}_{resource}"

        verb_node = SystemNode(
            id=f"verb:{ep.method}:{ep.path}",
            type=NodeType.VERB,
            name=verb_name,
            description=ep.docstring,
            source_file=ep.file_path,
            source_line=ep.line_number,
            code_signature=f"{ep.method} {ep.path}",
            http_method=ep.method,
            http_path=ep.path,
        )
        nodes.append(verb_node)

        path_nouns = extract_nouns_from_path(ep.path)
        for noun_name in path_nouns:
            noun_id = f"noun:{noun_name}"
            if noun_name not in seen_nouns:
                noun_node = SystemNode(
                    id=noun_id,
                    type=NodeType.NOUN,
                    name=noun_name,
                )
                nodes.append(noun_node)
                seen_nouns.add(noun_name)

            edges.append(SystemEdge(
                source_id=verb_node.id,
                target_id=noun_id,
                edge_type=EdgeType.OPERATES_ON,
            ))

    graph = SystemGraph(
        product_name="simple-test-app",
        source_paths=["simple_test_app"],
        nodes=nodes,
        edges=edges,
    )
    return _graph_to_stable_dict(graph)


def regenerate_golden_files() -> list[str]:
    """Regenerate all golden files. Returns list of updated file paths."""
    updated = []

    # simple_test_app
    golden_path = GOLDEN_DIR / "simple_test_app.json"
    data = generate_simple_test_app_golden()
    golden_path.write_text(json.dumps(data, indent=2) + "\n")
    updated.append(str(golden_path))

    return updated


def load_golden_file(name: str) -> dict:
    """Load a golden file by name (without .json extension)."""
    path = GOLDEN_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Golden file not found: {path}")
    return json.loads(path.read_text())


if __name__ == "__main__":
    updated = regenerate_golden_files()
    for path in updated:
        print(f"Updated: {path}")
