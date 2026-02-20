"""Tests for the OpenAPI comparison validator."""
import json
import tempfile
from pathlib import Path

from doczot_analyzer.models_v2 import (
    SystemGraph,
    SystemNode,
    NodeType,
)
from validation.validators.openapi_compare import (
    compare_openapi,
    load_openapi_spec,
    validate_openapi,
    _normalize_path,
    _extract_openapi_endpoints,
    _extract_graph_endpoints,
)
from validation.models import ValidationStatus


def _verb(name: str, path: str, method: str = "GET") -> SystemNode:
    return SystemNode(
        id=f"verb:{method}:{path}",
        type=NodeType.VERB,
        name=name,
        http_method=method,
        http_path=path,
    )


def _make_graph(verbs: list[SystemNode]) -> SystemGraph:
    return SystemGraph(product_name="test", nodes=verbs)


def _make_spec(endpoints: list[tuple[str, str]]) -> dict:
    """Build a minimal OpenAPI spec from (method, path) pairs."""
    paths: dict = {}
    for method, path in endpoints:
        if path not in paths:
            paths[path] = {}
        paths[path][method.lower()] = {
            "summary": f"{method} {path}",
            "responses": {"200": {"description": "OK"}},
        }
    return {
        "openapi": "3.0.0",
        "info": {"title": "Test", "version": "1.0.0"},
        "paths": paths,
    }


class TestNormalizePath:
    def test_strips_trailing_slash(self):
        assert _normalize_path("/users/") == "/users"

    def test_root_preserved(self):
        assert _normalize_path("/") == "/"

    def test_no_trailing_slash(self):
        assert _normalize_path("/users") == "/users"


class TestExtractOpenAPIEndpoints:
    def test_basic_extraction(self):
        spec = _make_spec([("GET", "/users"), ("POST", "/users")])
        eps = _extract_openapi_endpoints(spec)
        assert ("GET", "/users") in eps
        assert ("POST", "/users") in eps
        assert len(eps) == 2

    def test_ignores_non_http_methods(self):
        spec = {
            "paths": {
                "/users": {
                    "get": {"summary": "get"},
                    "parameters": [{"name": "id"}],  # not an HTTP method
                }
            }
        }
        eps = _extract_openapi_endpoints(spec)
        assert len(eps) == 1

    def test_empty_paths(self):
        spec = {"paths": {}}
        assert _extract_openapi_endpoints(spec) == set()


class TestExtractGraphEndpoints:
    def test_extracts_verb_nodes(self):
        graph = _make_graph([
            _verb("get_users", "/users", "GET"),
            _verb("create_user", "/users", "POST"),
        ])
        eps = _extract_graph_endpoints(graph)
        assert ("GET", "/users") in eps
        assert ("POST", "/users") in eps

    def test_ignores_non_verb_nodes(self):
        noun = SystemNode(id="noun:user", type=NodeType.NOUN, name="user")
        graph = _make_graph([noun])
        eps = _extract_graph_endpoints(graph)
        assert len(eps) == 0


class TestCompareOpenAPI:
    def test_perfect_match(self):
        graph = _make_graph([
            _verb("get_users", "/users", "GET"),
            _verb("create_user", "/users", "POST"),
        ])
        spec = _make_spec([("GET", "/users"), ("POST", "/users")])
        result, details = compare_openapi(graph, spec)
        assert result.status == ValidationStatus.PASS
        assert len(details["in_both"]) == 2
        assert len(details["openapi_only"]) == 0
        assert len(details["doczot_only"]) == 0

    def test_doczot_misses_endpoint(self):
        graph = _make_graph([_verb("get_users", "/users", "GET")])
        spec = _make_spec([("GET", "/users"), ("POST", "/users")])
        result, details = compare_openapi(graph, spec)
        assert result.status == ValidationStatus.FAIL
        assert len(details["openapi_only"]) == 1
        assert "POST /users" in details["openapi_only"][0]

    def test_doczot_has_extra(self):
        graph = _make_graph([
            _verb("get_users", "/users", "GET"),
            _verb("delete_user", "/users/{id}", "DELETE"),
        ])
        spec = _make_spec([("GET", "/users")])
        result, details = compare_openapi(graph, spec)
        assert result.status == ValidationStatus.WARN
        assert len(details["doczot_only"]) == 1

    def test_both_empty(self):
        graph = _make_graph([])
        spec = _make_spec([])
        result, details = compare_openapi(graph, spec)
        assert result.status == ValidationStatus.PASS

    def test_trailing_slash_normalization(self):
        graph = _make_graph([_verb("get_users", "/users/", "GET")])
        spec = _make_spec([("GET", "/users")])
        result, details = compare_openapi(graph, spec)
        assert result.status == ValidationStatus.PASS


class TestLoadOpenAPISpec:
    def test_load_json_file(self):
        spec = _make_spec([("GET", "/users")])
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(spec, f)
            f.flush()
            loaded = load_openapi_spec(f.name)
        assert loaded["paths"]["/users"]["get"]["summary"] == "GET /users"

    def test_file_not_found(self):
        try:
            load_openapi_spec("/nonexistent/openapi.json")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "not found" in str(e)


class TestValidateOpenAPI:
    def test_with_valid_spec(self):
        graph = _make_graph([_verb("get_users", "/users", "GET")])
        spec = _make_spec([("GET", "/users")])
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(spec, f)
            f.flush()
            results = validate_openapi(graph, f.name)
        assert len(results) == 1
        assert results[0].status == ValidationStatus.PASS

    def test_with_missing_file(self):
        graph = _make_graph([])
        results = validate_openapi(graph, "/nonexistent.json")
        assert len(results) == 1
        assert results[0].status == ValidationStatus.SKIPPED
