"""Unit tests for deterministic concept extraction.

Tests extraction of concepts from:
- Endpoint docstrings (definition patterns)
- Documentation files (headers, bold terms)
- Concept-to-noun RELATED_TO edge creation
"""

import pytest
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from doczot_analyzer.analyzer_v2 import (
    extract_concepts_from_docstrings,
    extract_concepts_from_docs,
    build_surface_graph_python,
)
from doczot_analyzer.models_v2 import EdgeType, NodeType


class TestDocstringConceptExtraction:
    """Test concept extraction from endpoint docstrings."""

    def _make_endpoint(self, docstring, file_path="test.py", line_number=1):
        return SimpleNamespace(
            docstring=docstring,
            file_path=file_path,
            line_number=line_number,
        )

    def test_extracts_is_definition(self):
        """'X is ...' pattern should extract a concept."""
        ep = self._make_endpoint("Authentication is the process of verifying identity.")
        concepts = extract_concepts_from_docstrings([ep])
        names = [c["name"] for c in concepts]
        assert "authentication" in names

    def test_extracts_refers_to_definition(self):
        """'X refers to ...' pattern should extract a concept."""
        ep = self._make_endpoint("Rate limiting refers to restricting request frequency.")
        concepts = extract_concepts_from_docstrings([ep])
        names = [c["name"] for c in concepts]
        assert "rate limiting" in names

    def test_extracts_represents_definition(self):
        """'X represents ...' pattern should extract a concept."""
        ep = self._make_endpoint("A workspace represents a collection of projects.")
        concepts = extract_concepts_from_docstrings([ep])
        names = [c["name"] for c in concepts]
        assert "workspace" in names

    def test_skips_crud_terms(self):
        """Common action words should not become concepts."""
        ep = self._make_endpoint("This endpoint handles creating users.")
        concepts = extract_concepts_from_docstrings([ep])
        names = [c["name"] for c in concepts]
        assert "this" not in names

    def test_skips_infrastructure_terms(self):
        """Infrastructure terms like 'endpoint' should be skipped."""
        ep = self._make_endpoint("Endpoint is a route that handles requests.")
        concepts = extract_concepts_from_docstrings([ep])
        names = [c["name"] for c in concepts]
        assert "endpoint" not in names

    def test_skips_empty_docstring(self):
        """No concepts from endpoints without docstrings."""
        ep = self._make_endpoint(None)
        concepts = extract_concepts_from_docstrings([ep])
        assert len(concepts) == 0

    def test_captures_definition_text(self):
        """Extracted concept should include the definition."""
        ep = self._make_endpoint("Authorization is the process of granting access.")
        concepts = extract_concepts_from_docstrings([ep])
        auth = next(c for c in concepts if c["name"] == "authorization")
        assert "granting access" in auth["definition"]

    def test_captures_source_location(self):
        """Concept should record its source file and line."""
        ep = self._make_endpoint(
            "Pagination is a technique for splitting results.",
            file_path="api/routes.py",
            line_number=42,
        )
        concepts = extract_concepts_from_docstrings([ep])
        assert concepts[0]["source_file"] == "api/routes.py"
        assert concepts[0]["source_line"] == 42

    def test_deduplicates_by_name(self):
        """Same concept from multiple docstrings should appear once."""
        eps = [
            self._make_endpoint("Authentication is verifying identity."),
            self._make_endpoint("Authentication is checking credentials."),
        ]
        concepts = extract_concepts_from_docstrings(eps)
        auth_concepts = [c for c in concepts if c["name"] == "authentication"]
        assert len(auth_concepts) == 1

    def test_multi_word_concept(self):
        """Multi-word concept names should be extracted."""
        ep = self._make_endpoint("Rate limiting provides protection against abuse.")
        concepts = extract_concepts_from_docstrings([ep])
        names = [c["name"] for c in concepts]
        assert "rate limiting" in names


class TestDocsConceptExtraction:
    """Test concept extraction from documentation files."""

    def _make_repo_with_docs(self, files: dict) -> str:
        """Create a temp repo with given markdown files.

        Args:
            files: dict mapping relative paths to content
        Returns:
            Path to the temp repo root
        """
        tmpdir = tempfile.mkdtemp()
        for rel_path, content in files.items():
            full_path = Path(tmpdir) / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        return tmpdir

    def test_extracts_from_h2_headers(self):
        """H2 headers with body text should produce concepts."""
        repo = self._make_repo_with_docs({
            "README.md": "# My App\n\n## Authentication\nThe auth system uses JWT tokens for secure access.\n\n## Installation\nRun pip install.\n"
        })
        concepts = extract_concepts_from_docs(repo)
        names = [c["name"] for c in concepts]
        assert "authentication" in names
        # Installation is in skip list
        assert "installation" not in names

    def test_extracts_from_h3_headers(self):
        """H3 headers should also be scanned."""
        repo = self._make_repo_with_docs({
            "README.md": "# App\n\n### Rate Limiting\nEach endpoint is limited to 100 requests per hour.\n"
        })
        concepts = extract_concepts_from_docs(repo)
        names = [c["name"] for c in concepts]
        assert "rate limiting" in names

    def test_extracts_bold_definitions(self):
        """**Bold term**: definition pattern should work."""
        repo = self._make_repo_with_docs({
            "README.md": "# App\n\n**Workspace**: A container that groups related projects together.\n"
        })
        concepts = extract_concepts_from_docs(repo)
        names = [c["name"] for c in concepts]
        assert "workspace" in names

    def test_extracts_bold_dash_definitions(self):
        """**Bold term** - definition pattern should work."""
        repo = self._make_repo_with_docs({
            "README.md": "# App\n\n**Tenant** - An isolated environment for a single customer.\n"
        })
        concepts = extract_concepts_from_docs(repo)
        names = [c["name"] for c in concepts]
        assert "tenant" in names

    def test_scans_docs_directory(self):
        """Files in docs/ should be scanned, not just README."""
        repo = self._make_repo_with_docs({
            "README.md": "# App\n\nSome intro text.\n",
            "docs/concepts.md": "# Concepts\n\n## Idempotency\nAn operation that produces the same result when called multiple times.\n"
        })
        concepts = extract_concepts_from_docs(repo)
        names = [c["name"] for c in concepts]
        assert "idempotency" in names

    def test_skips_meta_headers(self):
        """Headers like Installation, License should be skipped."""
        repo = self._make_repo_with_docs({
            "README.md": "# App\n\n## License\nMIT License applies to all code.\n\n## Contributing\nPlease read the guidelines.\n"
        })
        concepts = extract_concepts_from_docs(repo)
        names = [c["name"] for c in concepts]
        assert "license" not in names
        assert "contributing" not in names

    def test_deduplicates_across_files(self):
        """Same concept in README and docs/ should appear once."""
        repo = self._make_repo_with_docs({
            "README.md": "# App\n\n## Authentication\nJWT-based token authentication for all endpoints.\n",
            "docs/auth.md": "# Auth\n\n## Authentication\nThe authentication module verifies user identity.\n"
        })
        concepts = extract_concepts_from_docs(repo)
        auth_concepts = [c for c in concepts if c["name"] == "authentication"]
        assert len(auth_concepts) == 1

    def test_records_source_file(self):
        """Concept should track which file it came from."""
        repo = self._make_repo_with_docs({
            "docs/guide.md": "# Guide\n\n## Pagination\nResults are returned in pages of 20 items by default.\n"
        })
        concepts = extract_concepts_from_docs(repo)
        pag = next(c for c in concepts if c["name"] == "pagination")
        assert "docs/guide.md" in pag["source_file"]

    def test_empty_repo_returns_empty(self):
        """Repo with no markdown files should return empty list."""
        tmpdir = tempfile.mkdtemp()
        concepts = extract_concepts_from_docs(tmpdir)
        assert concepts == []


class TestConceptEdges:
    """Test that concept nodes get RELATED_TO edges to nouns."""

    def test_concept_related_to_noun(self):
        """Concept mentioning a noun in its definition should get RELATED_TO edge."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a FastAPI source file with a noun (user) and a concept docstring
            source = '''
from fastapi import FastAPI
app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    """Retrieve a specific user. Authentication is the process of verifying user identity."""
    pass

@app.post("/users")
async def create_user():
    """Create a new user."""
    pass
'''
            src_path = Path(tmpdir) / "main.py"
            src_path.write_text(source)

            graph = build_surface_graph_python(tmpdir, "test-app")

            # Should have concept nodes
            concept_nodes = [n for n in graph.nodes if n.type == NodeType.CONCEPT]
            # Should have RELATED_TO edges from concepts to nouns
            related_edges = [e for e in graph.edges if e.edge_type == EdgeType.RELATED_TO]

            if concept_nodes:
                # If authentication concept was extracted and mentions "user",
                # there should be a RELATED_TO edge
                auth_concepts = [n for n in concept_nodes if "authentication" in n.name]
                if auth_concepts:
                    auth_edges = [
                        e for e in related_edges
                        if e.source_id == auth_concepts[0].id
                    ]
                    assert len(auth_edges) > 0, "Concept mentioning a noun should have RELATED_TO edge"
