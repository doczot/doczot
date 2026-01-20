"""Tests for RDF/OWL ontology module.

Tests the ontology representation, SPARQL queries, and reasoning capabilities.
"""

import pytest
from datetime import datetime

# Skip all tests if rdflib is not installed
pytest.importorskip("rdflib")

from doczot_analyzer.ontology import (
    DoczotOntology,
    surface_graph_to_ontology,
    topic_manifest_to_ontology,
    full_analysis_to_ontology,
    HAS_RDFLIB,
)


class TestDoczotOntologyBasics:
    """Test basic ontology creation and element addition."""

    def test_creates_ontology_with_schema(self):
        """Test that ontology initializes with schema loaded."""
        onto = DoczotOntology("Test API")

        assert onto.product_name == "Test API"
        # Schema should include class definitions
        stats = onto.get_statistics()
        assert stats['total_triples'] > 0

    def test_creates_ontology_without_schema(self):
        """Test that ontology can be created without schema."""
        onto = DoczotOntology("Test API", load_schema=False)

        stats = onto.get_statistics()
        assert stats['total_triples'] == 0

    def test_add_noun(self):
        """Test adding a noun to the ontology."""
        onto = DoczotOntology("Test API", load_schema=False)

        uri = onto.add_noun(
            "user",
            node_id="noun:user",
            description="A system user",
            source_file="models.py",
            source_line=10,
        )

        assert uri is not None
        nouns = onto.get_all_nouns()
        assert len(nouns) == 1
        assert nouns[0]['name'] == "user"

    def test_add_verb(self):
        """Test adding a verb (endpoint) to the ontology."""
        onto = DoczotOntology("Test API", load_schema=False)

        uri = onto.add_verb(
            "get_user",
            http_method="GET",
            http_path="/users/{id}",
            node_id="verb:GET:/users/{id}",
            description="Retrieve a user by ID",
            source_file="api.py",
            source_line=20,
        )

        assert uri is not None
        verbs = onto.get_all_verbs()
        assert len(verbs) == 1
        assert verbs[0]['name'] == "get_user"
        assert verbs[0]['path'] == "/users/{id}"

    def test_add_concept(self):
        """Test adding a concept to the ontology."""
        onto = DoczotOntology("Test API", load_schema=False)

        uri = onto.add_concept(
            "authentication",
            node_id="concept:authentication",
            description="The process of verifying user identity",
        )

        assert uri is not None
        stats = onto.get_statistics()
        assert stats['concepts'] == 1

    def test_add_constraint(self):
        """Test adding constraints to the ontology."""
        onto = DoczotOntology("Test API", load_schema=False)

        auth_uri = onto.add_constraint(
            "auth",
            "requires_login",
            description="Requires authenticated user",
            value="jwt",
        )

        rate_uri = onto.add_constraint(
            "rate_limit",
            "api_rate",
            description="Rate limited endpoint",
            value="100/hour",
        )

        assert auth_uri is not None
        assert rate_uri is not None
        stats = onto.get_statistics()
        assert stats['constraints'] == 2


class TestRelationships:
    """Test adding relationships between elements."""

    def test_operates_on_relationship(self):
        """Test adding verb-operates_on-noun relationship."""
        onto = DoczotOntology("Test API", load_schema=False)

        noun_uri = onto.add_noun("user", node_id="noun:user")
        verb_uri = onto.add_verb(
            "get_user", "GET", "/users/{id}",
            node_id="verb:GET:/users/{id}",
            operates_on=["user"],
        )

        relationships = onto.get_verb_noun_relationships()
        assert len(relationships) == 1
        assert relationships[0]['nounName'] == "user"

    def test_part_of_relationship(self):
        """Test adding part_of relationship between nouns."""
        onto = DoczotOntology("Test API", load_schema=False)

        user_uri = onto.add_noun("user", node_id="noun:user")
        project_uri = onto.add_noun("project", node_id="noun:project", part_of="user")

        hierarchy = onto.get_noun_hierarchy()
        assert len(hierarchy) == 1
        assert hierarchy[0]['childName'] == "project"
        assert hierarchy[0]['parentName'] == "user"

    def test_constrained_by_relationship(self):
        """Test adding constraint relationships."""
        onto = DoczotOntology("Test API", load_schema=False)

        verb_uri = onto.add_verb("get_user", "GET", "/users/{id}", node_id="v1")
        constraint_uri = onto.add_constraint("auth", "auth_required", node_id="c1")

        onto.add_constrained_by(verb_uri, constraint_uri)

        # Check that the relationship exists via SPARQL
        results = onto.query("""
            SELECT ?verb ?constraint WHERE {
                ?verb doczot:constrainedBy ?constraint .
            }
        """)
        assert len(results) == 1


class TestSerialization:
    """Test ontology serialization to different formats."""

    def test_serialize_turtle(self):
        """Test serialization to Turtle format."""
        onto = DoczotOntology("Test API", load_schema=False)
        onto.add_noun("user", node_id="noun:user")

        output = onto.serialize("turtle")

        assert "@prefix" in output
        assert "user" in output

    def test_serialize_json_ld(self):
        """Test serialization to JSON-LD format."""
        onto = DoczotOntology("Test API", load_schema=False)
        onto.add_noun("user", node_id="noun:user")

        output = onto.serialize("json-ld")

        # JSON-LD output should be valid JSON with @id references
        assert '"@id"' in output
        assert "user" in output

    def test_serialize_ntriples(self):
        """Test serialization to N-Triples format."""
        onto = DoczotOntology("Test API", load_schema=False)
        onto.add_noun("user", node_id="noun:user")

        output = onto.serialize("nt")

        # N-Triples format: each triple ends with " ."
        assert " ." in output


class TestSPARQLQueries:
    """Test SPARQL query functionality."""

    def test_custom_sparql_query(self):
        """Test executing custom SPARQL queries."""
        onto = DoczotOntology("Test API", load_schema=False)
        onto.add_noun("user", node_id="noun:user")
        onto.add_noun("project", node_id="noun:project")

        results = onto.query("""
            SELECT ?noun ?name WHERE {
                ?noun a doczot:Noun ;
                      doczot:name ?name .
            }
            ORDER BY ?name
        """)

        assert len(results) == 2
        assert results[0]['name'] == "project"
        assert results[1]['name'] == "user"

    def test_get_undocumented_elements(self):
        """Test finding undocumented elements."""
        onto = DoczotOntology("Test API")  # With schema for subclass queries

        onto.add_noun("user", node_id="noun:user")
        onto.add_verb("get_user", "GET", "/users/{id}", node_id="v1")

        # No topics added, so all should be undocumented
        undocumented = onto.get_undocumented_elements()

        # Should find the verb and noun (not schema classes)
        names = [r['name'] for r in undocumented]
        assert "user" in names or "get_user" in names

    def test_get_auth_protected_endpoints(self):
        """Test finding auth-protected endpoints."""
        onto = DoczotOntology("Test API", load_schema=False)

        verb_uri = onto.add_verb("get_user", "GET", "/users/{id}", node_id="v1")
        constraint_uri = onto.add_constraint("auth", "jwt_auth", value="bearer")
        onto.add_constrained_by(verb_uri, constraint_uri)

        protected = onto.get_auth_protected_endpoints()

        assert len(protected) == 1
        assert protected[0]['path'] == "/users/{id}"

    def test_get_rate_limited_endpoints(self):
        """Test finding rate-limited endpoints."""
        onto = DoczotOntology("Test API", load_schema=False)

        verb_uri = onto.add_verb("list_items", "GET", "/items", node_id="v1")
        constraint_uri = onto.add_constraint("rate_limit", "api_limit", value="100/hour")
        onto.add_constrained_by(verb_uri, constraint_uri)

        rate_limited = onto.get_rate_limited_endpoints()

        assert len(rate_limited) == 1
        assert rate_limited[0]['rateLimit'] == "100/hour"


class TestTopics:
    """Test documentation topic functionality."""

    def test_add_topic(self):
        """Test adding documentation topics."""
        onto = DoczotOntology("Test API", load_schema=False)

        # Add surface elements first
        onto.add_noun("user", node_id="noun:user")

        # Add topic that covers the noun
        topic_uri = onto.add_topic(
            "User Management",
            "reference",
            topic_id="topic:user_mgmt",
            source_document="docs/users.md",
            coverage_score=0.8,
            has_examples=True,
            covers=["noun:user"],
        )

        assert topic_uri is not None

        coverage = onto.get_topic_coverage()
        assert len(coverage) == 1
        assert coverage[0]['name'] == "User Management"


class TestInference:
    """Test reasoning and inference capabilities."""

    def test_transitive_closure(self):
        """Test computing transitive closure for partOf."""
        onto = DoczotOntology("Test API", load_schema=False)

        # Create hierarchy: task -> project -> user
        onto.add_noun("user", node_id="noun:user")
        onto.add_noun("project", node_id="noun:project", part_of="user")

        # Manually add project URI so we can reference it
        project_uri = onto._node_uris.get("noun:project")

        # Add task partOf project
        task_uri = onto.add_noun("task", node_id="noun:task")
        onto.add_part_of(task_uri, project_uri)

        # Run transitive closure
        inferred = onto.infer_transitive_closure()

        # Should infer task partOf user (transitively)
        # and hasPart inverse relationships
        assert inferred > 0

    def test_validate_consistency(self):
        """Test ontology consistency validation."""
        onto = DoczotOntology("Test API", load_schema=False)

        # Add a well-formed verb
        onto.add_verb("get_user", "GET", "/users/{id}", node_id="v1")

        validation = onto.validate_consistency()

        assert validation['valid'] is True
        assert validation['issue_count'] == 0


class TestConversions:
    """Test conversion from Pydantic models to ontology."""

    def test_surface_graph_conversion(self):
        """Test converting SurfaceGraph to ontology."""
        from doczot_analyzer.models_v2 import (
            SurfaceGraph, SurfaceNode, SurfaceEdge,
            NodeType, NodeClass, EdgeType, ConfidenceLevel,
        )

        # Create a simple surface graph
        surface = SurfaceGraph(
            product_name="Test API",
            scanned_at=datetime.now(),
            source_paths=["/test/api.py"],
            nodes=[
                SurfaceNode(
                    id="noun:user",
                    type=NodeType.NOUN,
                    name="user",
                    description="A user entity",
                    node_class=NodeClass.USER_FACING,
                ),
                SurfaceNode(
                    id="verb:GET:/users/{id}",
                    type=NodeType.VERB,
                    name="get_user",
                    node_class=NodeClass.USER_FACING,
                    http_method="GET",
                    http_path="/users/{id}",
                ),
            ],
            edges=[
                SurfaceEdge(
                    source_id="verb:GET:/users/{id}",
                    target_id="noun:user",
                    edge_type=EdgeType.OPERATES_ON,
                    confidence=ConfidenceLevel.HIGH,
                ),
            ],
        )

        onto = surface_graph_to_ontology(surface)

        assert onto.product_name == "Test API"

        nouns = onto.get_all_nouns()
        assert len(nouns) == 1
        assert nouns[0]['name'] == "user"

        verbs = onto.get_all_verbs()
        assert len(verbs) == 1
        assert verbs[0]['path'] == "/users/{id}"

        relationships = onto.get_verb_noun_relationships()
        assert len(relationships) == 1


class TestStatistics:
    """Test statistics gathering."""

    def test_get_statistics(self):
        """Test getting ontology statistics."""
        onto = DoczotOntology("Test API", load_schema=False)

        onto.add_noun("user", node_id="noun:user")
        onto.add_noun("project", node_id="noun:project")
        onto.add_verb("get_user", "GET", "/users/{id}", node_id="v1", operates_on=["user"])
        onto.add_concept("auth", node_id="concept:auth")
        onto.add_constraint("rate_limit", "api_rate", node_id="c1", value="100/hour")

        stats = onto.get_statistics()

        assert stats['nouns'] == 2
        assert stats['verbs'] == 1
        assert stats['concepts'] == 1
        assert stats['constraints'] == 1
        assert stats['relationships']['operates_on'] == 1

    def test_get_coverage_statistics(self):
        """Test getting coverage statistics."""
        onto = DoczotOntology("Test API")

        # Add user-facing elements
        onto.add_noun("user", node_id="noun:user", is_user_facing=True)
        onto.add_verb("get_user", "GET", "/users/{id}", node_id="v1", is_user_facing=True)

        stats = onto.get_coverage_statistics()

        # With no ATM topics, coverage should be 0
        assert stats['total_elements'] == 2
        assert stats['covered_elements'] == 0
        assert stats['coverage_percent'] == 0.0
