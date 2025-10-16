"""Tests for documentation parser.

Tests are based on docs/features/documentation-parsing.md specification.
Each test references specific requirements (R1-R4) and edge cases (EC1-EC4).
"""

import pytest
from pathlib import Path
from doczot_analyzer.docs_parser import (
    parse_markdown_file,
    find_markdown_files,
    scan_documentation,
)
from doczot_analyzer.models import DocReference


class TestMarkdownFileFinding:
    """Test R1: Find markdown files in documentation directories."""

    def test_finds_readme_in_root(self, tmp_path):
        """Test R1: Find README.md in root directory.

        Reference: documentation-parsing.md R1
        """
        readme = tmp_path / "README.md"
        readme.write_text("# Project")

        files = find_markdown_files(str(tmp_path))

        assert len(files) == 1
        assert "README.md" in files[0]

    def test_finds_files_in_docs_directory(self, tmp_path):
        """Test R1: Find markdown files in /docs/."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        (docs_dir / "api.md").write_text("# API")
        (docs_dir / "guide.md").write_text("# Guide")

        files = find_markdown_files(str(tmp_path))

        assert len(files) == 2
        assert any("api.md" in f for f in files)
        assert any("guide.md" in f for f in files)

    def test_finds_files_in_documentation_directory(self, tmp_path):
        """Test R1: Find markdown files in /documentation/."""
        docs_dir = tmp_path / "documentation"
        docs_dir.mkdir()

        (docs_dir / "setup.md").write_text("# Setup")

        files = find_markdown_files(str(tmp_path))

        assert len(files) == 1
        assert "setup.md" in files[0]

    def test_finds_api_related_files(self, tmp_path):
        """Test R1: Find files matching *api*.md pattern."""
        (tmp_path / "api-reference.md").write_text("# API")
        (tmp_path / "rest-api.md").write_text("# REST API")

        files = find_markdown_files(str(tmp_path))

        assert len(files) == 2
        assert any("api-reference.md" in f for f in files)
        assert any("rest-api.md" in f for f in files)

    def test_skips_changelog(self, tmp_path):
        """Test R1: Skip CHANGELOG.md."""
        (tmp_path / "CHANGELOG.md").write_text("# Changelog")
        (tmp_path / "README.md").write_text("# Project")

        files = find_markdown_files(str(tmp_path))

        assert len(files) == 1
        assert "README.md" in files[0]
        assert not any("CHANGELOG" in f for f in files)

    def test_skips_license_and_contributing(self, tmp_path):
        """Test R1: Skip LICENSE.md and CONTRIBUTING.md."""
        (tmp_path / "LICENSE.md").write_text("License")
        (tmp_path / "CONTRIBUTING.md").write_text("Contributing")
        (tmp_path / "README.md").write_text("# Project")

        files = find_markdown_files(str(tmp_path))

        assert len(files) == 1
        assert "README.md" in files[0]

    def test_skips_hidden_files(self, tmp_path):
        """Test R1: Skip hidden files (starting with .)."""
        (tmp_path / ".hidden.md").write_text("Hidden")
        (tmp_path / "visible.md").write_text("Visible")

        files = find_markdown_files(str(tmp_path))

        assert len(files) == 1
        assert "visible.md" in files[0]


class TestEndpointExtraction:
    """Test R2: Extract endpoint references from markdown."""

    def test_extracts_code_block_with_endpoint(self):
        """Test Example 1 from specification: Code block with endpoint.

        Reference: documentation-parsing.md Example 1
        Requirements: R2, R3
        """
        markdown_content = """## Authentication

To get an access token:

```
POST /api/auth/token
Content-Type: application/json
```
"""
        references = parse_markdown_file(markdown_content, "docs/auth.md")

        assert len(references) > 0
        ref = references[0]

        assert ref.file_path == "docs/auth.md"
        assert ref.section_heading == "Authentication"
        assert "/api/auth/token" in ref.mentioned_paths
        assert "POST" in ref.mentioned_methods
        assert "POST /api/auth/token" in ref.content

    def test_extracts_inline_code_endpoints(self):
        """Test Example 2 from specification: Inline documentation.

        Reference: documentation-parsing.md Example 2
        Requirements: R2, R3
        """
        markdown_content = """## Quick Start

First, create a user with `POST /api/users`.
Then retrieve it using `GET /api/users/{id}`.
"""
        references = parse_markdown_file(markdown_content, "docs/quickstart.md")

        assert len(references) > 0

        # Check that both endpoints are captured
        all_paths = []
        all_methods = []
        for ref in references:
            all_paths.extend(ref.mentioned_paths)
            all_methods.extend(ref.mentioned_methods)

        assert "/api/users" in all_paths
        assert "/api/users/{id}" in all_paths
        assert "POST" in all_methods
        assert "GET" in all_methods

    def test_extracts_table_endpoints(self):
        """Test Example 3 from specification: Table format.

        Reference: documentation-parsing.md Example 3
        Requirements: R2, R3
        """
        markdown_content = """## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /users | List all users |
| POST | /users | Create a user |
| DELETE | /users/{id} | Delete a user |
"""
        references = parse_markdown_file(markdown_content, "docs/api.md")

        assert len(references) > 0

        # Collect all mentioned paths and methods
        all_paths = []
        all_methods = []
        for ref in references:
            all_paths.extend(ref.mentioned_paths)
            all_methods.extend(ref.mentioned_methods)

        assert "/users" in all_paths
        assert "/users/{id}" in all_paths
        assert "GET" in all_methods
        assert "POST" in all_methods
        assert "DELETE" in all_methods

    def test_extracts_plain_text_endpoints(self):
        """Test plain text endpoint mentions (not in code blocks)."""
        markdown_content = """## API Overview

The API supports GET /users and POST /users endpoints.
"""
        references = parse_markdown_file(markdown_content, "docs/overview.md")

        assert len(references) > 0

        all_paths = []
        all_methods = []
        for ref in references:
            all_paths.extend(ref.mentioned_paths)
            all_methods.extend(ref.mentioned_methods)

        assert "/users" in all_paths
        assert "GET" in all_methods
        assert "POST" in all_methods


class TestContextCapture:
    """Test R3: Capture context information."""

    def test_captures_section_heading(self):
        """Test R3: Extract section heading."""
        markdown_content = """## User Management

Use `GET /users` to list users.

## Authentication

Use `POST /auth/login` to authenticate.
"""
        references = parse_markdown_file(markdown_content, "docs/api.md")

        assert len(references) >= 2

        # Find references by their paths
        user_ref = next((r for r in references if "/users" in r.mentioned_paths), None)
        auth_ref = next((r for r in references if "/auth/login" in r.mentioned_paths), None)

        assert user_ref is not None
        assert user_ref.section_heading == "User Management"

        assert auth_ref is not None
        assert auth_ref.section_heading == "Authentication"

    def test_captures_line_numbers(self):
        """Test R3: Track line numbers."""
        markdown_content = """## API

Line 3
Line 4
GET /users
"""
        references = parse_markdown_file(markdown_content, "docs/api.md")

        assert len(references) > 0
        ref = references[0]

        assert ref.line_number > 0

    def test_captures_content(self):
        """Test R3: Capture surrounding content."""
        markdown_content = """## Endpoints

Use GET /users to fetch all users from the database.
"""
        references = parse_markdown_file(markdown_content, "docs/api.md")

        assert len(references) > 0
        ref = references[0]

        assert ref.content is not None
        assert len(ref.content) > 0

    def test_sets_file_path(self):
        """Test R3: Set file path correctly."""
        markdown_content = "GET /test"
        references = parse_markdown_file(markdown_content, "docs/test.md")

        assert len(references) > 0
        assert references[0].file_path == "docs/test.md"


class TestPathFormats:
    """Test R4: Handle various path formats."""

    def test_handles_simple_paths(self):
        """Test R4: Simple paths like /users.

        Reference: documentation-parsing.md R4
        """
        markdown_content = "GET /users"
        references = parse_markdown_file(markdown_content, "docs/api.md")

        assert len(references) > 0
        paths = references[0].mentioned_paths
        assert "/users" in paths

    def test_handles_path_parameters(self):
        """Test R4: Paths with parameters like /users/{id}."""
        markdown_content = "GET /users/{user_id}"
        references = parse_markdown_file(markdown_content, "docs/api.md")

        assert len(references) > 0
        paths = references[0].mentioned_paths
        assert "/users/{user_id}" in paths

    def test_handles_api_prefix(self):
        """Test R4: Paths with API prefix like /api/v1/users."""
        markdown_content = "GET /api/v1/users"
        references = parse_markdown_file(markdown_content, "docs/api.md")

        assert len(references) > 0
        paths = references[0].mentioned_paths
        assert "/api/v1/users" in paths

    def test_handles_multiple_parameters(self):
        """Test R4: Paths with multiple parameters."""
        markdown_content = "GET /orgs/{org_id}/repos/{repo_id}"
        references = parse_markdown_file(markdown_content, "docs/api.md")

        assert len(references) > 0
        paths = references[0].mentioned_paths
        assert "/orgs/{org_id}/repos/{repo_id}" in paths

    def test_handles_colon_style_parameters(self):
        """Test R4: Alternative parameter style /users/:id."""
        markdown_content = "GET /users/:id"
        references = parse_markdown_file(markdown_content, "docs/api.md")

        assert len(references) > 0
        paths = references[0].mentioned_paths
        # Should capture the path
        assert len(paths) > 0


class TestEdgeCases:
    """Test edge cases from specification."""

    def test_handles_empty_markdown(self):
        """Test EC1: Empty file.

        Reference: documentation-parsing.md EC1
        """
        markdown_content = ""
        references = parse_markdown_file(markdown_content, "docs/empty.md")

        assert references == []

    def test_handles_markdown_without_endpoints(self):
        """Test EC2: No endpoint references.

        Reference: documentation-parsing.md EC2
        """
        markdown_content = """## Introduction

This is a project about documentation.
There are no API endpoints mentioned here.
"""
        references = parse_markdown_file(markdown_content, "docs/intro.md")

        assert references == []

    def test_ignores_commented_code(self):
        """Test EC3: HTML comments with endpoints.

        Reference: documentation-parsing.md EC3
        """
        markdown_content = """## API

<!--
GET /api/internal
This endpoint is commented out
-->

GET /api/public
"""
        references = parse_markdown_file(markdown_content, "docs/api.md")

        # Should only find the public endpoint
        all_paths = []
        for ref in references:
            all_paths.extend(ref.mentioned_paths)

        assert "/api/public" in all_paths
        # Should NOT find the commented endpoint
        assert "/api/internal" not in all_paths

    def test_handles_various_path_formats(self):
        """Test EC4: Similar path variations.

        Reference: documentation-parsing.md EC4
        """
        markdown_content = """## Variations

- GET /users/{id}
- GET /users/{user_id}
- GET /users/:id
"""
        references = parse_markdown_file(markdown_content, "docs/api.md")

        all_paths = []
        for ref in references:
            all_paths.extend(ref.mentioned_paths)

        # Should capture all variations
        assert len(all_paths) >= 3


class TestMultipleEndpointsInFile:
    """Test files with multiple endpoint references."""

    def test_handles_multiple_sections(self):
        """Test multiple sections with different endpoints."""
        markdown_content = """## Users

GET /users - List users
POST /users - Create user

## Posts

GET /posts - List posts
POST /posts - Create post
"""
        references = parse_markdown_file(markdown_content, "docs/api.md")

        assert len(references) >= 2

        all_paths = []
        for ref in references:
            all_paths.extend(ref.mentioned_paths)

        assert "/users" in all_paths
        assert "/posts" in all_paths

    def test_handles_mixed_formats(self):
        """Test file with code blocks and inline code."""
        markdown_content = """## API

Use `GET /users` to list users.

Example:
```
POST /users
{"name": "John"}
```
"""
        references = parse_markdown_file(markdown_content, "docs/api.md")

        all_paths = []
        for ref in references:
            all_paths.extend(ref.mentioned_paths)

        assert "/users" in all_paths


class TestHTTPMethods:
    """Test detection of all HTTP methods."""

    def test_detects_all_http_methods(self):
        """Test R2: Recognize all HTTP methods."""
        markdown_content = """## Methods

- GET /test
- POST /test
- PUT /test
- DELETE /test
- PATCH /test
- OPTIONS /test
- HEAD /test
"""
        references = parse_markdown_file(markdown_content, "docs/methods.md")

        all_methods = []
        for ref in references:
            all_methods.extend(ref.mentioned_methods)

        expected_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}
        for method in expected_methods:
            assert method in all_methods

    def test_case_insensitive_methods(self):
        """Test that HTTP methods are normalized to uppercase."""
        markdown_content = """## API

- get /users
- Post /users
- DELETE /users
"""
        references = parse_markdown_file(markdown_content, "docs/api.md")

        all_methods = []
        for ref in references:
            all_methods.extend(ref.mentioned_methods)

        # Methods should be normalized to uppercase
        assert "GET" in all_methods
        assert "POST" in all_methods
        assert "DELETE" in all_methods


class TestDirectoryScanning:
    """Test scan_documentation function."""

    def test_scans_multiple_markdown_files(self, tmp_path):
        """Test scanning entire documentation directory."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        (docs_dir / "api.md").write_text("GET /users")
        (docs_dir / "auth.md").write_text("POST /auth/login")

        references = scan_documentation(str(tmp_path))

        assert len(references) >= 2

        all_paths = []
        for ref in references:
            all_paths.extend(ref.mentioned_paths)

        assert "/users" in all_paths
        assert "/auth/login" in all_paths

    def test_handles_nested_directories(self, tmp_path):
        """Test scanning nested documentation directories."""
        docs_dir = tmp_path / "docs" / "api"
        docs_dir.mkdir(parents=True)

        (docs_dir / "v1.md").write_text("GET /api/v1/users")

        references = scan_documentation(str(tmp_path))

        all_paths = []
        for ref in references:
            all_paths.extend(ref.mentioned_paths)

        assert "/api/v1/users" in all_paths

    def test_returns_empty_list_for_no_docs(self, tmp_path):
        """Test scanning directory with no markdown files."""
        references = scan_documentation(str(tmp_path))

        assert references == []


class TestMatchingEndpoints:
    """Test DocReference.matches_endpoint() method."""

    def test_matches_endpoint_with_same_method_and_path(self):
        """Test that matching works correctly."""
        from doczot_analyzer.models import Endpoint, Parameter

        doc_ref = DocReference(
            file_path="docs/api.md",
            content="GET /users",
            mentioned_paths=["/users"],
            mentioned_methods=["GET"],
            section_heading="API",
            line_number=1
        )

        endpoint = Endpoint(
            method="GET",
            path="/users",
            function_name="get_users",
            file_path="api.py",
            line_number=10
        )

        assert doc_ref.matches_endpoint(endpoint) is True

    def test_does_not_match_different_method(self):
        """Test that different methods don't match."""
        from doczot_analyzer.models import Endpoint

        doc_ref = DocReference(
            file_path="docs/api.md",
            content="GET /users",
            mentioned_paths=["/users"],
            mentioned_methods=["GET"],
        )

        endpoint = Endpoint(
            method="POST",
            path="/users",
            function_name="create_user",
            file_path="api.py",
            line_number=20
        )

        assert doc_ref.matches_endpoint(endpoint) is False

    def test_does_not_match_different_path(self):
        """Test that different paths don't match."""
        from doczot_analyzer.models import Endpoint

        doc_ref = DocReference(
            file_path="docs/api.md",
            content="GET /users",
            mentioned_paths=["/users"],
            mentioned_methods=["GET"],
        )

        endpoint = Endpoint(
            method="GET",
            path="/posts",
            function_name="get_posts",
            file_path="api.py",
            line_number=30
        )

        assert doc_ref.matches_endpoint(endpoint) is False
