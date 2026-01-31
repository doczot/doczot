"""Unit tests for Phase 2 quality assessment.

Tests:
- TopicQuality constraint field population
- Constraint coverage gap detection in drift report
- Terminology consistency checking
"""

import pytest
from doczot_analyzer.analyzer_v2 import _check_terminology_consistency
from doczot_analyzer.models_v2 import (
    TopicQuality,
    SystemGraph,
    SystemNode,
    SystemEdge,
    NodeType,
    NodeClass,
    EdgeType,
    ConfidenceLevel,
    TopicManifest,
    ManifestType,
    Topic,
    TopicType,
    DriftItem,
    DriftReport,
    compute_drift_report,
)


class TestTerminologyConsistency:
    """Test terminology consistency checking."""

    def _make_graph(self, noun_names: list[str]) -> SystemGraph:
        nodes = []
        for name in noun_names:
            nodes.append(SystemNode(
                id=f"noun:{name}",
                type=NodeType.NOUN,
                name=name,
            ))
        return SystemGraph(
            product_name="test",
            source_paths=["test"],
            nodes=nodes,
            edges=[],
        )

    def test_consistent_terminology(self):
        """No issues when docs use the same terms as code."""
        graph = self._make_graph(["user", "project"])
        graph_nouns = {n.name.lower() for n in graph.nodes if n.type == NodeType.NOUN}
        issues = _check_terminology_consistency(
            "The user can create a project.",
            graph_nouns,
            {"noun:user", "noun:project"},
            graph,
        )
        assert issues == []

    def test_detects_variant_usage(self):
        """Flags when docs use a known variant of a graph noun."""
        graph = self._make_graph(["user"])
        graph_nouns = {n.name.lower() for n in graph.nodes if n.type == NodeType.NOUN}
        issues = _check_terminology_consistency(
            "Each account has a unique identifier.",
            graph_nouns,
            {"noun:user"},
            graph,
        )
        assert len(issues) > 0
        assert any("account" in i and "user" in i for i in issues)

    def test_no_false_positive_for_uncovered_nouns(self):
        """Don't flag nouns that aren't covered by this topic."""
        graph = self._make_graph(["user", "project"])
        graph_nouns = {n.name.lower() for n in graph.nodes if n.type == NodeType.NOUN}
        # Only project is covered, so no user consistency check
        issues = _check_terminology_consistency(
            "Each account has projects.",
            graph_nouns,
            {"noun:project"},
            graph,
        )
        # "account" variant of "user" shouldn't be flagged since user isn't covered
        assert not any("user" in i for i in issues)

    def test_consistent_when_noun_present(self):
        """No issue when the canonical noun name appears in docs."""
        graph = self._make_graph(["task"])
        graph_nouns = {n.name.lower() for n in graph.nodes if n.type == NodeType.NOUN}
        issues = _check_terminology_consistency(
            "Each task can be assigned to a user.",
            graph_nouns,
            {"noun:task"},
            graph,
        )
        assert issues == []


class TestTopicQualityFields:
    """Test that TopicQuality model has all Phase 2 fields."""

    def test_constraint_fields_exist(self):
        """TopicQuality should have all constraint coverage fields."""
        q = TopicQuality()
        assert hasattr(q, 'has_auth_requirements')
        assert hasattr(q, 'has_rate_limits')
        assert hasattr(q, 'has_prerequisites')

    def test_agent_navigability_fields_exist(self):
        """TopicQuality should have agent navigability fields."""
        q = TopicQuality()
        assert hasattr(q, 'has_machine_readable_spec')
        assert hasattr(q, 'terminology_consistent')

    def test_score_fields_exist(self):
        """TopicQuality should have all score fields."""
        q = TopicQuality()
        assert hasattr(q, 'coverage_score')
        assert hasattr(q, 'constraint_score')
        assert hasattr(q, 'agent_readiness_score')

    def test_defaults_are_safe(self):
        """Default values should indicate 'not assessed'."""
        q = TopicQuality()
        assert q.has_prerequisites == "no"
        assert q.has_machine_readable_spec is False
        assert q.terminology_consistent is False
        assert q.constraint_score == 0.0
        assert q.agent_readiness_score == 0.0


class TestConstraintGapDetection:
    """Test that drift report detects constraint documentation gaps."""

    def _make_graph_with_constraints(self) -> SystemGraph:
        """Create a graph where verb has auth + rate limit constraints."""
        nodes = [
            SystemNode(
                id="verb:GET:/users",
                type=NodeType.VERB,
                name="list_users",
                http_method="GET",
                http_path="/users",
            ),
            SystemNode(
                id="noun:user",
                type=NodeType.NOUN,
                name="user",
            ),
            SystemNode(
                id="constraint:auth_required:verb:GET:/users",
                type=NodeType.CONSTRAINT,
                name="auth_required",
                description="Authentication required",
            ),
            SystemNode(
                id="constraint:rate_limit:verb:GET:/users",
                type=NodeType.CONSTRAINT,
                name="rate_limit",
                description="Rate limited to 100/hour",
            ),
        ]
        edges = [
            SystemEdge(
                source_id="verb:GET:/users",
                target_id="noun:user",
                edge_type=EdgeType.OPERATES_ON,
            ),
            SystemEdge(
                source_id="verb:GET:/users",
                target_id="constraint:auth_required:verb:GET:/users",
                edge_type=EdgeType.CONSTRAINED_BY,
            ),
            SystemEdge(
                source_id="verb:GET:/users",
                target_id="constraint:rate_limit:verb:GET:/users",
                edge_type=EdgeType.CONSTRAINED_BY,
            ),
        ]
        return SystemGraph(
            product_name="test",
            source_paths=["test"],
            nodes=nodes,
            edges=edges,
        )

    def test_flags_missing_auth_docs(self):
        """Drift report should flag auth-protected endpoints without auth docs."""
        graph = self._make_graph_with_constraints()

        # Matrix says we need docs for users
        matrix = TopicManifest(
            manifest_type=ManifestType.INTENDED,
            graph_id="test",
            product_name="test",
            topics=[Topic(
                id="itm_1",
                name="User Management",
                topic_type=TopicType.REFERENCE,
                covers=["verb:GET:/users", "noun:user"],
            )],
        )

        # Inventory has docs but no auth/rate limit mention
        inventory = TopicManifest(
            manifest_type=ManifestType.ACTUAL,
            graph_id="test",
            product_name="test",
            topics=[Topic(
                id="atm_1",
                name="Users",
                topic_type=TopicType.REFERENCE,
                covers=["verb:GET:/users", "noun:user"],
            )],
            quality={
                "atm_1": TopicQuality(
                    has_description=True,
                    has_examples=True,
                    has_auth_requirements="no",
                    has_rate_limits="no",
                    terminology_consistent=True,
                ),
            },
        )

        report = compute_drift_report(graph, matrix, inventory)

        # Find the drift item for User Management
        user_item = next(d for d in report.drift_items if d.matrix_topic_name == "User Management")
        assert "auth-protected endpoint but no auth docs" in user_item.quality_issues
        assert "rate-limited endpoint but no rate limit docs" in user_item.quality_issues

    def test_no_flag_when_constraints_documented(self):
        """No constraint gap when docs mention auth and rate limits."""
        graph = self._make_graph_with_constraints()

        matrix = TopicManifest(
            manifest_type=ManifestType.INTENDED,
            graph_id="test",
            product_name="test",
            topics=[Topic(
                id="itm_1",
                name="User Management",
                topic_type=TopicType.REFERENCE,
                covers=["verb:GET:/users", "noun:user"],
            )],
        )

        inventory = TopicManifest(
            manifest_type=ManifestType.ACTUAL,
            graph_id="test",
            product_name="test",
            topics=[Topic(
                id="atm_1",
                name="Users",
                topic_type=TopicType.REFERENCE,
                covers=["verb:GET:/users", "noun:user"],
            )],
            quality={
                "atm_1": TopicQuality(
                    has_description=True,
                    has_examples=True,
                    has_auth_requirements="yes",
                    has_rate_limits="yes",
                    terminology_consistent=True,
                ),
            },
        )

        report = compute_drift_report(graph, matrix, inventory)
        user_item = next(d for d in report.drift_items if d.matrix_topic_name == "User Management")
        assert "auth-protected endpoint but no auth docs" not in user_item.quality_issues
        assert "rate-limited endpoint but no rate limit docs" not in user_item.quality_issues

    def test_flags_terminology_inconsistency(self):
        """Drift report should flag terminology issues."""
        graph = self._make_graph_with_constraints()

        matrix = TopicManifest(
            manifest_type=ManifestType.INTENDED,
            graph_id="test",
            product_name="test",
            topics=[Topic(
                id="itm_1",
                name="User Management",
                topic_type=TopicType.REFERENCE,
                covers=["verb:GET:/users", "noun:user"],
            )],
        )

        inventory = TopicManifest(
            manifest_type=ManifestType.ACTUAL,
            graph_id="test",
            product_name="test",
            topics=[Topic(
                id="atm_1",
                name="Users",
                topic_type=TopicType.REFERENCE,
                covers=["verb:GET:/users", "noun:user"],
            )],
            quality={
                "atm_1": TopicQuality(
                    has_description=True,
                    terminology_consistent=False,
                ),
            },
        )

        report = compute_drift_report(graph, matrix, inventory)
        user_item = next(d for d in report.drift_items if d.matrix_topic_name == "User Management")
        assert "inconsistent terminology with codebase" in user_item.quality_issues
