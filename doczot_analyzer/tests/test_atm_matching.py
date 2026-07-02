"""Tests for Content Inventory (ATM) matching strategies.

Covers the deterministic title-match strategy that credits doc sections
titled after nouns/concepts even when the section prose is short
(regression: thin-but-real READMEs used to report 0% coverage).
"""

from doczot_analyzer.analyzer_v2 import _match_title_to_nodes
from doczot_analyzer.models_v2 import NodeClass, NodeType, SystemNode


def _noun(name: str) -> SystemNode:
    return SystemNode(
        id=f"noun:{name}", type=NodeType.NOUN, name=name,
        node_class=NodeClass.USER_FACING,
    )


def _concept(name: str) -> SystemNode:
    return SystemNode(
        id=f"concept:{name}", type=NodeType.CONCEPT, name=name,
        node_class=NodeClass.USER_FACING,
    )


def _verb(name: str) -> SystemNode:
    return SystemNode(
        id=f"verb:GET:/{name}", type=NodeType.VERB, name=name,
        node_class=NodeClass.USER_FACING,
        http_method="GET", http_path=f"/{name}",
    )


class TestMatchTitleToNodes:
    def test_plural_section_title_matches_singular_noun(self):
        nodes = [_noun("user"), _noun("item")]
        matched = _match_title_to_nodes("Users", nodes)
        assert [n.name for n in matched] == ["user"]

    def test_exact_concept_title_match_case_insensitive(self):
        nodes = [_concept("rate limiting"), _concept("authentication")]
        matched = _match_title_to_nodes("Rate Limiting", nodes)
        assert [n.name for n in matched] == ["rate limiting"]

    def test_plural_concept_name_matches_singular_title(self):
        # Concepts mined from docs are sometimes stored in plural form
        nodes = [_concept("projects")]
        matched = _match_title_to_nodes("Project", nodes)
        assert len(matched) == 1

    def test_verbs_are_never_title_matched(self):
        nodes = [_verb("users")]
        assert _match_title_to_nodes("Users", nodes) == []

    def test_unrelated_title_matches_nothing(self):
        nodes = [_noun("user"), _concept("authentication")]
        assert _match_title_to_nodes("Deployment Guide", nodes) == []

    def test_empty_title_matches_nothing(self):
        nodes = [_noun("user")]
        assert _match_title_to_nodes("", nodes) == []
        assert _match_title_to_nodes("   ", nodes) == []


class TestEmptyResultDiagnostics:
    """Empty analyses must explain themselves via diagnostics fields."""

    def test_graph_diagnostics_populated_for_empty_scan(self, tmp_path):
        from doczot_analyzer.analyzer_v2 import build_system_graph

        (tmp_path / "util.py").write_text("x = 1\n")
        graph = build_system_graph(str(tmp_path), product_name="empty-app")

        assert graph.verbs == []
        scan = graph.diagnostics["scan"]
        assert scan["files_seen"] == 1
        assert scan["files_scanned"] == 1
        assert scan["files_with_endpoints"] == 0

    def test_inventory_diagnostics_when_no_docs(self, tmp_path):
        from doczot_analyzer.analyzer_v2 import (
            build_system_graph, discover_content_inventory,
        )

        (tmp_path / "util.py").write_text("x = 1\n")
        graph = build_system_graph(str(tmp_path), product_name="empty-app")
        inventory = discover_content_inventory(str(tmp_path), graph)

        assert inventory.topics == []
        assert inventory.diagnostics["doc_files_found"] == 0
        assert inventory.diagnostics["sections_parsed"] == 0
