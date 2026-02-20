"""OpenAPI comparison validator.

Compares DocZot's SystemGraph against a FastAPI app's generated OpenAPI spec
to triangulate surface area completeness.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from doczot_analyzer.models_v2 import SystemGraph, NodeType
from validation.models import (
    CheckResult,
    ValidationDimension,
    ValidationStatus,
)

DIMENSION = ValidationDimension.SURFACE_COMPLETENESS


def _normalize_path(path: str) -> str:
    """Normalize path for comparison.

    OpenAPI uses {param} style, DocZot may use {param} or :param.
    Strip trailing slashes for consistency.
    """
    return path.rstrip("/") or "/"


def _extract_openapi_endpoints(spec: dict) -> set[tuple[str, str]]:
    """Extract (METHOD, path) pairs from an OpenAPI spec."""
    endpoints: set[tuple[str, str]] = set()
    paths = spec.get("paths", {})
    for path, methods in paths.items():
        normalized = _normalize_path(path)
        for method in methods:
            if method.lower() in ("get", "post", "put", "patch", "delete", "head", "options"):
                endpoints.add((method.upper(), normalized))
    return endpoints


def _extract_graph_endpoints(graph: SystemGraph) -> set[tuple[str, str]]:
    """Extract (METHOD, path) pairs from SystemGraph verb nodes."""
    endpoints: set[tuple[str, str]] = set()
    for node in graph.nodes:
        if node.type == NodeType.VERB and node.http_method and node.http_path:
            normalized = _normalize_path(node.http_path)
            endpoints.add((node.http_method.upper(), normalized))
    return endpoints


def load_openapi_spec(source: str) -> dict:
    """Load an OpenAPI spec from a file path or URL.

    Args:
        source: Path to a JSON/YAML file, or an HTTP(S) URL.

    Returns:
        Parsed OpenAPI spec as a dict.

    Raises:
        ValueError: If the source cannot be loaded.
    """
    if source.startswith("http://") or source.startswith("https://"):
        try:
            import httpx
        except ImportError:
            raise ValueError(
                "httpx is required for URL-based OpenAPI loading. "
                "Install with: pip install httpx"
            )
        response = httpx.get(source, timeout=10.0)
        response.raise_for_status()
        return response.json()

    path = Path(source)
    if not path.exists():
        raise ValueError(f"OpenAPI spec file not found: {source}")

    text = path.read_text()
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml
            return yaml.safe_load(text)
        except ImportError:
            raise ValueError(
                "PyYAML is required for YAML OpenAPI specs. "
                "Install with: pip install pyyaml"
            )
    return json.loads(text)


def compare_openapi(
    graph: SystemGraph,
    spec: dict,
) -> tuple[CheckResult, dict]:
    """Compare SystemGraph endpoints against an OpenAPI spec.

    Returns:
        A tuple of (CheckResult, details_dict) where details_dict contains:
        - in_both: endpoints found in both sources
        - openapi_only: endpoints in OpenAPI but not in DocZot (false negatives)
        - doczot_only: endpoints in DocZot but not in OpenAPI
    """
    openapi_eps = _extract_openapi_endpoints(spec)
    graph_eps = _extract_graph_endpoints(graph)

    in_both = openapi_eps & graph_eps
    openapi_only = openapi_eps - graph_eps
    doczot_only = graph_eps - openapi_eps

    comparison = {
        "in_both": sorted(f"{m} {p}" for m, p in in_both),
        "openapi_only": sorted(f"{m} {p}" for m, p in openapi_only),
        "doczot_only": sorted(f"{m} {p}" for m, p in doczot_only),
    }

    details = []
    if openapi_only:
        details.append(f"DocZot missed {len(openapi_only)} endpoint(s):")
        details.extend(f"  - {ep}" for ep in comparison["openapi_only"])
    if doczot_only:
        details.append(f"DocZot found {len(doczot_only)} endpoint(s) not in OpenAPI:")
        details.extend(f"  - {ep}" for ep in comparison["doczot_only"])

    if openapi_only:
        status = ValidationStatus.FAIL
        message = (
            f"{len(in_both)} matched, {len(openapi_only)} missed by DocZot, "
            f"{len(doczot_only)} extra in DocZot"
        )
    elif doczot_only:
        status = ValidationStatus.WARN
        message = (
            f"All {len(in_both)} OpenAPI endpoints found. "
            f"{len(doczot_only)} extra endpoint(s) in DocZot (may be test artifacts)"
        )
    else:
        status = ValidationStatus.PASS
        message = f"Perfect match: {len(in_both)} endpoints in both sources"

    result = CheckResult(
        name="openapi_comparison",
        dimension=DIMENSION,
        status=status,
        message=message,
        details=details,
    )
    return result, comparison


def validate_openapi(
    graph: SystemGraph,
    openapi_source: str,
) -> list[CheckResult]:
    """Run OpenAPI comparison validation.

    Args:
        graph: The SystemGraph to validate.
        openapi_source: Path or URL to the OpenAPI spec.
    """
    try:
        spec = load_openapi_spec(openapi_source)
    except (ValueError, Exception) as e:
        return [CheckResult(
            name="openapi_comparison",
            dimension=DIMENSION,
            status=ValidationStatus.SKIPPED,
            message=f"Could not load OpenAPI spec: {e}",
        )]

    result, _ = compare_openapi(graph, spec)
    return [result]
