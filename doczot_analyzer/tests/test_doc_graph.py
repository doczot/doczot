"""Tests for doc_graph.py - Doc-side entity/relationship extraction."""
import pytest
from datetime import datetime

from doczot_analyzer.doc_graph import (
    DocEntity,
    DocGraph,
    DocMention,
    DocRelationship,
    GraphComparison,
    extract_doc_graph,
    compare_graphs,
    _extract_from_file,
    _add_entity,
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


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_graph():
    """A minimal SystemGraph for testing."""
    return SystemGraph(
        product_name="test-api",
        scanned_at=datetime.now(),
        nodes=[
            SystemNode(id="noun:user", type=NodeType.NOUN, name="user"),
            SystemNode(id="noun:project", type=NodeType.NOUN, name="project"),
            SystemNode(id="noun:team", type=NodeType.NOUN, name="team"),
            SystemNode(
                id="verb:POST:/users",
                type=NodeType.VERB,
                name="create_user",
                http_method="POST",
                http_path="/users",
            ),
            SystemNode(
                id="verb:GET:/users",
                type=NodeType.VERB,
                name="list_users",
                http_method="GET",
                http_path="/users",
            ),
            SystemNode(
                id="verb:GET:/projects",
                type=NodeType.VERB,
                name="list_projects",
                http_method="GET",
                http_path="/projects",
            ),
        ],
        edges=[
            SystemEdge(
                source_id="verb:POST:/users",
                target_id="noun:user",
                edge_type=EdgeType.OPERATES_ON,
            ),
            SystemEdge(
                source_id="verb:GET:/users",
                target_id="noun:user",
                edge_type=EdgeType.OPERATES_ON,
            ),
            SystemEdge(
                source_id="noun:project",
                target_id="noun:user",
                edge_type=EdgeType.PART_OF,
            ),
        ],
    )


@pytest.fixture
def sample_doc_content():
    """Sample markdown documentation."""
    return """# Test API Documentation

## Users

The **user** is the primary entity in the system. Users can create projects.

Each user belongs to a team. A project belongs to a user.

### Creating Users

To create a user, send a POST /users request with the following body:

```json
{"name": "Alice", "email": "alice@example.com"}
```

### Listing Users

GET /users returns a list of all users.

## Projects

A project is part of a user's workspace. Projects require authentication.

### Listing Projects

GET /projects returns all projects.

## Authentication

**API Key**: An API key is required for all requests.

Rate limits apply: each user is limited to 100 requests per hour.
"""


# =============================================================================
# ENTITY EXTRACTION TESTS
# =============================================================================

def test_extract_nouns_from_doc(sample_graph, sample_doc_content):
    """Test that known code nouns are detected in docs."""
    code_nouns = {n.name.lower() for n in sample_graph.nouns}
    entities: dict[str, DocEntity] = {}
    relationships: list[DocRelationship] = []

    _extract_from_file(sample_doc_content, "README.md", code_nouns, entities, relationships)

    # "user" and "project" should be found
    assert "user" in entities
    assert "project" in entities


def test_extract_http_verbs_from_doc(sample_graph, sample_doc_content):
    """Test that HTTP endpoint references are extracted."""
    code_nouns = {n.name.lower() for n in sample_graph.nouns}
    entities: dict[str, DocEntity] = {}
    relationships: list[DocRelationship] = []

    _extract_from_file(sample_doc_content, "README.md", code_nouns, entities, relationships)

    # POST /users and GET /users should be found
    assert "post /users" in entities
    assert "get /users" in entities
    assert "get /projects" in entities


def test_extract_bold_definitions(sample_graph, sample_doc_content):
    """Test that bold term definitions are extracted as concepts."""
    code_nouns = {n.name.lower() for n in sample_graph.nouns}
    entities: dict[str, DocEntity] = {}
    relationships: list[DocRelationship] = []

    _extract_from_file(sample_doc_content, "README.md", code_nouns, entities, relationships)

    # "API Key" defined with bold syntax should be found
    assert "api key" in entities
    assert entities["api key"].entity_type == "concept"
    assert entities["api key"].definition is not None


def test_extract_imperative_verbs(sample_graph):
    """Test that imperative verb + noun patterns are extracted."""
    content = """## Getting Started

- Create a user to get started
- Delete the project when done
- Update your profile settings
"""
    code_nouns = {n.name.lower() for n in sample_graph.nouns}
    entities: dict[str, DocEntity] = {}
    relationships: list[DocRelationship] = []

    _extract_from_file(content, "README.md", code_nouns, entities, relationships)

    assert "create user" in entities
    assert "delete project" in entities


def test_skip_generic_terms(sample_graph):
    """Test that generic terms are skipped."""
    content = """## The system

The example shows how to use the following features.
This section describes the configuration.
"""
    code_nouns = set()
    entities: dict[str, DocEntity] = {}
    relationships: list[DocRelationship] = []

    _extract_from_file(content, "README.md", code_nouns, entities, relationships)

    # Generic terms should not appear
    assert "the" not in entities
    assert "example" not in entities
    assert "section" not in entities


# =============================================================================
# RELATIONSHIP EXTRACTION TESTS
# =============================================================================

def test_extract_part_of_relationship(sample_graph, sample_doc_content):
    """Test that 'belongs to' / 'part of' patterns produce part_of relationships."""
    code_nouns = {n.name.lower() for n in sample_graph.nouns}
    entities: dict[str, DocEntity] = {}
    relationships: list[DocRelationship] = []

    _extract_from_file(sample_doc_content, "README.md", code_nouns, entities, relationships)

    part_of_rels = [r for r in relationships if r.rel_type == "part_of"]
    # "user belongs to a team" or "project belongs to user"
    assert len(part_of_rels) > 0

    # Check that at least one part_of relationship involves known entities
    sources_targets = [(r.source, r.target) for r in part_of_rels]
    # "user belongs to team" → source=user, target=team
    assert any("user" in s or "user" in t for s, t in sources_targets)


def test_extract_prerequisite_relationship(sample_graph):
    """Test that 'requires' patterns produce prerequisite relationships."""
    content = """## Authentication

Projects require authentication before access.
Before you can create a project, you must authenticate.
"""
    code_nouns = {"project", "user", "authentication"}
    entities: dict[str, DocEntity] = {}
    relationships: list[DocRelationship] = []

    _extract_from_file(content, "README.md", code_nouns, entities, relationships)

    prereq_rels = [r for r in relationships if r.rel_type == "prerequisite"]
    assert len(prereq_rels) > 0


def test_extract_constrained_by_relationship(sample_graph, sample_doc_content):
    """Test that limit patterns produce constrained_by relationships."""
    code_nouns = {n.name.lower() for n in sample_graph.nouns}
    entities: dict[str, DocEntity] = {}
    relationships: list[DocRelationship] = []

    _extract_from_file(sample_doc_content, "README.md", code_nouns, entities, relationships)

    constrained_rels = [r for r in relationships if r.rel_type == "constrained_by"]
    # "each user is limited to 100 requests per hour"
    assert len(constrained_rels) > 0


# =============================================================================
# GRAPH COMPARISON TESTS
# =============================================================================

def test_compare_graphs_covered(sample_graph):
    """Test that covered entities are detected."""
    doc_graph = DocGraph(
        entities=[
            DocEntity(name="user", entity_type="noun", mentions=[
                DocMention(doc_file="README.md", snippet="user entity")
            ]),
            DocEntity(name="post /users", entity_type="verb", mentions=[
                DocMention(doc_file="README.md", snippet="POST /users")
            ]),
        ],
    )

    comparison = compare_graphs(sample_graph, doc_graph)
    assert "user" in comparison.covered_entities
    assert comparison.coverage_ratio > 0


def test_compare_graphs_missing(sample_graph):
    """Test that missing entities are detected."""
    doc_graph = DocGraph(
        entities=[
            DocEntity(name="user", entity_type="noun", mentions=[
                DocMention(doc_file="README.md", snippet="user entity")
            ]),
        ],
    )

    comparison = compare_graphs(sample_graph, doc_graph)
    # "project" and "team" should be missing
    assert "project" in comparison.missing_entities
    assert "team" in comparison.missing_entities


def test_compare_graphs_extra(sample_graph):
    """Test that extra doc entities are detected."""
    doc_graph = DocGraph(
        entities=[
            DocEntity(name="user", entity_type="noun", mentions=[]),
            DocEntity(name="widget", entity_type="noun", mentions=[]),
        ],
    )

    comparison = compare_graphs(sample_graph, doc_graph)
    assert "widget" in comparison.extra_entities


def test_compare_graphs_relationship_mismatch(sample_graph):
    """Test that relationship mismatches are found."""
    # Code says project part_of user, docs say project operates_on user
    doc_graph = DocGraph(
        entities=[],
        relationships=[
            DocRelationship(
                source="project",
                target="user",
                rel_type="operates_on",
                evidence="project operates on user",
                doc_file="README.md",
            ),
        ],
    )

    comparison = compare_graphs(sample_graph, doc_graph)
    assert len(comparison.relationship_mismatches) > 0
    mismatch = comparison.relationship_mismatches[0]
    assert mismatch["code_rel"] == "part_of"
    assert mismatch["doc_rel"] == "operates_on"


# =============================================================================
# DOC GRAPH MODEL TESTS
# =============================================================================

def test_doc_graph_entities_by_type():
    """Test filtering entities by type."""
    dg = DocGraph(
        entities=[
            DocEntity(name="user", entity_type="noun", mentions=[]),
            DocEntity(name="create user", entity_type="verb", mentions=[]),
            DocEntity(name="auth", entity_type="concept", mentions=[]),
        ],
    )

    assert len(dg.nouns) == 1
    assert len(dg.verbs) == 1
    assert len(dg.concepts) == 1
    assert dg.nouns[0].name == "user"


def test_add_entity_deduplication():
    """Test that _add_entity deduplicates by name."""
    entities: dict[str, DocEntity] = {}

    _add_entity(entities, "user", "noun", DocMention(doc_file="a.md", snippet="first"))
    _add_entity(entities, "user", "noun", DocMention(doc_file="b.md", snippet="second"))

    assert len(entities) == 1
    assert len(entities["user"].mentions) == 2


def test_graph_comparison_empty():
    """Test comparison with empty graphs."""
    empty_code = SystemGraph(
        product_name="empty",
        scanned_at=datetime.now(),
    )
    empty_doc = DocGraph()

    comparison = compare_graphs(empty_code, empty_doc)
    assert comparison.code_entity_count == 0
    assert comparison.doc_entity_count == 0
    assert comparison.coverage_ratio == 0.0
