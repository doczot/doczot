"""Tests for the graph consistency validator."""
from doczot_analyzer.models_v2 import (
    SystemGraph,
    SystemNode,
    SystemEdge,
    NodeType,
    NodeClass,
    EdgeType,
    ConfidenceLevel,
)
from validation.validators.graph_consistency import (
    check_orphaned_edges,
    check_edge_type_semantics,
    check_node_id_format,
    check_duplicates,
    check_required_fields,
    validate_graph_consistency,
)
from validation.models import ValidationStatus


def _make_graph(nodes=None, edges=None) -> SystemGraph:
    return SystemGraph(
        product_name="test",
        nodes=nodes or [],
        edges=edges or [],
    )


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


def _constraint(name: str) -> SystemNode:
    return SystemNode(
        id=f"constraint:{name}",
        type=NodeType.CONSTRAINT,
        name=name,
    )


def _edge(source: str, target: str, edge_type: EdgeType) -> SystemEdge:
    return SystemEdge(
        source_id=source,
        target_id=target,
        edge_type=edge_type,
    )


class TestOrphanedEdges:
    def test_no_edges(self):
        graph = _make_graph(nodes=[_noun("user")])
        result = check_orphaned_edges(graph)
        assert result.status == ValidationStatus.PASS

    def test_valid_edges(self):
        verb = _verb("get_user", "/users", "GET")
        noun = _noun("user")
        edge = _edge(verb.id, noun.id, EdgeType.OPERATES_ON)
        graph = _make_graph(nodes=[verb, noun], edges=[edge])
        result = check_orphaned_edges(graph)
        assert result.status == ValidationStatus.PASS

    def test_orphaned_source(self):
        noun = _noun("user")
        edge = _edge("verb:GET:/missing", noun.id, EdgeType.OPERATES_ON)
        graph = _make_graph(nodes=[noun], edges=[edge])
        result = check_orphaned_edges(graph)
        assert result.status == ValidationStatus.FAIL
        assert "verb:GET:/missing" in result.details[0]

    def test_orphaned_target(self):
        verb = _verb("get_user", "/users", "GET")
        edge = _edge(verb.id, "noun:missing", EdgeType.OPERATES_ON)
        graph = _make_graph(nodes=[verb], edges=[edge])
        result = check_orphaned_edges(graph)
        assert result.status == ValidationStatus.FAIL
        assert "noun:missing" in result.details[0]


class TestEdgeTypeSemantics:
    def test_valid_operates_on(self):
        verb = _verb("get_user", "/users")
        noun = _noun("user")
        edge = _edge(verb.id, noun.id, EdgeType.OPERATES_ON)
        graph = _make_graph(nodes=[verb, noun], edges=[edge])
        result = check_edge_type_semantics(graph)
        assert result.status == ValidationStatus.PASS

    def test_invalid_operates_on(self):
        """operates_on should go verb->noun, not noun->verb."""
        verb = _verb("get_user", "/users")
        noun = _noun("user")
        edge = _edge(noun.id, verb.id, EdgeType.OPERATES_ON)
        graph = _make_graph(nodes=[verb, noun], edges=[edge])
        result = check_edge_type_semantics(graph)
        assert result.status == ValidationStatus.FAIL

    def test_valid_part_of(self):
        project = _noun("project")
        user = _noun("user")
        edge = _edge(project.id, user.id, EdgeType.PART_OF)
        graph = _make_graph(nodes=[project, user], edges=[edge])
        result = check_edge_type_semantics(graph)
        assert result.status == ValidationStatus.PASS

    def test_invalid_constrained_by(self):
        """constrained_by should go verb->constraint, not noun->constraint."""
        noun = _noun("user")
        constraint = _constraint("auth_required")
        edge = _edge(noun.id, constraint.id, EdgeType.CONSTRAINED_BY)
        graph = _make_graph(nodes=[noun, constraint], edges=[edge])
        result = check_edge_type_semantics(graph)
        assert result.status == ValidationStatus.FAIL

    def test_related_to_allows_any(self):
        noun1 = _noun("user")
        noun2 = _noun("project")
        edge = _edge(noun1.id, noun2.id, EdgeType.RELATED_TO)
        graph = _make_graph(nodes=[noun1, noun2], edges=[edge])
        result = check_edge_type_semantics(graph)
        assert result.status == ValidationStatus.PASS


class TestNodeIdFormat:
    def test_correct_format(self):
        graph = _make_graph(nodes=[
            _verb("get_user", "/users"),
            _noun("user"),
            _constraint("auth"),
        ])
        result = check_node_id_format(graph)
        assert result.status == ValidationStatus.PASS

    def test_wrong_prefix(self):
        bad_node = SystemNode(
            id="endpoint:GET:/users",
            type=NodeType.VERB,
            name="get_user",
            http_method="GET",
            http_path="/users",
        )
        graph = _make_graph(nodes=[bad_node])
        result = check_node_id_format(graph)
        assert result.status == ValidationStatus.WARN
        assert "endpoint:GET:/users" in result.details[0]


class TestDuplicates:
    def test_no_duplicates(self):
        graph = _make_graph(nodes=[_noun("user"), _noun("project")])
        result = check_duplicates(graph)
        assert result.status == ValidationStatus.PASS

    def test_duplicate_node_id(self):
        graph = _make_graph(nodes=[_noun("user"), _noun("user")])
        result = check_duplicates(graph)
        assert result.status == ValidationStatus.WARN
        assert any("Duplicate node" in d for d in result.details)

    def test_duplicate_edge(self):
        verb = _verb("get_user", "/users")
        noun = _noun("user")
        edge = _edge(verb.id, noun.id, EdgeType.OPERATES_ON)
        graph = _make_graph(nodes=[verb, noun], edges=[edge, edge])
        result = check_duplicates(graph)
        assert result.status == ValidationStatus.WARN
        assert any("Duplicate edge" in d for d in result.details)


class TestRequiredFields:
    def test_complete_verb(self):
        graph = _make_graph(nodes=[_verb("get_user", "/users")])
        result = check_required_fields(graph)
        assert result.status == ValidationStatus.PASS

    def test_verb_missing_method(self):
        bad_verb = SystemNode(
            id="verb:GET:/users",
            type=NodeType.VERB,
            name="get_user",
            http_path="/users",
            # http_method intentionally omitted
        )
        graph = _make_graph(nodes=[bad_verb])
        result = check_required_fields(graph)
        assert result.status == ValidationStatus.FAIL
        assert any("http_method" in d for d in result.details)

    def test_verb_missing_path(self):
        bad_verb = SystemNode(
            id="verb:GET:/users",
            type=NodeType.VERB,
            name="get_user",
            http_method="GET",
            # http_path intentionally omitted
        )
        graph = _make_graph(nodes=[bad_verb])
        result = check_required_fields(graph)
        assert result.status == ValidationStatus.FAIL
        assert any("http_path" in d for d in result.details)


class TestValidateAll:
    def test_healthy_graph(self):
        verb = _verb("get_user", "/users")
        noun = _noun("user")
        edge = _edge(verb.id, noun.id, EdgeType.OPERATES_ON)
        graph = _make_graph(nodes=[verb, noun], edges=[edge])
        results = validate_graph_consistency(graph)
        assert len(results) == 5
        assert all(r.status == ValidationStatus.PASS for r in results)

    def test_empty_graph(self):
        graph = _make_graph()
        results = validate_graph_consistency(graph)
        assert all(r.status == ValidationStatus.PASS for r in results)
