"""Tests for Coverage Checklist (ITM) generation.

Regression coverage for duplicate endpoint topics: nested routes used
to produce identical titles ("Get projects" twice) and appear under
every entity they operate on, double-counting them in drift reports.
"""
from doczot_analyzer.models_v2 import (
    EdgeType,
    NodeClass,
    NodeType,
    SystemEdge,
    SystemGraph,
    SystemNode,
    generate_default_itm,
)


def _verb(method: str, path: str) -> SystemNode:
    return SystemNode(
        id=f"verb:{method}:{path}", type=NodeType.VERB,
        name=f"{method.lower()}_{path.strip('/').split('/')[-1]}",
        node_class=NodeClass.USER_FACING,
        http_method=method, http_path=path,
    )


def _noun(name: str) -> SystemNode:
    return SystemNode(
        id=f"noun:{name}", type=NodeType.NOUN, name=name,
        node_class=NodeClass.USER_FACING,
    )


def _graph() -> SystemGraph:
    """user + project entities; nested project routes touch both."""
    nodes = [
        _noun("user"), _noun("project"),
        _verb("GET", "/users"),
        _verb("GET", "/users/{user_id}/projects"),
        _verb("GET", "/users/{user_id}/projects/{project_id}"),
        _verb("POST", "/users/{user_id}/projects"),
    ]
    edges = [
        SystemEdge(source_id="verb:GET:/users", target_id="noun:user",
                   edge_type=EdgeType.OPERATES_ON),
    ]
    # Nested project endpoints operate on BOTH user and project
    for vid in ["verb:GET:/users/{user_id}/projects",
                "verb:GET:/users/{user_id}/projects/{project_id}",
                "verb:POST:/users/{user_id}/projects"]:
        edges.append(SystemEdge(source_id=vid, target_id="noun:user",
                                edge_type=EdgeType.OPERATES_ON))
        edges.append(SystemEdge(source_id=vid, target_id="noun:project",
                                edge_type=EdgeType.OPERATES_ON))
    return SystemGraph(product_name="t", nodes=nodes, edges=edges)


class TestEndpointTitles:
    def test_collection_vs_item_titles_differ(self):
        itm = generate_default_itm(_graph())
        names = {t.name for t in itm.topics}
        assert "List projects" in names
        assert "Get project by id" in names
        assert "Create project" in names

    def test_nested_collection_is_not_titled_get(self):
        """/users/{id}/projects is a listing despite the param upstream."""
        itm = generate_default_itm(_graph())
        by_cover = {t.covers[0]: t.name for t in itm.topics if len(t.covers) == 1}
        assert by_cover["verb:GET:/users/{user_id}/projects"] == "List projects"
        assert by_cover["verb:GET:/users/{user_id}/projects/{project_id}"] == "Get project by id"


class TestEndpointOwnership:
    def test_each_endpoint_topic_appears_once(self):
        itm = generate_default_itm(_graph())
        endpoint_topics = [t for t in itm.topics
                           if t.topic_type.value == "reference" and len(t.covers) == 1]
        covered = [t.covers[0] for t in endpoint_topics]
        assert len(covered) == len(set(covered)), (
            f"duplicate endpoint topics: {sorted(covered)}"
        )

    def test_project_endpoints_grouped_under_project(self):
        itm = generate_default_itm(_graph())
        project_group = next(t for t in itm.topics if t.name == "Project")
        child_names = {t.name for t in itm.topics if t.parent_id == project_group.id}
        assert child_names == {"List projects", "Get project by id", "Create project"}

    def test_all_verbs_still_covered(self):
        graph = _graph()
        itm = generate_default_itm(graph)
        covered = {vid for t in itm.topics for vid in t.covers}
        for verb in graph.verbs:
            assert verb.id in covered
