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
