"""Tests for the cross-layer consistency validator."""
from doczot_analyzer.models_v2 import (
    SystemGraph,
    SystemNode,
    SystemEdge,
    NodeType,
    NodeClass,
    EdgeType,
    TopicType,
    TopicManifest,
    ManifestType,
    Topic,
    DriftReport,
    DriftItem,
)
from validation.validators.cross_layer import (
    check_itm_covers_valid_nodes,
    check_no_vacuous_topics,
    check_user_facing_coverage,
    check_coverage_math,
    check_atm_references_valid_nodes,
    validate_cross_layer,
)
from validation.models import ValidationStatus


def _verb(name: str, path: str, method: str = "GET") -> SystemNode:
    return SystemNode(
        id=f"verb:{method}:{path}",
        type=NodeType.VERB,
        name=name,
        http_method=method,
        http_path=path,
        node_class=NodeClass.USER_FACING,
    )


def _noun(name: str) -> SystemNode:
    return SystemNode(
        id=f"noun:{name}",
        type=NodeType.NOUN,
        name=name,
        node_class=NodeClass.USER_FACING,
    )


def _make_graph(nodes=None, edges=None) -> SystemGraph:
    return SystemGraph(
        product_name="test",
        nodes=nodes or [],
        edges=edges or [],
    )


def _make_topic(
    name: str,
    covers: list[str] | None = None,
    children: list[str] | None = None,
) -> Topic:
    return Topic(
        id=f"topic:{name}",
        name=name,
        topic_type=TopicType.REFERENCE,
        covers=covers or [],
        children=children or [],
    )


def _make_manifest(topics: list[Topic]) -> TopicManifest:
    return TopicManifest(
        product_name="test",
        manifest_type=ManifestType.INTENDED,
        graph_id="test-graph",
        topics=topics,
    )


def _make_drift(items: list[DriftItem]) -> DriftReport:
    return DriftReport(
        product_name="test",
        graph_id="test-graph",
        matrix_id="test-itm",
        inventory_id="test-atm",
        drift_items=items,
    )


class TestITMCoversValidNodes:
    def test_valid_references(self):
        verb = _verb("get_user", "/users")
        graph = _make_graph(nodes=[verb])
        itm = _make_manifest([_make_topic("Get User", covers=[verb.id])])
        result = check_itm_covers_valid_nodes(graph, itm)
        assert result.status == ValidationStatus.PASS

    def test_invalid_reference(self):
        graph = _make_graph(nodes=[_verb("get_user", "/users")])
        itm = _make_manifest([_make_topic("Ghost", covers=["verb:GET:/ghost"])])
        result = check_itm_covers_valid_nodes(graph, itm)
        assert result.status == ValidationStatus.FAIL
        assert "verb:GET:/ghost" in result.details[0]

    def test_empty_covers(self):
        graph = _make_graph(nodes=[_verb("get_user", "/users")])
        itm = _make_manifest([_make_topic("Empty", covers=[])])
        result = check_itm_covers_valid_nodes(graph, itm)
        assert result.status == ValidationStatus.PASS


class TestNoVacuousTopics:
    def test_leaf_with_covers(self):
        itm = _make_manifest([_make_topic("Get User", covers=["verb:GET:/users"])])
        result = check_no_vacuous_topics(itm)
        assert result.status == ValidationStatus.PASS

    def test_leaf_without_covers(self):
        itm = _make_manifest([_make_topic("Empty Leaf", covers=[])])
        result = check_no_vacuous_topics(itm)
        assert result.status == ValidationStatus.WARN

    def test_parent_without_covers_ok(self):
        """Parent topics with children are allowed to have empty covers."""
        parent = _make_topic("Parent", covers=[], children=["topic:Child"])
        itm = _make_manifest([parent])
        result = check_no_vacuous_topics(itm)
        assert result.status == ValidationStatus.PASS


class TestUserFacingCoverage:
    def test_all_covered(self):
        verb = _verb("get_user", "/users")
        noun = _noun("user")
        graph = _make_graph(nodes=[verb, noun])
        itm = _make_manifest([
            _make_topic("Get User", covers=[verb.id]),
            _make_topic("User Concept", covers=[noun.id]),
        ])
        result = check_user_facing_coverage(graph, itm)
        assert result.status == ValidationStatus.PASS

    def test_uncovered_node(self):
        verb = _verb("get_user", "/users")
        noun = _noun("user")
        graph = _make_graph(nodes=[verb, noun])
        itm = _make_manifest([_make_topic("Get User", covers=[verb.id])])
        result = check_user_facing_coverage(graph, itm)
        assert result.status == ValidationStatus.WARN
        assert "noun:user" in result.details[0]

    def test_internal_nodes_excluded(self):
        """Internal nodes don't need ITM coverage."""
        internal = SystemNode(
            id="verb:GET:/internal",
            type=NodeType.VERB,
            name="internal_check",
            http_method="GET",
            http_path="/internal",
            node_class=NodeClass.INTERNAL,
        )
        graph = _make_graph(nodes=[internal])
        itm = _make_manifest([])
        result = check_user_facing_coverage(graph, itm)
        assert result.status == ValidationStatus.PASS


class TestCoverageMath:
    def test_correct_percentage(self):
        drift = _make_drift([
            DriftItem(
                matrix_topic_id="t1", matrix_topic_name="A",
                status="complete",
            ),
            DriftItem(
                matrix_topic_id="t2", matrix_topic_name="B",
                status="missing",
            ),
        ])
        result = check_coverage_math(drift)
        assert result.status == ValidationStatus.PASS

    def test_empty_drift(self):
        drift = _make_drift([])
        result = check_coverage_math(drift)
        assert result.status == ValidationStatus.PASS

    def test_all_complete(self):
        drift = _make_drift([
            DriftItem(
                matrix_topic_id="t1", matrix_topic_name="A",
                status="complete",
            ),
        ])
        result = check_coverage_math(drift)
        assert result.status == ValidationStatus.PASS
        assert "100.0%" in result.message


class TestATMReferencesValidNodes:
    def test_valid_atm(self):
        verb = _verb("get_user", "/users")
        graph = _make_graph(nodes=[verb])
        atm = _make_manifest([_make_topic("Get User Doc", covers=[verb.id])])
        result = check_atm_references_valid_nodes(graph, atm)
        assert result.status == ValidationStatus.PASS

    def test_invalid_atm_reference(self):
        graph = _make_graph(nodes=[_verb("get_user", "/users")])
        atm = _make_manifest([_make_topic("Ghost Doc", covers=["verb:GET:/ghost"])])
        result = check_atm_references_valid_nodes(graph, atm)
        assert result.status == ValidationStatus.FAIL


class TestValidateAll:
    def test_full_pipeline(self):
        verb = _verb("get_user", "/users")
        noun = _noun("user")
        graph = _make_graph(nodes=[verb, noun])
        itm = _make_manifest([
            _make_topic("Get User", covers=[verb.id]),
            _make_topic("User Concept", covers=[noun.id]),
        ])
        atm = _make_manifest([
            _make_topic("User Docs", covers=[verb.id]),
        ])
        drift = _make_drift([
            DriftItem(
                matrix_topic_id="t1", matrix_topic_name="Get User",
                status="complete",
            ),
        ])
        results = validate_cross_layer(graph, itm, atm, drift)
        assert len(results) == 5  # 3 ITM + 1 ATM + 1 drift
        assert all(
            r.status in (ValidationStatus.PASS, ValidationStatus.WARN)
            for r in results
        )

    def test_without_atm_or_drift(self):
        verb = _verb("get_user", "/users")
        graph = _make_graph(nodes=[verb])
        itm = _make_manifest([_make_topic("Get User", covers=[verb.id])])
        results = validate_cross_layer(graph, itm)
        assert len(results) == 3  # ITM checks only
