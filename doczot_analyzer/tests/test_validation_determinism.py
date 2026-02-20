"""Tests for determinism validator and golden file comparison."""
import json
from pathlib import Path

from doczot_analyzer.models_v2 import (
    SystemGraph,
    SystemNode,
    SystemEdge,
    NodeType,
    EdgeType,
)
from validation.validators.determinism import (
    _compare_graphs,
    validate_determinism_from_graphs,
)
from validation.golden.generate import (
    generate_simple_test_app_golden,
    load_golden_file,
    _graph_to_stable_dict,
)
from validation.models import ValidationStatus


def _verb(name: str, path: str, method: str = "GET") -> SystemNode:
    return SystemNode(
        id=f"verb:{method}:{path}",
        type=NodeType.VERB,
        name=name,
        http_method=method,
        http_path=path,
    )


def _noun(name: str) -> SystemNode:
    return SystemNode(
        id=f"noun:{name}",
        type=NodeType.NOUN,
        name=name,
    )


def _make_graph(nodes=None, edges=None) -> SystemGraph:
    return SystemGraph(product_name="test", nodes=nodes or [], edges=edges or [])


class TestCompareGraphs:
    def test_identical_graphs(self):
        nodes = [_verb("get_user", "/users"), _noun("user")]
        edges = [SystemEdge(
            source_id="verb:GET:/users",
            target_id="noun:user",
            edge_type=EdgeType.OPERATES_ON,
        )]
        a = _make_graph(nodes=nodes, edges=edges)
        b = _make_graph(nodes=nodes, edges=edges)
        diffs = _compare_graphs(a, b)
        assert len(diffs) == 0

    def test_different_nodes(self):
        a = _make_graph(nodes=[_noun("user")])
        b = _make_graph(nodes=[_noun("user"), _noun("project")])
        diffs = _compare_graphs(a, b)
        assert len(diffs) > 0
        assert any("noun:project" in d for d in diffs)

    def test_different_edges(self):
        verb = _verb("get_user", "/users")
        noun = _noun("user")
        edge = SystemEdge(
            source_id=verb.id,
            target_id=noun.id,
            edge_type=EdgeType.OPERATES_ON,
        )
        a = _make_graph(nodes=[verb, noun], edges=[])
        b = _make_graph(nodes=[verb, noun], edges=[edge])
        diffs = _compare_graphs(a, b)
        assert len(diffs) > 0

    def test_different_node_attributes(self):
        a = _make_graph(nodes=[SystemNode(
            id="verb:GET:/users", type=NodeType.VERB,
            name="get_user", http_method="GET", http_path="/users",
        )])
        b = _make_graph(nodes=[SystemNode(
            id="verb:GET:/users", type=NodeType.VERB,
            name="list_users", http_method="GET", http_path="/users",
        )])
        diffs = _compare_graphs(a, b)
        assert len(diffs) > 0
        assert any("name" in d for d in diffs)

    def test_empty_graphs(self):
        diffs = _compare_graphs(_make_graph(), _make_graph())
        assert len(diffs) == 0


class TestValidateDeterminism:
    def test_identical_graphs_pass(self):
        graph = _make_graph(nodes=[_noun("user")])
        results = validate_determinism_from_graphs(graph, graph)
        assert len(results) == 1
        assert results[0].status == ValidationStatus.PASS

    def test_different_graphs_fail(self):
        a = _make_graph(nodes=[_noun("user")])
        b = _make_graph(nodes=[_noun("user"), _noun("project")])
        results = validate_determinism_from_graphs(a, b)
        assert results[0].status == ValidationStatus.FAIL


class TestGoldenFile:
    def test_golden_file_exists(self):
        """The golden file for simple_test_app should exist."""
        golden_path = (
            Path(__file__).parent.parent.parent
            / "validation" / "golden" / "simple_test_app.json"
        )
        assert golden_path.exists(), f"Golden file missing: {golden_path}"

    def test_golden_matches_current_scan(self):
        """Current scanner output should match the golden file."""
        golden = load_golden_file("simple_test_app")
        current = generate_simple_test_app_golden()

        # Compare node IDs
        golden_node_ids = sorted(n["id"] for n in golden["nodes"])
        current_node_ids = sorted(n["id"] for n in current["nodes"])
        assert golden_node_ids == current_node_ids, (
            f"Node IDs differ.\n"
            f"  Golden: {golden_node_ids}\n"
            f"  Current: {current_node_ids}"
        )

        # Compare edge keys
        golden_edge_keys = sorted(
            (e["source_id"], e["target_id"], e["edge_type"])
            for e in golden["edges"]
        )
        current_edge_keys = sorted(
            (e["source_id"], e["target_id"], e["edge_type"])
            for e in current["edges"]
        )
        assert golden_edge_keys == current_edge_keys, (
            f"Edge keys differ.\n"
            f"  Golden: {golden_edge_keys}\n"
            f"  Current: {current_edge_keys}"
        )

    def test_golden_has_expected_fixture_nodes(self):
        """Sanity check: golden file should contain known fixture elements."""
        golden = load_golden_file("simple_test_app")
        node_ids = {n["id"] for n in golden["nodes"]}

        # The simple_test_app fixture has these endpoints
        assert "verb:GET:/health" in node_ids
        assert "verb:POST:/auth/login" in node_ids
        assert "verb:GET:/items" in node_ids
        assert "noun:user" in node_ids
        assert "noun:item" in node_ids
