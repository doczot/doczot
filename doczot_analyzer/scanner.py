"""FastAPI endpoint scanner using AST parsing.

This module scans Python source code to detect FastAPI endpoints.
Based on docs/features/endpoint-detection.md specification.

Uses Python's built-in ast module for parsing - no external dependencies.
"""

import ast
import os
from pathlib import Path
from typing import List, Optional

from doczot_analyzer.models import Endpoint, Parameter


def scan_python_file(source_code: str, file_path: str) -> List[Endpoint]:
    """Scan Python source code for FastAPI endpoints using AST parsing.

    Args:
        source_code: Python source code as string
        file_path: Path to the file (for reference in results)

    Returns:
        List of detected Endpoint objects

    Raises:
        SyntaxError: If source_code contains invalid Python syntax
    """
    if not source_code or not source_code.strip():
        return []

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        # Re-raise syntax errors - let caller handle them
        raise

    endpoints = []

    # Walk the AST tree looking for function definitions
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            endpoint = _extract_endpoint_from_function(node, file_path)
            if endpoint:
                endpoints.append(endpoint)

    return endpoints


def _extract_endpoint_from_function(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    file_path: str
) -> Optional[Endpoint]:
    """Extract endpoint information from a function definition node.

    Args:
        func_node: AST node representing a function definition
        file_path: Path to the file containing this function

    Returns:
        Endpoint object if this is a FastAPI endpoint, None otherwise
    """
    # Check if function has FastAPI decorators
    for decorator in func_node.decorator_list:
        endpoint_info = _parse_fastapi_decorator(decorator)
        if endpoint_info:
            method, path, response_model, is_deprecated = endpoint_info

            # Extract docstring
            docstring = ast.get_docstring(func_node)
            has_docstring = docstring is not None

            # Extract parameters
            parameters = _extract_parameters(func_node, path)

            # Determine if function is async
            is_async = isinstance(func_node, ast.AsyncFunctionDef)

            return Endpoint(
                method=method,
                path=path,
                function_name=func_node.name,
                file_path=file_path,
                line_number=func_node.lineno,
                docstring=docstring,
                has_docstring=has_docstring,
                parameters=parameters,
                response_model=response_model,
                is_deprecated=is_deprecated,
                is_async=is_async,
            )

    return None


def _parse_fastapi_decorator(decorator: ast.expr) -> Optional[tuple]:
    """Parse a decorator to check if it's a FastAPI route decorator.

    Supports patterns:
    - @app.get(path)
    - @router.post(path)
    - @app.put(path, response_model=Model, deprecated=True)

    Args:
        decorator: AST decorator node

    Returns:
        Tuple of (method, path, response_model, is_deprecated) if FastAPI decorator,
        None otherwise
    """
    # Decorator must be a Call node (has parentheses)
    if not isinstance(decorator, ast.Call):
        return None

    # Decorator must be attribute access (e.g., app.get, router.post)
    if not isinstance(decorator.func, ast.Attribute):
        return None

    # Get the HTTP method from the attribute name
    method = decorator.func.attr.upper()

    # Check if it's a valid HTTP method
    valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}
    if method not in valid_methods:
        return None

    # Get the base object (should be 'app' or 'router')
    if isinstance(decorator.func.value, ast.Name):
        base_name = decorator.func.value.id
        # Accept 'app' or 'router' as valid FastAPI objects
        if base_name not in {"app", "router"}:
            return None
    else:
        return None

    # Extract the path (first positional argument)
    if not decorator.args:
        return None

    path_arg = decorator.args[0]
    if not isinstance(path_arg, ast.Constant):
        return None

    path = path_arg.value
    if not isinstance(path, str):
        return None

    # Extract optional keyword arguments
    response_model = None
    is_deprecated = False

    for keyword in decorator.keywords:
        if keyword.arg == "response_model":
            if isinstance(keyword.value, ast.Name):
                response_model = keyword.value.id
        elif keyword.arg == "deprecated":
            if isinstance(keyword.value, ast.Constant):
                is_deprecated = bool(keyword.value.value)

    return (method, path, response_model, is_deprecated)


def _extract_parameters(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    path: str
) -> List[Parameter]:
    """Extract parameters from a function definition.

    Determines parameter location (path/query/body) based on:
    - Path parameters: mentioned in the path string (e.g., {user_id})
    - Body parameters: custom types (usually Pydantic models)
    - Query parameters: everything else (typically with defaults)

    Args:
        func_node: AST function definition node
        path: The endpoint path (to identify path parameters)

    Returns:
        List of Parameter objects
    """
    parameters = []
    args = func_node.args

    # Extract path parameter names from the path
    path_param_names = _extract_path_param_names(path)

    # Process each argument
    for i, arg in enumerate(args.args):
        param_name = arg.arg

        # Skip 'self' and 'cls' parameters
        if param_name in {"self", "cls"}:
            continue

        # Extract type hint
        type_hint = None
        if arg.annotation:
            type_hint = _extract_type_annotation(arg.annotation)

        # Determine if parameter has a default value
        default_value = None
        required = True

        # Defaults are stored in reverse order
        num_defaults = len(args.defaults)
        num_args = len(args.args)
        default_offset = i - (num_args - num_defaults)

        if default_offset >= 0:
            default_node = args.defaults[default_offset]
            default_value = _extract_default_value(default_node)
            required = False

        # Determine parameter location
        location = _determine_parameter_location(
            param_name, type_hint, path_param_names
        )

        parameters.append(
            Parameter(
                name=param_name,
                type_hint=type_hint,
                location=location,
                required=required,
                default_value=default_value,
            )
        )

    return parameters


def _extract_path_param_names(path: str) -> set:
    """Extract parameter names from a path string.

    Examples:
        "/users/{user_id}" -> {"user_id"}
        "/orgs/{org_id}/repos/{repo_id}" -> {"org_id", "repo_id"}
        "/items/{item_id:int}" -> {"item_id"}

    Args:
        path: URL path string

    Returns:
        Set of parameter names found in the path
    """
    import re

    # Match {param_name} or {param_name:type}
    pattern = r'\{([^}:]+)(?::[^}]*)?\}'
    matches = re.findall(pattern, path)
    return set(matches)


def _extract_type_annotation(annotation: ast.expr) -> str:
    """Extract type annotation as a string.

    Handles:
    - Simple types: int, str, bool
    - Names: UserCreate, Item
    - Complex types: Optional[str], List[int]

    Args:
        annotation: AST annotation node

    Returns:
        String representation of the type
    """
    if isinstance(annotation, ast.Name):
        return annotation.id
    elif isinstance(annotation, ast.Constant):
        return str(annotation.value)
    elif isinstance(annotation, ast.Subscript):
        # Handle generic types like Optional[str], List[int]
        return ast.unparse(annotation)
    else:
        # Fallback: use ast.unparse for complex types
        try:
            return ast.unparse(annotation)
        except Exception:
            return None


def _extract_default_value(default_node: ast.expr) -> str:
    """Extract default value as a string.

    Args:
        default_node: AST node representing the default value

    Returns:
        String representation of the default value
    """
    if isinstance(default_node, ast.Constant):
        return str(default_node.value)
    elif isinstance(default_node, ast.Name):
        return default_node.id
    else:
        # For complex defaults, use ast.unparse
        try:
            return ast.unparse(default_node)
        except Exception:
            return "..."


def _determine_parameter_location(
    param_name: str,
    type_hint: Optional[str],
    path_param_names: set
) -> str:
    """Determine where a parameter is used (path/query/body).

    Logic:
    - If parameter name is in the path, it's a path parameter
    - If type hint looks like a custom model (capitalized), it's a body parameter
    - Otherwise, it's a query parameter

    Args:
        param_name: Name of the parameter
        type_hint: Type hint string (or None)
        path_param_names: Set of parameter names found in the path

    Returns:
        "path", "query", or "body"
    """
    # Check if it's a path parameter
    if param_name in path_param_names:
        return "path"

    # Check if it's likely a body parameter (Pydantic model)
    # Heuristic: capitalized type names are usually models
    if type_hint and type_hint[0].isupper() and not type_hint.startswith("Optional"):
        # Common built-in types that are capitalized but not models
        builtin_types = {"List", "Dict", "Set", "Tuple", "Optional", "Union"}
        if type_hint.split("[")[0] not in builtin_types:
            return "body"

    # Default to query parameter
    return "query"


def scan_directory(directory_path: str) -> List[Endpoint]:
    """Scan all Python files in a directory for FastAPI endpoints.

    Recursively scans the directory for .py files and extracts endpoints.

    Args:
        directory_path: Path to the directory to scan

    Returns:
        List of all endpoints found across all files

    Raises:
        FileNotFoundError: If directory_path doesn't exist
    """
    directory = Path(directory_path)

    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory_path}")

    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory_path}")

    all_endpoints = []

    # Recursively find all .py files
    for py_file in directory.rglob("*.py"):
        # Skip common non-source directories and example/doc code
        parts = py_file.parts
        skip_dirs = {"__pycache__", ".venv", "venv", ".git", "node_modules", "tests", "test", "docs_src", "examples", "example"}
        if any(skip_dir in parts for skip_dir in skip_dirs):
            continue

        # Skip test files (test_*.py, *_test.py)
        if py_file.name.startswith("test_") or py_file.name.endswith("_test.py"):
            continue

        try:
            source_code = py_file.read_text(encoding="utf-8")
            # Use relative path from the scan directory
            relative_path = py_file.relative_to(directory)
            endpoints = scan_python_file(source_code, str(relative_path))
            all_endpoints.extend(endpoints)
        except (SyntaxError, UnicodeDecodeError):
            # Skip files with syntax errors or encoding issues
            continue

    return all_endpoints
