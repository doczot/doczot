"""FastAPI endpoint scanner using AST parsing.

This module scans Python source code to detect FastAPI endpoints.
Based on docs/features/endpoint-detection.md specification.

Uses Python's built-in ast module for parsing - no external dependencies.
"""

import ast
import os
import re
from pathlib import Path
from typing import List, Optional, Set

from doczot_analyzer.models import Endpoint, Parameter


# Common entity patterns to detect in code
ENTITY_PATTERN = re.compile(r'^([A-Z][a-z]+)+$')  # PascalCase like User, UserCreate


def _singularize(name: str) -> str:
    """Convert a name to singular lowercase form."""
    name = name.lower()
    if name.endswith('ies'):
        return name[:-3] + 'y'
    elif name.endswith('es') and len(name) > 3:
        return name[:-2]
    elif name.endswith('s') and not name.endswith('ss'):
        return name[:-1]
    return name


def _extract_entity_from_type(type_name: str) -> Optional[str]:
    """Extract base entity from a type name like UserCreate, UserPublic, etc."""
    if not type_name or not ENTITY_PATTERN.match(type_name):
        return None

    # Strip database prefixes first
    result = type_name
    db_prefixes = ['DB', 'Db', 'db_']
    for prefix in db_prefixes:
        if result.startswith(prefix):
            result = result[len(prefix):]
            # Capitalize first letter if it was lowercased
            if result and result[0].islower():
                result = result[0].upper() + result[1:]
            break

    # Common suffixes to strip (DTO patterns)
    # Note: Order matters - longer suffixes first to avoid partial matches
    suffixes = [
        # Compound suffixes (check first)
        'InDB', 'InDb', 'CreateIn', 'UpdateIn', 'ReadOut', 'WriteOut',
        # Standard CRUD suffixes
        'Create', 'Update', 'Delete', 'Read', 'Write',
        # Access level suffixes
        'Public', 'Private', 'Internal', 'Admin',
        # Schema/model suffixes
        'Base', 'Schema', 'Model', 'DTO', 'Entity',
        # Request/Response suffixes
        'Response', 'Request', 'Payload',
        # Input/Output suffixes (Pydantic patterns)
        'Input', 'Output', 'In', 'Out',
        # Auth-related suffixes
        'Login', 'Logout', 'Register', 'Auth',
        # Form suffixes
        'Form', 'Edit', 'View', 'Detail', 'Summary', 'List',
        # Database suffixes
        'Table', 'Row', 'Record',
        # Setting/Config suffixes
        'Setting', 'Settings', 'Config', 'Configuration',
    ]

    for suffix in suffixes:
        # Case-insensitive suffix check
        if result.lower().endswith(suffix.lower()) and len(result) > len(suffix):
            result = result[:-len(suffix)]
            break

    # Skip common non-entity types (infrastructure, not domain)
    skip_types = {'Any', 'List', 'Dict', 'Set', 'Tuple', 'Optional', 'Union',
                  'Annotated', 'Depends', 'Query', 'Path', 'Body', 'Header',
                  'Message', 'Token', 'Session', 'Response', 'Request', 'HTML',
                  'SessionDep', 'CurrentUser', 'Str', 'Int', 'Bool', 'Float',
                  'HTTPException', 'EmailStr', 'NewPassword', 'Form', 'File',
                  'UploadFile', 'BackgroundTasks', 'Callable', 'Coroutine',
                  'Cookie', 'Context', 'Settings', 'Config', 'Pagination',
                  'Filter', 'Sort', 'Order', 'Page', 'Limit', 'Offset',
                  'My', 'Current', 'Self', 'Ready', 'Check', 'Health',
                  'Status', 'Info', 'Version', 'Meta', 'Metadata'}

    if result in skip_types:
        return None

    # Skip if result is too short or too generic
    if len(result) < 3:
        return None

    return result.lower()


def _extract_entities_from_body(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> Set[str]:
    """Extract entity references from function body.

    Detects patterns like:
    - user = crud.get_user_by_email(...)
    - user = crud.authenticate(...)
    - item = session.get(Item, id)
    """
    entities = set()

    for node in ast.walk(func_node):
        # Pattern 1: Variable assignments with entity-like names
        # e.g., user = ..., item = ..., post = ...
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    var_name = target.id.lower()
                    # Skip common non-entity variables (infrastructure, not domain)
                    skip_vars = {
                        # Database/ORM
                        'session', 'db', 'conn', 'connection', 'cursor', 'transaction',
                        'statement', 'query', 'result', 'results', 'rows', 'record',
                        # HTTP/Request
                        'request', 'response', 'form', 'body', 'headers', 'cookies',
                        'params', 'args', 'kwargs', 'data', 'payload', 'content',
                        # Auth
                        'token', 'email', 'password', 'credentials', 'access', 'hashed',
                        'expires', 'secret', 'key', 'api_key', 'apikey',
                        # Common variables
                        'config', 'settings', 'options', 'context', 'ctx',
                        'count', 'total', 'index', 'i', 'j', 'k', 'n', 'x', 'y',
                        'value', 'values', 'obj', 'model', 'schema', 'instance',
                        # Messaging
                        'subject', 'html', 'text', 'message', 'msg', 'notification',
                        # Errors
                        'error', 'err', 'exception', 'exc', 'status', 'code',
                        # Plurals of common entities (should use singular form)
                        'items', 'users', 'posts', 'tasks', 'jobs', 'files',
                        # Generic words that are NOT entities
                        'all', 'single', 'one', 'many', 'multi', 'new', 'old',
                        'first', 'last', 'current', 'next', 'prev', 'previous',
                        'tmp', 'temp', 'cache', 'buffer', 'output', 'input',
                        'cookie', 'ready', 'check', 'health', 'info', 'meta',
                    }
                    if var_name not in skip_vars:
                        # Check if it looks like an entity (short, noun-like)
                        if len(var_name) > 2 and len(var_name) < 15 and var_name.isalpha():
                            entities.add(var_name)

        # Pattern 2: CRUD-style function calls
        # e.g., crud.get_user_by_email, crud.create_item
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                attr_name = node.func.attr
                # Match patterns like get_user, create_user, get_user_by_email
                for prefix in ['get_', 'create_', 'update_', 'delete_', 'authenticate_']:
                    if attr_name.startswith(prefix):
                        remainder = attr_name[len(prefix):]
                        # Extract entity: get_user_by_email -> user
                        entity = remainder.split('_')[0] if '_' in remainder else remainder
                        if entity and len(entity) > 2:
                            entities.add(_singularize(entity))
                        break

        # Pattern 3: session.get(Model, id) or db.query(Model)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ('get', 'query', 'add', 'delete'):
                    if node.args and isinstance(node.args[0], ast.Name):
                        model_name = node.args[0].id
                        entity = _extract_entity_from_type(model_name)
                        if entity:
                            entities.add(entity)

    return entities


def _extract_entities_from_types(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    response_model: Optional[str] = None
) -> Set[str]:
    """Extract entity references from type hints and response_model."""
    entities = set()

    # From response_model
    if response_model:
        entity = _extract_entity_from_type(response_model)
        if entity:
            entities.add(entity)

    # From return type annotation
    if func_node.returns:
        return_type = _get_type_name(func_node.returns)
        if return_type:
            entity = _extract_entity_from_type(return_type)
            if entity:
                entities.add(entity)

    # From parameter type hints
    for arg in func_node.args.args:
        if arg.annotation:
            type_name = _get_type_name(arg.annotation)
            if type_name:
                entity = _extract_entity_from_type(type_name)
                if entity:
                    entities.add(entity)

    return entities


def _get_type_name(annotation: ast.expr) -> Optional[str]:
    """Extract type name from an annotation node."""
    if isinstance(annotation, ast.Name):
        return annotation.id
    elif isinstance(annotation, ast.Subscript):
        # Handle List[User], Optional[User], etc.
        if isinstance(annotation.slice, ast.Name):
            return annotation.slice.id
        elif isinstance(annotation.slice, ast.Subscript):
            return _get_type_name(annotation.slice)
    elif isinstance(annotation, ast.Attribute):
        return annotation.attr
    return None


def _extract_router_prefixes(tree: ast.Module) -> dict[str, str]:
    """Extract router prefix mappings from APIRouter assignments.

    Detects patterns like:
    - router = APIRouter(prefix="/users")
    - items_router = APIRouter(prefix="/items", tags=["items"])

    Returns:
        Dict mapping variable names to their prefixes (e.g., {"router": "/users"})
    """
    prefixes = {}

    for node in ast.walk(tree):
        # Look for assignments: router = APIRouter(...)
        if isinstance(node, ast.Assign):
            # Check if right side is a Call to APIRouter
            if isinstance(node.value, ast.Call):
                # Check if it's APIRouter
                func = node.value.func
                is_apirouter = False

                if isinstance(func, ast.Name) and func.id == "APIRouter":
                    is_apirouter = True
                elif isinstance(func, ast.Attribute) and func.attr == "APIRouter":
                    is_apirouter = True

                if is_apirouter:
                    # Extract the variable name(s)
                    var_names = []
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            var_names.append(target.id)

                    # Extract prefix from keyword arguments
                    prefix = ""
                    for keyword in node.value.keywords:
                        if keyword.arg == "prefix":
                            if isinstance(keyword.value, ast.Constant):
                                prefix = keyword.value.value
                                break

                    # Map variable names to prefix
                    for var_name in var_names:
                        prefixes[var_name] = prefix

    return prefixes


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

    # Extract router prefixes from this file
    router_prefixes = _extract_router_prefixes(tree)

    endpoints = []

    # Walk the AST tree looking for function definitions
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            endpoint = _extract_endpoint_from_function(node, file_path, router_prefixes)
            if endpoint:
                endpoints.append(endpoint)

    return endpoints


def _extract_endpoint_from_function(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    file_path: str,
    router_prefixes: dict[str, str] | None = None,
) -> Optional[Endpoint]:
    """Extract endpoint information from a function definition node.

    Args:
        func_node: AST node representing a function definition
        file_path: Path to the file containing this function
        router_prefixes: Dict mapping router variable names to their prefixes

    Returns:
        Endpoint object if this is a FastAPI endpoint, None otherwise
    """
    if router_prefixes is None:
        router_prefixes = {}

    # Check if function has FastAPI decorators
    for decorator in func_node.decorator_list:
        endpoint_info = _parse_fastapi_decorator(decorator)
        if endpoint_info:
            method, path, response_model, is_deprecated, router_name, decorator_desc, decorator_summary, tags = endpoint_info

            # Combine router prefix with endpoint path
            prefix = router_prefixes.get(router_name, "")
            if prefix:
                # Ensure proper path joining (avoid double slashes)
                if path.startswith("/"):
                    path = prefix + path
                else:
                    path = prefix + "/" + path

            # Extract docstring from function
            func_docstring = ast.get_docstring(func_node)

            # Combine decorator description/summary with function docstring
            # Priority: decorator description > decorator summary > function docstring
            if decorator_desc:
                docstring = decorator_desc
            elif decorator_summary:
                docstring = decorator_summary
            elif func_docstring:
                docstring = func_docstring
            else:
                docstring = None

            has_docstring = docstring is not None

            # Extract parameters
            parameters = _extract_parameters(func_node, path)

            # Determine if function is async
            is_async = isinstance(func_node, ast.AsyncFunctionDef)

            # Generate semantic signature
            semantic_signature = _generate_semantic_signature(
                method, path, docstring, parameters, response_model, func_node
            )

            # Extract entity references from code analysis
            entity_refs = set()
            entity_refs.update(_extract_entities_from_body(func_node))
            entity_refs.update(_extract_entities_from_types(func_node, response_model))

            # v3: Extract constraints from decorators and dependencies
            constraints = _extract_constraints(func_node)

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
                semantic_signature=semantic_signature,
                entity_references=sorted(entity_refs),
                constraints=constraints,
            )

    return None


def _parse_fastapi_decorator(decorator: ast.expr) -> Optional[tuple]:
    """Parse a decorator to check if it's a FastAPI route decorator.

    Supports patterns:
    - @app.get(path)
    - @router.post(path)
    - @items_router.put(path, response_model=Model, deprecated=True)
    - @router.get(path, description="...", summary="...", tags=["..."])

    Args:
        decorator: AST decorator node

    Returns:
        Tuple of (method, path, response_model, is_deprecated, router_name, description, summary, tags)
        if FastAPI decorator, None otherwise.
        router_name is the variable name (e.g., "router", "app", "items_router")
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

    # Get the base object name (e.g., 'app', 'router', 'items_router')
    if isinstance(decorator.func.value, ast.Name):
        base_name = decorator.func.value.id
        # Accept any variable name that could be a router/app
        # Common patterns: app, router, api_router, users_router, etc.
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
    description = None
    summary = None
    tags = []

    for keyword in decorator.keywords:
        if keyword.arg == "response_model":
            if isinstance(keyword.value, ast.Name):
                response_model = keyword.value.id
        elif keyword.arg == "deprecated":
            if isinstance(keyword.value, ast.Constant):
                is_deprecated = bool(keyword.value.value)
        elif keyword.arg == "description":
            if isinstance(keyword.value, ast.Constant):
                description = str(keyword.value.value)
        elif keyword.arg == "summary":
            if isinstance(keyword.value, ast.Constant):
                summary = str(keyword.value.value)
        elif keyword.arg == "tags":
            if isinstance(keyword.value, ast.List):
                for elt in keyword.value.elts:
                    if isinstance(elt, ast.Constant):
                        tags.append(str(elt.value))

    return (method, path, response_model, is_deprecated, base_name, description, summary, tags)


def _extract_constraints(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict]:
    """Extract constraint information from decorators and dependencies.

    Detects:
    - Rate limits: @limiter.limit("100/hour"), @ratelimit.limits(...)
    - Auth: @requires_auth, @authenticated, @login_required
    - Dependencies: Depends(get_current_user), Depends(require_admin)
    - Router dependencies: @router.get("/", dependencies=[Depends(...)])
    - Permissions: @permission_required(...), @role_required(...)

    Args:
        func_node: AST function definition node

    Returns:
        List of constraint dictionaries with 'type' and 'value' keys
    """
    constraints = []

    for decorator in func_node.decorator_list:
        # Pattern 1: @limiter.limit("X/timeunit") or @ratelimit.limits(...)
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                if decorator.func.attr in ("limit", "limits"):
                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                        constraints.append({
                            "type": "rate_limit",
                            "value": decorator.args[0].value,
                        })

            # Pattern 3: @permission_required("admin") or @role_required(...)
            if isinstance(decorator.func, ast.Name):
                if decorator.func.id in ("permission_required", "role_required"):
                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                        constraints.append({
                            "type": "permission",
                            "value": decorator.args[0].value,
                        })

            # Pattern 5 (NEW): @router.get("/", dependencies=[Depends(...)])
            # Check decorator keyword arguments for "dependencies"
            for keyword in decorator.keywords:
                if keyword.arg == "dependencies" and isinstance(keyword.value, ast.List):
                    for dep_call in keyword.value.elts:
                        if isinstance(dep_call, ast.Call):
                            if isinstance(dep_call.func, ast.Name) and dep_call.func.id == "Depends":
                                # Extract dependency name
                                if dep_call.args and isinstance(dep_call.args[0], ast.Name):
                                    dep_name = dep_call.args[0].id
                                    # Check if it's an auth-related dependency
                                    if any(kw in dep_name.lower() for kw in ['user', 'auth', 'admin', 'superuser']):
                                        constraints.append({
                                            "type": "auth_required",
                                            "value": dep_name,
                                        })

        # Pattern 2: @requires_auth, @authenticated, etc. (simple decorators)
        if isinstance(decorator, ast.Name):
            auth_decorators = {
                "requires_auth", "authenticated", "login_required",
                "require_auth", "auth_required"
            }
            if decorator.id in auth_decorators:
                constraints.append({
                    "type": "auth_required",
                    "value": True,
                })

    # Pattern 4: Depends(get_current_user) in function parameters
    # Look for Annotated[Type, Depends(...)] pattern
    for arg in func_node.args.args:
        if arg.annotation:
            # Check for Depends() in type annotation
            if isinstance(arg.annotation, ast.Subscript):
                # Could be Annotated[X, Depends(...)]
                if isinstance(arg.annotation.value, ast.Name):
                    if arg.annotation.value.id == "Annotated":
                        # Check the slice (second part of Annotated)
                        if isinstance(arg.annotation.slice, ast.Tuple):
                            for elt in arg.annotation.slice.elts[1:]:  # Skip first element (type)
                                if isinstance(elt, ast.Call):
                                    if isinstance(elt.func, ast.Name):
                                        if elt.func.id == "Depends":
                                            # Extract dependency name
                                            if elt.args and isinstance(elt.args[0], ast.Name):
                                                dep_name = elt.args[0].id
                                                # Common auth dependency patterns
                                                if any(kw in dep_name.lower() for kw in ['user', 'auth', 'admin']):
                                                    constraints.append({
                                                        "type": "auth_required",
                                                        "value": dep_name,
                                                    })

    return constraints


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
        # Skip common non-source directories and example/doc code.
        # Only consider path parts BELOW the scan root, so a project that
        # happens to live under e.g. .../tests/... is still scanned.
        parts = py_file.relative_to(directory).parts
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

def _generate_semantic_signature(
    method: str,
    path: str,
    docstring: Optional[str],
    parameters: List[Parameter],
    response_model: Optional[str],
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:
    """Generate a natural language signature for the endpoint.
    
    Combines method, path, docstring, and parameters into a descriptive string.
    Format: "{docstring}. Method: {method} {path}. Parameters: {params}."
    """
    signature = ""
    
    # Prioritize docstring as it contains the semantic intent
    if docstring:
        # Clean up docstring (remove newlines, extra spaces)
        clean_doc = " ".join(docstring.split())
        signature += f"{clean_doc}"
    else:
        signature += "Undocumented endpoint"
        
    # Add technical details
    signature += f". Method: {method} {path}"
        
    # Add parameter info (simplified)
    if parameters:
        param_names = [p.name for p in parameters]
        signature += f". Parameters: {', '.join(param_names)}"
        
    return signature
