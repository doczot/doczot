"""FastAPI endpoint scanner using AST parsing.

This module scans Python source code to detect FastAPI endpoints.
Based on docs/features/endpoint-detection.md specification.

Uses Python's built-in ast module for parsing - no external dependencies.
"""

import ast
import os
import re
from pathlib import Path
from typing import List, NamedTuple, Optional, Set

from doczot_analyzer.models import Endpoint, Parameter


# Common entity patterns to detect in code
ENTITY_PATTERN = re.compile(r'^([A-Z][a-z]+)+$')  # PascalCase like User, UserCreate


# Words that look plural but are already singular. Stripping their ending
# produces nonsense nouns ("status" -> "statu") that then fail to match the
# same entity named correctly elsewhere.
_INVARIANT_PLURALS = frozenset({
    'series', 'species', 'news', 'data', 'media', 'metadata',
    'status', 'address', 'access', 'progress', 'analysis', 'basis',
})

# A trailing "es" is a two-letter plural suffix only after a stem that could
# not take a bare "s": sibilants and affricates (boxes -> box, batches ->
# batch), double-s (addresses -> address), and the -oes pattern (heroes ->
# hero). Everywhere else the stem simply ends in "e" and only the "s" is the
# plural marker (invoices -> invoice, not "invoic").
_SIBILANT_ES_STEMS = ('x', 'z', 'ch', 'sh', 'ss', 'o')

# Singular nouns ending in "-us". Needed to disambiguate "-uses" plurals:
# "buses" -> "bus" but "warehouses" -> "warehouse", and both leave a stem
# ending in "s" after dropping "es".
_US_SINGULARS = frozenset({
    'bus', 'status', 'virus', 'campus', 'focus', 'bonus', 'census',
    'corpus', 'genus', 'nexus', 'radius', 'surplus', 'plus', 'minus',
    'alias', 'bias', 'gas', 'atlas', 'canvas', 'lens',
})


def _singularize(name: str) -> str:
    """Convert a name to singular lowercase form.

    Handles the English plural patterns that appear in API path segments and
    type names. Deliberately conservative: when a word's plurality is
    ambiguous it is left alone, because inventing a stem that matches nothing
    is worse than leaving a plural in place.
    """
    name = name.lower()

    if name in _INVARIANT_PLURALS:
        return name

    # Latin/Greek singulars ending in -us or -is (status, campus, analysis).
    if name.endswith(('us', 'is')):
        return name

    if name.endswith('ies'):
        # categories -> category, but ties -> tie and pies -> pie, where the
        # "ie" belongs to the stem rather than marking a consonant + y plural.
        if len(name) > 4:
            return name[:-3] + 'y'
        return name[:-1]

    if name.endswith('es') and len(name) > 3:
        stem = name[:-2]
        if stem.endswith(_SIBILANT_ES_STEMS) or stem in _US_SINGULARS:
            return stem
        # invoices -> invoice, warehouses -> warehouse, venues -> venue
        return name[:-1]

    if name.endswith('s') and not name.endswith('ss'):
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


# Directories excluded from the router pre-pass. Kept in step with the skip
# set in scan_directory so both passes agree on which files exist.
_ROUTER_SCAN_SKIP_DIRS = {
    "__pycache__", ".venv", "venv", ".git", "node_modules",
    "tests", "test", "docs_src", "examples", "example",
}


def _module_name_for(relative_path: Path) -> str:
    """Dotted module name for a source file, relative to the scan root.

    ``app/api/routes/invoices.py`` -> ``app.api.routes.invoices``, and
    ``app/api/__init__.py`` -> ``app.api`` so package-level imports resolve to
    the same key as the file that defines them.
    """
    parts = list(relative_path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


class ImportScope(NamedTuple):
    """What the names visible in one module refer to.

    ``names`` maps a local name to the (module, original name) it was imported
    under. Keeping the *original* name matters: ``from src.modules.user.routes
    import router as users_router`` makes ``users_router`` locally, but the
    router is declared as ``router`` in that module, so looking it up under the
    alias finds nothing.

    ``modules`` maps a local name that refers to a module rather than a value,
    which is what ``invoices.router`` needs.
    """

    names: dict[str, tuple[str, str]]
    modules: dict[str, str]


def _collect_import_aliases(tree: ast.Module, module_name: str) -> ImportScope:
    """Map local names to the modules and original names they came from.

    Handles the shapes that matter for router resolution:

    - ``from app.api.main import api_router`` -> ``api_router`` is ``api_router``
      in ``app.api.main``
    - ``from x.routes import router as users_router`` -> ``users_router`` is
      ``router`` in ``x.routes``
    - ``from app.api.routes import invoices`` -> ``invoices`` may itself be the
      module ``app.api.routes.invoices``

    Relative imports resolve against the importing module's own package.
    """
    names: dict[str, tuple[str, str]] = {}
    modules: dict[str, str] = {}
    package = module_name.rsplit(".", 1)[0] if "." in module_name else ""

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                # Relative import: climb the importing module's package chain.
                pkg_parts = package.split(".") if package else []
                climb = node.level - 1
                if climb:
                    pkg_parts = pkg_parts[:-climb] if climb <= len(pkg_parts) else []
                base = ".".join(filter(None, [".".join(pkg_parts), base]))
            for alias in node.names:
                local = alias.asname or alias.name
                names[local] = (base, alias.name)
                # The imported name may itself be a submodule.
                modules[local] = f"{base}.{alias.name}" if base else alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                modules[local] = alias.name

    return ImportScope(names=names, modules=modules)


def _collect_string_constants(tree: ast.Module) -> dict[str, str]:
    """Collect string constants declared anywhere in a module.

    Real projects rarely inline the API prefix. FastAPI's own
    full-stack-fastapi-template writes
    ``app.include_router(api_router, prefix=settings.API_V1_STR)`` against a
    Pydantic settings class holding ``API_V1_STR: str = "/api/v1"``. Accepting
    only literals meant the canonical layout silently lost its prefix and every
    reported path named a URL the service does not serve.

    Keyed by bare name, which is what both ``settings.API_V1_STR`` and a
    module-level ``API_PREFIX`` need. Collisions across modules are possible but
    harmless here: these are near-always uppercase configuration constants, and
    an unresolved prefix degrades to the previous behaviour rather than to a
    wrong one.
    """
    constants: dict[str, str] = {}

    for node in ast.walk(tree):
        target = None
        value = None

        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target, value = node.target.id, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            if isinstance(node.targets[0], ast.Name):
                target, value = node.targets[0].id, node.value

        if target is None or value is None:
            continue
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            constants.setdefault(target, value.value)

    return constants


def _resolve_prefix_value(
    node: Optional[ast.expr], constants: dict[str, str]
) -> str:
    """Resolve a prefix keyword argument to a string.

    Accepts a literal, a bare constant name, an attribute access such as
    ``settings.API_V1_STR``, and simple concatenation of those. Returns "" when
    the value cannot be determined statically, which leaves the path unprefixed
    exactly as before rather than guessing.
    """
    if node is None:
        return ""

    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else ""

    if isinstance(node, ast.Name):
        return constants.get(node.id, "")

    if isinstance(node, ast.Attribute):
        # settings.API_V1_STR / config.settings.API_V1_STR
        return constants.get(node.attr, "")

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return (
            _resolve_prefix_value(node.left, constants)
            + _resolve_prefix_value(node.right, constants)
        )

    if isinstance(node, ast.JoinedStr):
        # f"{settings.API_V1_STR}/extra"
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                parts.append(_resolve_prefix_value(value.value, constants))
            else:
                return ""
        return "".join(parts)

    return ""


def _resolve_router_ref(
    arg: ast.expr, module_name: str, scope: ImportScope
) -> Optional[tuple[str, str]]:
    """Resolve the first argument of an include_router call to (module, var).

    ``include_router(api_router)`` resolves through the import that brought
    ``api_router`` into scope, under the name it was *declared* with rather than
    the local alias; ``include_router(invoices.router)`` resolves ``invoices``
    to a module and takes ``router`` as the variable. Returns None for shapes we
    cannot resolve statically.
    """
    if isinstance(arg, ast.Name):
        imported = scope.names.get(arg.id)
        if imported is not None:
            owner_module, original_name = imported
            return (owner_module or module_name, original_name)
        # A router defined in this same file has no import entry.
        return (module_name, arg.id)

    if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name):
        holder = arg.value.id
        holder_module = scope.modules.get(holder)
        if holder_module:
            return (holder_module, arg.attr)
        return (f"{module_name}.{holder}", arg.attr)

    return None


def _extract_include_router_calls(
    tree: ast.Module,
    module_name: str,
    scope: ImportScope,
    constants: dict[str, str],
) -> list[tuple[str, tuple[str, str]]]:
    """Find include_router calls and the prefix each one contributes.

    Returns a list of (prefix, (child_module, child_var)) pairs. The prefix is
    the one supplied at include time, which is *additional* to any prefix the
    child router declared for itself.
    """
    includes = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "include_router"):
            continue
        if not node.args:
            continue

        child = _resolve_router_ref(node.args[0], module_name, scope)
        if child is None:
            continue

        prefix = ""
        for keyword in node.keywords:
            if keyword.arg == "prefix":
                prefix = _resolve_prefix_value(keyword.value, constants)
                break

        includes.append((prefix, child))

    return includes


def build_router_prefix_map(directory_path: str) -> dict[tuple[str, str], str]:
    """Resolve the effective URL prefix of every router in a project.

    A router's real prefix is the concatenation of the prefixes contributed by
    every ``include_router`` call between it and the FastAPI app, plus whatever
    it declared in its own ``APIRouter(prefix=...)``. Those pieces routinely
    live in different files:

        app/main.py           app.include_router(api_router, prefix="/api/v1")
        app/api/main.py       api_router.include_router(invoices.router)
        app/api/routes/...    router = APIRouter(prefix="/invoices")

    Reading one file at a time can only ever see the last line, so paths came
    out as ``/invoices/`` for a service that actually serves
    ``/api/v1/invoices/``. Reporting URLs the application does not serve makes
    the coverage report wrong twice: the endpoint is misnamed, and the docs
    describing the real URL no longer match it.

    Returns a mapping of (module_name, router_variable) to the prefix
    contributed by include chains — excluding the router's own declared prefix,
    which ``scan_python_file`` already applies.
    """
    directory = Path(directory_path)
    if not directory.is_dir():
        return {}

    # (module, var) -> prefix declared on its own APIRouter(...) call
    own_prefix: dict[tuple[str, str], str] = {}
    # parent (module, var) -> [(include prefix, child (module, var))]
    include_graph: dict[tuple[str, str], list[tuple[str, tuple[str, str]]]] = {}
    # Routers included by a FastAPI app rather than another router.
    app_includes: list[tuple[str, tuple[str, str]]] = []
    app_vars: set[tuple[str, str]] = set()

    # Pass 1: parse every file once, recording router declarations, app objects
    # and string constants. Constants must be known project-wide before includes
    # are read, because a prefix is routinely a settings attribute defined in a
    # different file than the include_router call that uses it.
    parsed: list[tuple[str, ast.Module]] = []
    constants: dict[str, str] = {}

    for py_file in directory.rglob("*.py"):
        try:
            relative = py_file.relative_to(directory)
        except ValueError:
            continue
        if any(part in _ROUTER_SCAN_SKIP_DIRS for part in relative.parts):
            continue

        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue

        module_name = _module_name_for(relative)
        parsed.append((module_name, tree))

        for var, prefix in _extract_router_prefixes(tree).items():
            own_prefix[(module_name, var)] = prefix

        for name, value in _collect_string_constants(tree).items():
            constants.setdefault(name, value)

        # Identify FastAPI() app objects so their includes seed the walk. The
        # assignment may sit inside an application-factory function, so this
        # walks the whole tree rather than module level only.
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                func = node.value.func
                is_app = (
                    (isinstance(func, ast.Name) and func.id == "FastAPI")
                    or (isinstance(func, ast.Attribute) and func.attr == "FastAPI")
                )
                if is_app:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            app_vars.add((module_name, target.id))

    # Pass 2: read the include graph, now able to resolve non-literal prefixes.
    for module_name, tree in parsed:
        scope = _collect_import_aliases(tree, module_name)

        for prefix, child in _extract_include_router_calls(
            tree, module_name, scope, constants
        ):
            parent = _include_parent(tree, module_name, scope, child)
            if parent is not None and parent in app_vars:
                app_includes.append((prefix, child))
            elif parent is not None:
                include_graph.setdefault(parent, []).append((prefix, child))
            else:
                app_includes.append((prefix, child))

    # Walk downward from each app include, accumulating prefixes. Visited set
    # guards against a router graph with a cycle.
    effective: dict[tuple[str, str], str] = {}

    def walk(router: tuple[str, str], inherited: str, seen: frozenset) -> None:
        if router in seen:
            return
        effective[router] = inherited
        own = own_prefix.get(router, "")
        base = inherited + own
        for prefix, child in include_graph.get(router, []):
            walk(child, base + prefix, seen | {router})

    for prefix, child in app_includes:
        walk(child, prefix, frozenset())

    return effective


def _include_parent(
    tree: ast.Module,
    module_name: str,
    scope: ImportScope,
    child: tuple[str, str],
) -> Optional[tuple[str, str]]:
    """Find which object called include_router for a given child router."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "include_router"):
            continue
        if not node.args:
            continue
        if _resolve_router_ref(node.args[0], module_name, scope) != child:
            continue
        if isinstance(func.value, ast.Name):
            return (module_name, func.value.id)
    return None


def scan_python_file(
    source_code: str,
    file_path: str,
    inherited_prefixes: Optional[dict[str, str]] = None,
) -> List[Endpoint]:
    """Scan Python source code for FastAPI endpoints using AST parsing.

    Args:
        source_code: Python source code as string
        file_path: Path to the file (for reference in results)
        inherited_prefixes: Router variable name -> prefix contributed by
            include_router calls elsewhere in the project. Supplied by
            scan_directory via build_router_prefix_map(); when omitted, only
            prefixes declared in this file are applied.

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

    # Extract router prefixes from this file, then prepend whatever the include
    # chain contributes so the reported path is the URL actually served.
    router_prefixes = _extract_router_prefixes(tree)
    if inherited_prefixes:
        for var, inherited in inherited_prefixes.items():
            router_prefixes[var] = inherited + router_prefixes.get(var, "")

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
                if not path:
                    # @router.get("") on a prefixed router is served at the
                    # prefix itself, with no trailing slash. Appending one here
                    # reports a URL the app does not serve, and the wrong path
                    # then fails to match its documentation.
                    path = prefix
                elif path.startswith("/"):
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


def scan_directory(directory_path: str, stats: Optional[dict] = None) -> List[Endpoint]:
    """Scan all Python files in a directory for FastAPI endpoints.

    Recursively scans the directory for .py files and extracts endpoints.

    Args:
        directory_path: Path to the directory to scan
        stats: Optional dict populated with scan diagnostics:
            files_seen, files_scanned, files_with_endpoints,
            skipped_by_dir_filter, skipped_test_files, parse_errors

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

    if stats is None:
        stats = {}
    stats.update({
        "files_seen": 0,
        "files_scanned": 0,
        "files_with_endpoints": 0,
        "skipped_by_dir_filter": 0,
        "skipped_test_files": 0,
        "parse_errors": 0,
    })

    all_endpoints = []

    # Resolve include_router chains across the whole project first, so each
    # file can be given the prefix its routers actually inherit.
    prefix_map = build_router_prefix_map(str(directory))

    # Recursively find all .py files
    for py_file in directory.rglob("*.py"):
        stats["files_seen"] += 1

        # Skip common non-source directories and example/doc code.
        # Only consider path parts BELOW the scan root, so a project that
        # happens to live under e.g. .../tests/... is still scanned.
        parts = py_file.relative_to(directory).parts
        skip_dirs = _ROUTER_SCAN_SKIP_DIRS
        if any(skip_dir in parts for skip_dir in skip_dirs):
            stats["skipped_by_dir_filter"] += 1
            continue

        # Skip test files (test_*.py, *_test.py)
        if py_file.name.startswith("test_") or py_file.name.endswith("_test.py"):
            stats["skipped_test_files"] += 1
            continue

        try:
            source_code = py_file.read_text(encoding="utf-8")
            # Use relative path from the scan directory
            relative_path = py_file.relative_to(directory)
            module_name = _module_name_for(relative_path)
            inherited = {
                var: prefix
                for (mod, var), prefix in prefix_map.items()
                if mod == module_name
            }
            endpoints = scan_python_file(
                source_code, str(relative_path), inherited_prefixes=inherited
            )
            stats["files_scanned"] += 1
            if endpoints:
                stats["files_with_endpoints"] += 1
            all_endpoints.extend(endpoints)
        except (SyntaxError, UnicodeDecodeError):
            # Skip files with syntax errors or encoding issues
            stats["parse_errors"] += 1
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
