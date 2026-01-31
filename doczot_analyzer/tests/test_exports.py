"""Unit tests for agent-oriented export formats.

Tests:
- MCP resource definition export
- llms.txt generation
- JSON-LD export
"""

import json
import pytest

from doczot_analyzer.exports import (
    export_mcp_resources,
    export_llms_txt,
    export_jsonld,
)
from doczot_analyzer.models_v2 import (
    SystemGraph,
    SystemNode,
    SystemEdge,
    NodeType,
    NodeClass,
    EdgeType,
    ConfidenceLevel,
)


def _make_test_graph() -> SystemGraph:
    """Create a small but realistic system graph for testing."""
    nodes = [
        SystemNode(
            id="verb:GET:/users",
            type=NodeType.VERB,
            name="list_users",
            http_method="GET",
            http_path="/users",
            description="List all users",
        ),
        SystemNode(
            id="verb:GET:/users/{user_id}",
            type=NodeType.VERB,
            name="get_user",
            http_method="GET",
            http_path="/users/{user_id}",
            description="Get a specific user",
        ),
        SystemNode(
            id="verb:POST:/users",
            type=NodeType.VERB,
            name="create_user",
            http_method="POST",
            http_path="/users",
            description="Create a new user",
        ),
        SystemNode(
            id="noun:user",
            type=NodeType.NOUN,
            name="user",
            description="A system user",
        ),
        SystemNode(
            id="concept:authentication",
            type=NodeType.CONCEPT,
            name="authentication",
            description="JWT-based token authentication",
        ),
        SystemNode(
            id="constraint:auth_required:verb:GET:/users",
            type=NodeType.CONSTRAINT,
            name="auth_required",
            description="Authentication required: Bearer token",
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
            source_id="verb:GET:/users/{user_id}",
            target_id="noun:user",
            edge_type=EdgeType.OPERATES_ON,
        ),
        SystemEdge(
            source_id="verb:POST:/users",
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
        product_name="test-api",
        source_paths=["test"],
        nodes=nodes,
        edges=edges,
    )


class TestMCPExport:
    """Test MCP resource definition export."""

    def test_exports_nouns_as_resources(self):
        """Each noun should become an MCP resource."""
        graph = _make_test_graph()
        mcp = export_mcp_resources(graph)

        assert "resources" in mcp
        assert len(mcp["resources"]) == 1  # one noun: user

        resource = mcp["resources"][0]
        assert resource["name"] == "user"
        assert "doczot://test-api/entity/user" == resource["uri"]
        assert resource["mimeType"] == "text/plain"

    def test_exports_verbs_as_tools(self):
        """Each verb should become an MCP tool."""
        graph = _make_test_graph()
        mcp = export_mcp_resources(graph)

        assert "tools" in mcp
        assert len(mcp["tools"]) == 3  # three verbs

        names = {t["name"] for t in mcp["tools"]}
        assert "list_users" in names
        assert "get_user" in names
        assert "create_user" in names

    def test_tool_has_path_parameters(self):
        """Tools with path params should have inputSchema properties."""
        graph = _make_test_graph()
        mcp = export_mcp_resources(graph)

        get_user = next(t for t in mcp["tools"] if t["name"] == "get_user")
        schema = get_user["inputSchema"]
        assert "user_id" in schema["properties"]
        assert "user_id" in schema["required"]

    def test_tool_description_includes_constraints(self):
        """Tool descriptions should mention constraints."""
        graph = _make_test_graph()
        mcp = export_mcp_resources(graph)

        list_users = next(t for t in mcp["tools"] if t["name"] == "list_users")
        assert "Authentication required" in list_users["description"]
        assert "Rate limited" in list_users["description"]

    def test_output_is_valid_json(self):
        """MCP output should be serializable to valid JSON."""
        graph = _make_test_graph()
        mcp = export_mcp_resources(graph)
        output = json.dumps(mcp, indent=2)
        parsed = json.loads(output)
        assert parsed == mcp


class TestLlmsTxtExport:
    """Test llms.txt generation."""

    def test_starts_with_product_name(self):
        """llms.txt should start with product name as H1."""
        graph = _make_test_graph()
        output = export_llms_txt(graph)
        assert output.startswith("# test-api")

    def test_has_entities_section(self):
        """llms.txt should list entities."""
        graph = _make_test_graph()
        output = export_llms_txt(graph)
        assert "## Entities" in output
        assert "**user**" in output

    def test_has_operations_section(self):
        """llms.txt should list operations grouped by entity."""
        graph = _make_test_graph()
        output = export_llms_txt(graph)
        assert "## Operations" in output
        assert "GET /users" in output
        assert "POST /users" in output

    def test_has_constraints_section(self):
        """llms.txt should list constraints."""
        graph = _make_test_graph()
        output = export_llms_txt(graph)
        assert "## Constraints" in output
        assert "Authentication required" in output
        assert "Rate limited" in output

    def test_has_concepts_section(self):
        """llms.txt should list concepts."""
        graph = _make_test_graph()
        output = export_llms_txt(graph)
        assert "## Concepts" in output
        assert "**authentication**" in output

    def test_operations_grouped_by_noun(self):
        """Operations should be grouped under their entity."""
        graph = _make_test_graph()
        output = export_llms_txt(graph)
        # "### user" should appear before the user operations
        assert "### user" in output

    def test_entity_descriptions_included(self):
        """Entity descriptions should be in the output."""
        graph = _make_test_graph()
        output = export_llms_txt(graph)
        assert "A system user" in output


class TestJsonLdExport:
    """Test JSON-LD export."""

    def test_has_context(self):
        """JSON-LD output should have @context."""
        graph = _make_test_graph()
        output = export_jsonld(graph)
        assert "@context" in output
        assert "@vocab" in output["@context"]

    def test_has_product_id(self):
        """JSON-LD output should identify the product."""
        graph = _make_test_graph()
        output = export_jsonld(graph)
        assert output["@type"] == "SoftwareApplication"
        assert output["name"] == "test-api"

    def test_includes_all_nodes(self):
        """All graph nodes should be in the output."""
        graph = _make_test_graph()
        output = export_jsonld(graph)
        assert len(output["nodes"]) == len(graph.nodes)

    def test_node_types_mapped(self):
        """Node types should be mapped to JSON-LD types."""
        graph = _make_test_graph()
        output = export_jsonld(graph)

        verb_nodes = [n for n in output["nodes"] if n["@type"] == "APIOperation"]
        entity_nodes = [n for n in output["nodes"] if n["@type"] == "Entity"]
        concept_nodes = [n for n in output["nodes"] if n["@type"] == "Concept"]
        constraint_nodes = [n for n in output["nodes"] if n["@type"] == "Constraint"]

        assert len(verb_nodes) == 3
        assert len(entity_nodes) == 1
        assert len(concept_nodes) == 1
        assert len(constraint_nodes) == 2

    def test_relationships_included(self):
        """Nodes with edges should have relationships."""
        graph = _make_test_graph()
        output = export_jsonld(graph)

        list_users = next(n for n in output["nodes"] if n["name"] == "list_users")
        assert "relationships" in list_users
        assert len(list_users["relationships"]) > 0

    def test_output_is_valid_json(self):
        """JSON-LD output should be serializable to valid JSON."""
        graph = _make_test_graph()
        output = export_jsonld(graph)
        serialized = json.dumps(output, indent=2)
        parsed = json.loads(serialized)
        assert parsed == output

    def test_has_date(self):
        """JSON-LD output should include scan date."""
        graph = _make_test_graph()
        output = export_jsonld(graph)
        assert "dateCreated" in output
