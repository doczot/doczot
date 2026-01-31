"""DocZot v2 Analyzer - Build System Graph, Coverage Checklist, and Content Inventory.

This module provides functions to:
1. Build a SystemGraph from code scanning (endpoints, entities, constraints)
2. Generate a Coverage Checklist from the system graph (what should be documented)
3. Discover Content Inventory from existing documentation (what is documented)
4. Compute Drift Reports (documentation drift detection)

Terminology:
    SystemGraph = Code structure graph (formerly SurfaceGraph, KnowledgeGraph)
    Coverage Checklist = ITM (Intended Topic Manifest) - the plan
    Content Inventory = ATM (Actual Topic Manifest) - the reality
    Drift Report = Gap Report - divergence between code and docs
"""
from pathlib import Path
from typing import Optional
import re

from doczot_analyzer.scanner import scan_directory
from doczot_analyzer.docs_parser import (
    scan_documentation,
    parse_markdown_chunks,
    find_markdown_files,
)
from doczot_analyzer.vector_store import LocalVectorStore
from doczot_analyzer.scanner_nodejs import scan_nodejs_directory  # v3
from doczot_analyzer.models_v2 import (
    # New terminology
    SystemGraph,
    SystemNode,
    SystemEdge,
    DriftReport,
    DriftItem,
    compute_drift_report,
    # Backward compatibility aliases
    SurfaceGraph,
    SurfaceNode,
    SurfaceEdge,
    GapReport,
    compute_gap_report,
    # Shared types
    NodeType,
    NodeClass,
    EdgeType,
    TopicManifest,
    Topic,
    TopicType,
    TopicQuality,
    ManifestType,
    ConfidenceLevel,
    generate_default_itm,
)


# =============================================================================
# ACTION WORDS (for filtering)
# =============================================================================

ACTION_WORDS = {
    # Auth actions
    'login', 'logout', 'signin', 'signout', 'signup', 'register',
    'authenticate', 'authorize', 'auth', 'oauth', 'callback',
    # Password actions
    'forgot-password', 'reset-password', 'change-password', 'recover',
    'password', 'forgot', 'reset', 'recover-password',
    # Verification actions
    'verify', 'confirm', 'validate', 'activate', 'request-verify-token',
    'request-verify', 'verify-email', 'verify-token',
    # Common API actions
    'search', 'filter', 'export', 'import', 'download', 'upload',
    'refresh', 'revoke', 'sync', 'batch', 'bulk',
    # Meta endpoints
    'health', 'healthz', 'ready', 'readyz', 'live', 'livez',
    'metrics', 'status', 'ping', 'version', 'info',
    'docs', 'openapi', 'swagger', 'redoc', 'schema',
    # Other
    'me', 'self', 'current', 'api', 'v1', 'v2', 'v3',
}

HTTP_METHOD_TO_VERB = {
    "GET": "get",
    "POST": "create",
    "PUT": "update",
    "PATCH": "patch",
    "DELETE": "delete",
}


# =============================================================================
# SURFACE GRAPH BUILDING
# =============================================================================

def detect_repo_type(repo_path: str) -> str:
    """Detect if repository is Python/FastAPI or Node.js/CLI.

    Args:
        repo_path: Path to the repository

    Returns:
        'nodejs', 'python', or 'unknown'
    """
    repo_path_obj = Path(repo_path)

    # Check for package.json (Node.js)
    if (repo_path_obj / "package.json").exists():
        return "nodejs"

    # Check for Python files
    py_files = list(repo_path_obj.rglob("*.py"))
    if py_files:
        return "python"

    return "unknown"


def build_system_graph_nodejs(
    repo_path: str,
    product_name: Optional[str] = None,
) -> SystemGraph:
    """Build a System Graph from a Node.js CLI repository.

    Creates:
    - Verb nodes for CLI commands
    - Noun nodes for CLI flags/options
    - Edges connecting commands to their flags

    Args:
        repo_path: Path to the repository
        product_name: Optional product name

    Returns:
        SurfaceGraph with CLI commands as verb nodes and flags as noun nodes
    """
    repo_path = str(Path(repo_path).resolve())
    if not product_name:
        product_name = Path(repo_path).name

    commands = scan_nodejs_directory(repo_path)

    nodes: list[SystemNode] = []
    edges: list[SystemEdge] = []
    seen_flags: set[str] = set()

    # Create verb nodes for each command and noun nodes for flags
    for cmd in commands:
        verb_node = SystemNode(
            id=f"verb:CLI:{cmd.name}",
            type=NodeType.VERB,
            name=cmd.name,
            description=cmd.description,
            source_file=cmd.file_path,
            source_line=cmd.line_number if cmd.line_number else 1,
            code_signature=cmd.name,  # Use clean name, not "CLI {name}"
        )
        nodes.append(verb_node)

        # Create noun nodes for each flag/option
        for flag in cmd.flags:
            flag_name = flag.get('name', '')
            if not flag_name or flag_name in seen_flags:
                continue

            seen_flags.add(flag_name)

            flag_node = SystemNode(
                id=f"noun:flag:{flag_name}",
                type=NodeType.NOUN,
                name=flag_name,
                description=flag.get('description', f'CLI flag: {flag_name}'),
                source_file=cmd.file_path,
                source_line=1,  # Default to line 1 for flags
            )
            nodes.append(flag_node)

            # Create edge: command operates_on flag
            edge = SystemEdge(
                source_id=verb_node.id,
                target_id=flag_node.id,
                edge_type=EdgeType.OPERATES_ON,
                confidence=ConfidenceLevel.HIGH,
            )
            edges.append(edge)

    # Deduplicate nodes and edges by their IDs
    unique_nodes = _deduplicate_nodes(nodes)
    unique_edges = _deduplicate_edges(edges)

    return SystemGraph(
        product_name=product_name,
        source_paths=[repo_path],
        nodes=unique_nodes,
        edges=unique_edges,
    )


def build_system_graph_python(
    repo_path: str,
    product_name: Optional[str] = None,
) -> SystemGraph:
    """Build a System Graph from a Python/FastAPI repository.

    Scans code for endpoints and extracts:
    - Verb nodes (API endpoints)
    - Noun nodes (entities from paths)
    - Constraint nodes (rate limits, auth requirements)
    - Concept nodes (from docstrings and README)
    - Edges (operates_on, part_of, prerequisite, constrained_by)
    """
    repo_path = str(Path(repo_path).resolve())
    if not product_name:
        product_name = Path(repo_path).name

    # Scan code for endpoints
    endpoints = scan_directory(repo_path)

    nodes: list[SystemNode] = []
    edges: list[SystemEdge] = []
    seen_nouns: set[str] = set()

    for ep in endpoints:
        # Create verb node
        base_verb = HTTP_METHOD_TO_VERB.get(ep.method, ep.method.lower())
        path_segments = [s for s in ep.path.split('/') if s and not s.startswith('{')]
        resource = path_segments[-1] if path_segments else "resource"
        verb_name = f"{base_verb}_{resource}"

        verb_node = SystemNode(
            id=f"verb:{ep.method}:{ep.path}",
            type=NodeType.VERB,
            name=verb_name,
            description=ep.docstring,  # Use docstring/decorator description
            source_file=ep.file_path,
            source_line=ep.line_number,
            code_signature=f"{ep.method} {ep.path}",
            http_method=ep.method,
            http_path=ep.path,
        )
        nodes.append(verb_node)

        # Extract nouns from path AND from code analysis
        path_nouns = extract_nouns_from_path(ep.path)

        # Filter code nouns: skip plurals, compound types, infrastructure, and generic words
        skip_code_nouns = {
            # Plurals (should use singular)
            'items', 'users', 'posts', 'tasks', 'jobs', 'files', 'tiers', 'keys',
            # Generic words that are NOT entities
            'all', 'single', 'one', 'many', 'multi', 'new', 'old', 'my', 'self',
            'first', 'last', 'current', 'next', 'prev', 'previous',
            # Infrastructure / constraints (not entities)
            'access', 'token', 'session', 'cookie', 'context', 'settings',
            'config', 'cache', 'rate', 'limit', 'ratelimit', 'rate_limit',
            'ready', 'readycheck', 'health', 'healthcheck', 'status', 'check',
            'root', 'home', 'index', 'base', 'main', 'app', 'tier', 'usertier',
            # Auth/security (not entities)
            'secret', 'key', 'apikey', 'password', 'hash', 'salt', 'credential',
            # URL/path components (not entities)
            'slug', 'id', 'uuid', 'url', 'path', 'route',
        }

        def is_valid_noun(noun: str) -> bool:
            """Check if a noun candidate is a valid domain entity."""
            n = noun.lower()

            # Skip if in explicit skip list
            if n in skip_code_nouns:
                return False

            # Skip database model prefixes (db_user, dbuser, DB_User)
            if n.startswith('db_') or n.startswith('db'):
                # But allow "database" as a word
                if n not in ('database', 'db'):
                    return False

            # Skip DTO suffixes that slipped through
            dto_patterns = ['create', 'update', 'read', 'write', 'base', 'public',
                           'private', 'login', 'edit', 'register', 'schema', 'model',
                           # Pydantic input/output patterns (from variable names like tags_in)
                           'in', 'out', 'input', 'output', 'response', 'request']
            for pattern in dto_patterns:
                if n.endswith(pattern) and len(n) > len(pattern):
                    return False

            # Skip compound patterns like "listofarticlesin", "usersinlist"
            if 'listof' in n or 'list' in n:
                return False

            # Skip compound patterns with 'in' in the middle (userinlog, articleindb)
            if 'inlog' in n or 'indb' in n or 'inlist' in n:
                return False

            # Skip names that look truncated (end in consonant cluster unlikely for entities)
            # e.g., "articl" instead of "article"
            if len(n) >= 4 and n[-1] not in 'aeiouy' and n[-2] not in 'aeiouy':
                # But allow common patterns like "post", "task"
                if n not in {'post', 'task', 'user', 'item', 'job', 'blog', 'tag', 'key'}:
                    # Check if this looks like a truncated version of a known word
                    # If articl + e = article, then articl is truncated -> skip it
                    known_words = {'article', 'profile', 'comment', 'project', 'product',
                                  'secret', 'select', 'content', 'document', 'element'}
                    if any(n + suffix in known_words for suffix in ['e', 'le', 'ent', 'ect', 'uct', 'et']):
                        return False
                    # Also skip if it's too short to be meaningful after consonant cluster
                    if len(n) < 4:
                        return False

            # Skip "my" prefix patterns (MyUser -> skip)
            if n.startswith('my') and len(n) > 2:
                return False

            return True

        code_nouns = [n for n in ep.entity_references if is_valid_noun(n)]

        # Combine and dedupe, preferring singularized forms
        all_nouns = set(path_nouns)
        for noun in code_nouns:
            # Singularize if needed
            singular = noun
            if singular.endswith('s') and not singular.endswith('ss'):
                singular = singular[:-1]
            # Skip compound names (more than one word run together)
            if len(singular) <= 10:  # Simple entity names are short
                all_nouns.add(singular)

        for noun in all_nouns:
            noun_id = f"noun:{noun}"

            if noun not in seen_nouns:
                seen_nouns.add(noun)
                noun_node = SystemNode(
                    id=noun_id,
                    type=NodeType.NOUN,
                    name=noun,
                )
                nodes.append(noun_node)

            # Create edge: verb operates_on noun
            edge = SystemEdge(
                source_id=verb_node.id,
                target_id=noun_id,
                edge_type=EdgeType.OPERATES_ON,
            )
            edges.append(edge)

    # v3: Create constraint nodes for each endpoint
    for ep in endpoints:
        verb_id = f"verb:{ep.method}:{ep.path}"

        for constraint in ep.constraints:
            constraint_id = f"constraint:{constraint['type']}:{verb_id}"

            # Generate description based on constraint type
            if constraint['type'] == 'rate_limit':
                description = f"Rate limited to {constraint['value']}"
            elif constraint['type'] == 'auth_required':
                if isinstance(constraint['value'], str):
                    description = f"Authentication required: {constraint['value']}"
                else:
                    description = "Authentication required"
            elif constraint['type'] == 'permission':
                description = f"Requires {constraint['value']} permission"
            else:
                description = str(constraint.get('value', ''))

            constraint_node = SystemNode(
                id=constraint_id,
                type=NodeType.CONSTRAINT,
                name=constraint['type'],
                description=description,
                source_file=ep.file_path,
                source_line=ep.line_number,
            )
            nodes.append(constraint_node)

            # Create constrained_by edge
            edge = SystemEdge(
                source_id=verb_id,
                target_id=constraint_id,
                edge_type=EdgeType.CONSTRAINED_BY,
                confidence=ConfidenceLevel.HIGH,
            )
            edges.append(edge)

    # v3: Detect part_of relationships from nested paths
    all_noun_names = {n.name for n in nodes if n.type == NodeType.NOUN}
    part_of_rels = detect_part_of_relationships(endpoints, all_noun_names)

    for child_name, parent_name in part_of_rels:
        child_id = f"noun:{child_name}"
        parent_id = f"noun:{parent_name}"

        edges.append(SystemEdge(
            source_id=child_id,
            target_id=parent_id,
            edge_type=EdgeType.PART_OF,
            confidence=ConfidenceLevel.HIGH,
        ))

    # v3: Detect prerequisite relationships (auth-protected → auth endpoints)
    prereq_rels = detect_prerequisite_relationships(nodes, edges)

    for source_id, target_id in prereq_rels:
        edges.append(SystemEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=EdgeType.PREREQUISITE,
            confidence=ConfidenceLevel.MEDIUM,
        ))

    # v3: Extract concepts from docstrings and documentation files
    docstring_concepts = extract_concepts_from_docstrings(endpoints)
    doc_concepts = extract_concepts_from_docs(repo_path)

    all_concepts = docstring_concepts + doc_concepts
    seen_concept_names = set()

    for concept_data in all_concepts:
        if concept_data['name'] in seen_concept_names:
            continue
        seen_concept_names.add(concept_data['name'])

        concept_node = SystemNode(
            id=f"concept:{concept_data['name']}",
            type=NodeType.CONCEPT,
            name=concept_data['name'],
            description=concept_data.get('definition'),
            source_file=concept_data.get('source_file'),
            source_line=concept_data.get('source_line'),
        )
        nodes.append(concept_node)

        # Create RELATED_TO edges from concept to nouns it mentions
        if concept_data.get('definition'):
            definition_lower = concept_data['definition'].lower()
            for noun_name in seen_nouns:
                if noun_name in definition_lower:
                    edges.append(SystemEdge(
                        source_id=concept_node.id,
                        target_id=f"noun:{noun_name}",
                        edge_type=EdgeType.RELATED_TO,
                        confidence=ConfidenceLevel.MEDIUM,
                    ))

    # Deduplicate nodes and edges by their IDs
    unique_nodes = _deduplicate_nodes(nodes)
    unique_edges = _deduplicate_edges(edges)

    return SystemGraph(
        product_name=product_name,
        source_paths=[repo_path],
        nodes=unique_nodes,
        edges=unique_edges,
    )


def _deduplicate_nodes(nodes: list[SystemNode]) -> list[SystemNode]:
    """Deduplicate nodes by their ID, keeping the first occurrence."""
    seen = {}
    for node in nodes:
        if node.id not in seen:
            seen[node.id] = node
    return list(seen.values())


def _deduplicate_edges(edges: list[SystemEdge]) -> list[SystemEdge]:
    """Deduplicate edges by (source_id, target_id, edge_type)."""
    seen = set()
    unique = []
    for edge in edges:
        key = (edge.source_id, edge.target_id, edge.edge_type)
        if key not in seen:
            seen.add(key)
            unique.append(edge)
    return unique


def detect_part_of_relationships(
    endpoints: list,
    all_nouns: set[str]
) -> list[tuple[str, str]]:
    """Detect part_of relationships from nested URL paths.

    Example: /users/{user_id}/projects/{project_id}
    Result: (project, user) - projects are part_of users

    Args:
        endpoints: List of endpoint objects
        all_nouns: Set of all noun names in the graph

    Returns:
        List of (child_noun, parent_noun) tuples
    """
    relationships = []
    seen = set()

    for ep in endpoints:
        path = ep.path
        # Strip API version prefixes
        path = re.sub(r'/api/v\d+', '', path)
        path = re.sub(r'/v\d+', '', path)

        segments = [s for s in path.split('/') if s and not s.startswith('{')]

        # Look for nested resource patterns
        for i in range(len(segments) - 1):
            # Check if there's a path param between segments
            path_parts = path.split('/')
            try:
                parent_idx = path_parts.index(segments[i])
                child_idx = path_parts.index(segments[i + 1])

                # If there's a {id} between parent and child
                if child_idx - parent_idx == 2:
                    parent = segments[i].rstrip('s')  # Singularize
                    child = segments[i + 1].rstrip('s')

                    if parent in all_nouns and child in all_nouns:
                        rel = (child, parent)
                        if rel not in seen:
                            relationships.append(rel)
                            seen.add(rel)
            except ValueError:
                # Segment not found in path_parts
                continue

    return relationships


def detect_prerequisite_relationships(
    nodes: list[SystemNode],
    edges: list[SystemEdge]
) -> list[tuple[str, str]]:
    """Detect prerequisite relationships.

    Auth-protected endpoints require login/token endpoints as prerequisites.

    Args:
        nodes: List of all surface nodes
        edges: List of all edges

    Returns:
        List of (source_verb_id, target_verb_id) tuples for prerequisites
    """
    prerequisites = []

    # Find auth endpoints (login, token, signup)
    auth_paths = ['login', 'token', 'access-token', 'signup', 'register']
    auth_verb_ids = [
        n.id for n in nodes
        if n.type == NodeType.VERB and n.http_path and
        any(kw in n.http_path.lower() for kw in auth_paths)
    ]

    if not auth_verb_ids:
        return prerequisites

    # Find constrained_by edges that point to auth constraints
    auth_constraint_ids = {
        e.target_id for e in edges
        if e.edge_type == EdgeType.CONSTRAINED_BY
    }

    auth_constraints = [
        n for n in nodes
        if n.id in auth_constraint_ids and
        n.type == NodeType.CONSTRAINT and
        'auth' in n.name.lower()
    ]

    # Find verbs constrained by auth
    auth_constrained_verbs = set()
    for constraint in auth_constraints:
        for edge in edges:
            if edge.target_id == constraint.id and edge.edge_type == EdgeType.CONSTRAINED_BY:
                auth_constrained_verbs.add(edge.source_id)

    # Create prerequisite: protected_endpoint → login_endpoint
    primary_auth = auth_verb_ids[0]  # Use first auth endpoint found
    for verb_id in auth_constrained_verbs:
        if verb_id not in auth_verb_ids:  # Don't make auth depend on itself
            prerequisites.append((verb_id, primary_auth))

    return prerequisites


def extract_concepts_from_docstrings(endpoints: list) -> list[dict]:
    """Extract concepts from endpoint docstrings using definition patterns.

    Looks for definition sentences in docstrings like:
    - "Authentication is the process of..."
    - "A rate limit refers to..."
    - "The workspace represents..."

    Args:
        endpoints: List of endpoint objects

    Returns:
        List of concept dictionaries with name, definition, source_file, source_line
    """
    concepts = {}  # Use dict to dedupe by name

    # Patterns that indicate a definition sentence
    definition_verbs = r'(?:is|are|refers?\s+to|represents?|describes?|means?|defines?|provides?|handles?|manages?|controls?)'
    definition_pattern = re.compile(
        rf'(?:^|\.)\s*(?:(?:The|A|An)\s+)?([A-Za-z][a-z]+(?:\s+[a-z]+)*)\s+{definition_verbs}\s+(.+?)(?:\.|$)',
        re.MULTILINE
    )

    # Skip terms that are just CRUD actions or infrastructure
    skip_terms = {
        'this', 'the', 'that', 'each', 'every', 'some', 'any',
        'create', 'update', 'delete', 'get', 'list', 'retrieve',
        'check', 'return', 'response', 'request', 'endpoint',
        'function', 'method', 'handler', 'route', 'path',
    }

    for ep in endpoints:
        if not ep.docstring:
            continue

        for match in definition_pattern.finditer(ep.docstring):
            term = match.group(1).strip()
            definition = match.group(2).strip()

            concept_name = term.lower()
            if concept_name in skip_terms:
                continue
            if len(concept_name) < 3:
                continue

            if concept_name not in concepts:
                concepts[concept_name] = {
                    "name": concept_name,
                    "definition": definition[:200],
                    "source_file": ep.file_path,
                    "source_line": ep.line_number,
                }

    return list(concepts.values())


def extract_concepts_from_docs(repo_path: str) -> list[dict]:
    """Extract concepts from all documentation files in the repository.

    Scans markdown files for concept definitions using multiple patterns:
    - H2/H3 headers followed by definition text
    - Bold terms followed by definitions ("**term**: definition")
    - Definition list patterns ("- **term** - definition")

    Args:
        repo_path: Path to the repository

    Returns:
        List of concept dictionaries with name, definition, source_file, source_line
    """
    from doczot_analyzer.docs_parser import find_markdown_files

    concepts = {}  # Dedupe by name
    md_files = find_markdown_files(repo_path)

    # Also check root README if find_markdown_files missed it
    readme_path = Path(repo_path) / "README.md"
    if readme_path.exists() and str(readme_path) not in md_files:
        md_files.append(str(readme_path))

    # Headers to skip (meta sections, not domain concepts)
    skip_headers = {
        'install', 'installation', 'usage', 'license', 'licence',
        'contributing', 'features', 'setup', 'requirements',
        'prerequisites', 'getting started', 'quick start', 'quickstart',
        'table of contents', 'toc', 'changelog', 'changes',
        'development', 'deployment', 'testing', 'tests',
        'configuration', 'environment variables', 'docker',
        'acknowledgements', 'credits', 'about', 'overview',
    }

    for file_path in md_files:
        try:
            content = Path(file_path).read_text(encoding='utf-8')
        except Exception:
            continue

        try:
            rel_path = str(Path(file_path).relative_to(repo_path))
        except ValueError:
            rel_path = file_path

        # Pattern 1: ## or ### Header followed by definition text
        header_pattern = r'^(#{2,3})\s+(.+?)\n+(.+?)(?=\n#{1,3}\s|\Z)'
        for match in re.finditer(header_pattern, content, re.MULTILINE | re.DOTALL):
            header = match.group(2).strip()
            body = match.group(3).strip()

            if header.lower() in skip_headers:
                continue
            # Skip headers that are just a single common word
            if len(header.split()) == 1 and header.lower() in {'api', 'endpoints', 'routes', 'models'}:
                continue

            # Get first meaningful sentence from body
            first_sentence = body.split('\n')[0].strip()
            # Remove leading markdown formatting
            first_sentence = re.sub(r'^[>\-*]\s*', '', first_sentence)

            if len(first_sentence) > 15:
                name = header.lower().strip()
                if name not in concepts:
                    line_num = content[:match.start()].count('\n') + 1
                    concepts[name] = {
                        "name": name,
                        "definition": first_sentence[:200],
                        "source_file": rel_path,
                        "source_line": line_num,
                    }

        # Pattern 2: **Bold term**: definition or **Bold term** - definition
        bold_pattern = r'\*\*([A-Z][^*]+?)\*\*\s*[:\-–—]\s*(.+?)(?:\n|$)'
        for match in re.finditer(bold_pattern, content):
            term = match.group(1).strip()
            definition = match.group(2).strip()

            if len(term) > 50 or len(definition) < 10:
                continue

            name = term.lower()
            if name not in concepts and name not in skip_headers:
                line_num = content[:match.start()].count('\n') + 1
                concepts[name] = {
                    "name": name,
                    "definition": definition[:200],
                    "source_file": rel_path,
                    "source_line": line_num,
                }

    return list(concepts.values())


# Backward compatibility alias
extract_concepts_from_readme = extract_concepts_from_docs


def _check_terminology_consistency(
    doc_content: str,
    graph_nouns: set[str],
    covered_node_ids: set[str],
    graph: 'SystemGraph',
) -> list[str]:
    """Check if documentation uses consistent terminology with the codebase.

    Compares noun references in documentation against the canonical noun names
    from the system graph. Reports inconsistencies where docs use different
    terms for the same entity.

    Args:
        doc_content: Full text content of the documentation topic
        graph_nouns: Set of canonical noun names from the system graph
        covered_node_ids: IDs of graph nodes this topic covers
        graph: The system graph for looking up node details

    Returns:
        List of terminology issue descriptions (empty = consistent)
    """
    issues = []
    content_lower = doc_content.lower()

    # Common variant patterns: plural/singular mismatches, synonyms
    common_variants = {
        'user': ['users', 'account', 'accounts', 'member', 'members'],
        'item': ['items', 'product', 'products', 'entry', 'entries'],
        'project': ['projects', 'workspace', 'workspaces', 'repo', 'repos'],
        'team': ['teams', 'group', 'groups', 'organization', 'org'],
        'task': ['tasks', 'job', 'jobs', 'work item', 'ticket'],
        'message': ['messages', 'notification', 'notifications', 'alert', 'alerts'],
        'file': ['files', 'document', 'documents', 'attachment', 'attachments'],
        'role': ['roles', 'permission', 'permissions'],
    }

    # For each noun covered by this topic, check if the docs use
    # a different term than the canonical noun name
    covered_nouns = set()
    for node_id in covered_node_ids:
        if node_id.startswith('noun:'):
            covered_nouns.add(node_id[5:])  # strip "noun:" prefix

    for noun in covered_nouns:
        if noun not in content_lower:
            # The canonical noun name isn't in the docs at all
            # Check if a known variant is used instead
            variants = common_variants.get(noun, [])
            used_variant = None
            for variant in variants:
                if variant in content_lower:
                    used_variant = variant
                    break

            if used_variant:
                issues.append(f"docs use '{used_variant}' but code uses '{noun}'")

    return issues


def extract_nouns_from_path(path: str) -> list[str]:
    """Extract noun candidates from an API path."""
    nouns = []

    # Skip paths that are clearly not entity-related
    skip_path_segments = {
        # Rate limiting / constraints
        'rate_limit', 'rate-limit', 'ratelimit', 'rate_limits', 'rate-limits',
        'limit', 'limits', 'rate', 'rates', 'quota', 'quotas',
        # Tiers (constraint, not entity)
        'tier', 'tiers', 'plan', 'plans', 'pricing',
        # Other non-entities
        'config', 'settings', 'admin', 'internal', 'system',
        'health', 'status', 'metrics', 'debug', 'test',
    }

    # Strip common prefixes
    path = re.sub(r'/api/v\d+', '', path)
    path = re.sub(r'/v\d+', '', path)

    segments = [s for s in path.split('/') if s and not s.startswith('{')]

    for i, segment in enumerate(segments):
        segment_lower = segment.lower()

        if segment_lower in ACTION_WORDS:
            continue

        # Skip constraint-related path segments
        if segment_lower in skip_path_segments:
            continue

        if '-' in segment_lower and not segment_lower.endswith('s'):
            continue

        # Check if before a path parameter
        all_parts = path.split('/')
        is_before_param = False
        for j, part in enumerate(all_parts):
            if part == segment and j + 1 < len(all_parts):
                if '{' in all_parts[j + 1]:
                    is_before_param = True
                    break

        is_plural = segment_lower.endswith('s') and len(segment_lower) > 2

        if not (is_plural or is_before_param):
            continue

        # Singularize
        noun = segment_lower
        if noun.endswith('ies'):
            noun = noun[:-3] + 'y'
        elif noun.endswith('es') and len(noun) > 3:
            noun = noun[:-2]
        elif noun.endswith('s') and not noun.endswith('ss'):
            noun = noun[:-1]

        # Strip db_ prefix (db_user -> user, db_post -> post)
        if noun.startswith('db_'):
            noun = noun[3:]
        elif noun.startswith('db') and len(noun) > 2 and noun[2:3].isupper():
            # Handle DbUser -> user (camelCase after db)
            noun = noun[2:].lower()

        if noun and noun not in nouns and len(noun) > 1:
            nouns.append(noun)

    return nouns


def build_system_graph(
    repo_path: str,
    product_name: Optional[str] = None,
    force_type: Optional[str] = None,
) -> SystemGraph:
    """Build a Software System Graph from a repository (auto-detects type).

    Scans code to extract semantic elements: endpoints, entities, concepts,
    and their relationships.

    Supports:
    - Python/FastAPI repositories (REST APIs)
    - Node.js/oclif repositories (CLI tools)

    Args:
        repo_path: Path to the repository root
        product_name: Optional product name (defaults to directory name)
        force_type: Optional type override ('python' or 'nodejs')

    Returns:
        SystemGraph with nodes and edges extracted from code
    """
    repo_type = force_type or detect_repo_type(repo_path)

    if repo_type == "nodejs":
        return build_system_graph_nodejs(repo_path, product_name)
    elif repo_type == "python":
        return build_system_graph_python(repo_path, product_name)
    else:
        raise ValueError(f"Unknown repository type: {repo_type}. Expected 'python' or 'nodejs'.")


# Backward compatibility aliases
build_surface_graph = build_system_graph
build_surface_graph_python = build_system_graph_python
build_surface_graph_nodejs = build_system_graph_nodejs
build_knowledge_graph = build_system_graph


# =============================================================================
# ATM DISCOVERY
# =============================================================================

def _find_git_root(start_path: str) -> Optional[str]:
    """Find the git repository root by looking for .git directory.

    Args:
        start_path: Directory to start searching from

    Returns:
        Absolute path to git root, or None if not in a git repo
    """
    current = Path(start_path).resolve()

    # Search up to 10 levels to avoid infinite loops
    for _ in range(10):
        if (current / '.git').exists():
            return str(current)

        parent = current.parent
        if parent == current:  # Reached filesystem root
            break
        current = parent

    return None


def discover_content_inventory(
    repo_path: str,
    graph: SystemGraph,
) -> TopicManifest:
    """Discover Content Inventory from existing documentation.

    Parses markdown files and matches content to system graph elements.
    Searches in the scanned directory and parent directories (up to git root).

    Returns a TopicManifest with manifest_type=ACTUAL (Content Inventory).
    """
    repo_path = str(Path(repo_path).resolve())

    # Find git root for expanded search
    git_root = _find_git_root(repo_path)

    # Search for markdown files in:
    # 1. The scanned directory
    # 2. Parent directories up to git root
    search_paths = [repo_path]
    if git_root and git_root != repo_path:
        current = Path(repo_path).parent
        while current >= Path(git_root):
            search_paths.append(str(current))
            if current == Path(git_root):
                break
            current = current.parent

    # Collect all markdown files from all search paths
    md_files = []
    seen_files = set()
    for search_path in search_paths:
        for md_file in find_markdown_files(search_path):
            # Dedupe by absolute path
            abs_path = str(Path(md_file).resolve())
            if abs_path not in seen_files:
                seen_files.add(abs_path)
                md_files.append(md_file)

    # Parse doc references from scanned directory only
    doc_references = scan_documentation(repo_path)

    # Build vector store for matching
    vector_store = LocalVectorStore(model_name="all-mpnet-base-v2")
    doc_chunks = []

    for md_file in md_files:
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            try:
                rel_path = str(Path(md_file).relative_to(repo_path))
            except ValueError:
                rel_path = md_file
            chunks = parse_markdown_chunks(content, rel_path)
            doc_chunks.extend(chunks)
        except Exception:
            pass

    if doc_chunks:
        vector_store.add_chunks(doc_chunks)

    # Discover topics from doc structure
    topics: list[Topic] = []
    quality: dict[str, TopicQuality] = {}
    topic_id_counter = 0

    # Group doc chunks - README files by section, other files by file
    # key = (file_path, section_name) for READMEs, (file_path, None) for others
    topic_groups: dict[tuple[str, str | None], list] = {}

    for chunk in doc_chunks:
        file_name = Path(chunk.file_path).name.upper()
        is_readme = file_name.startswith('README')

        if is_readme and chunk.section_header:
            # For READMEs, group by H2 section (second level after the project name)
            # e.g., "FastAPI Blog API > Overview > Details" -> "Overview"
            # e.g., "Overview" -> "Overview"
            section_parts = chunk.section_header.split(' > ')
            if len(section_parts) >= 2:
                # Has H1 (project name) and H2 - use H2
                h2_section = section_parts[1].strip()
            elif len(section_parts) == 1:
                # Only H1 (or direct H2 without H1) - use it
                h2_section = section_parts[0].strip()
            else:
                h2_section = None
            key = (chunk.file_path, h2_section)
        else:
            # For other files, group by file
            key = (chunk.file_path, None)

        if key not in topic_groups:
            topic_groups[key] = []
        topic_groups[key].append(chunk)

    for (file_path, section_name), chunks in topic_groups.items():
        topic_id_counter += 1
        topic_id = f"atm_topic_{topic_id_counter}"

        # Derive topic name from section (if README) or file
        if section_name:
            name = section_name
        else:
            name = Path(file_path).stem.replace("-", " ").replace("_", " ").title()

        # Match chunks to system graph elements
        covered_ids = set()
        for node in graph.user_facing_nodes():
            # Create search signature - include entity names for better matching
            sig_parts = []

            if node.type == NodeType.VERB:
                # Include HTTP method and path
                if node.code_signature:
                    sig_parts.append(node.code_signature)
                # Extract entity names from path (e.g., /users/me -> users)
                if node.http_path:
                    path_segments = [s for s in node.http_path.split('/') if s and not s.startswith('{')]
                    sig_parts.extend(path_segments)
                # Include function name (e.g., get_me -> get me)
                if node.name:
                    sig_parts.append(node.name.replace('_', ' '))
            else:
                sig_parts.append(node.name)

            # Include description/docstring if available
            if node.description:
                sig_parts.append(node.description)

            sig = ' '.join(sig_parts)

            results = vector_store.search(sig, limit=1)
            if results:
                chunk, score = results[0]
                # Check if this chunk is in current file/section
                # Lowered threshold from 0.4 to 0.28 based on analysis
                if chunk.file_path == file_path and score >= 0.28:
                    # For section-based topics, also check section match
                    if section_name:
                        section_parts = (chunk.section_header or "").split(' > ')
                        # Match H2 section (second level) for READMEs
                        if len(section_parts) >= 2:
                            chunk_h2_section = section_parts[1].strip()
                        elif len(section_parts) == 1:
                            chunk_h2_section = section_parts[0].strip()
                        else:
                            chunk_h2_section = ""
                        if chunk_h2_section == section_name:
                            covered_ids.add(node.id)
                    else:
                        covered_ids.add(node.id)

        if covered_ids:  # Only create topic if it covers something
            topic = Topic(
                id=topic_id,
                name=name,
                topic_type=TopicType.REFERENCE,  # Default
                covers=list(covered_ids),
                source_file=file_path,
                auto_generated=True,
            )
            topics.append(topic)

            # Assess quality
            full_content = " ".join(c.content for c in chunks)
            content_lower = full_content.lower()

            # Check for constraint documentation (v3)
            auth_mentioned = any(kw in content_lower for kw in ['authentication', 'auth', 'login', 'token', 'authorization', 'oauth'])
            rate_mentioned = any(kw in content_lower for kw in ['rate limit', 'throttle', 'quota', 'rate-limit', 'ratelimit'])
            prereq_mentioned = any(kw in content_lower for kw in ['prerequisite', 'requires', 'must first', 'before you', 'depends on', 'required before'])

            # Check for machine-readable spec references
            spec_mentioned = any(kw in content_lower for kw in ['openapi', 'swagger', 'json schema', 'graphql schema', 'api spec', '.yaml', '.json'])

            # Check terminology consistency against graph nouns
            graph_nouns = {n.name.lower() for n in graph.nodes if n.type == NodeType.NOUN}
            term_issues = _check_terminology_consistency(full_content, graph_nouns, covered_ids, graph)

            q = TopicQuality(
                has_parameters="partial" if "param" in content_lower else "no",
                has_returns="partial" if "return" in content_lower else "no",
                has_errors="partial" if "error" in content_lower or "exception" in content_lower else "no",
                has_warnings="warning" in content_lower or "caution" in content_lower,
                has_description=len(full_content) > 100,
                has_use_cases="example" in content_lower or "use case" in content_lower,
                has_examples="```" in full_content,
                # v3: Constraint coverage
                has_auth_requirements="yes" if auth_mentioned else "no",
                has_rate_limits="yes" if rate_mentioned else "no",
                has_prerequisites="yes" if prereq_mentioned else "no",
                # v3: Agent navigability
                has_machine_readable_spec=spec_mentioned,
                terminology_consistent=len(term_issues) == 0,
            )

            # Compute coverage score
            score_parts = [
                1.0 if q.has_parameters == "yes" else 0.5 if q.has_parameters == "partial" else 0.0,
                1.0 if q.has_returns == "yes" else 0.5 if q.has_returns == "partial" else 0.0,
                1.0 if q.has_errors == "yes" else 0.5 if q.has_errors == "partial" else 0.0,
                1.0 if q.has_description else 0.0,
                1.0 if q.has_examples else 0.0,
            ]
            q.coverage_score = sum(score_parts) / len(score_parts)

            # v3: Compute constraint score
            constraint_score_parts = [
                1.0 if q.has_auth_requirements == "yes" else 0.5 if q.has_auth_requirements == "partial" else 0.0,
                1.0 if q.has_rate_limits == "yes" else 0.5 if q.has_rate_limits == "partial" else 0.0,
                1.0 if q.has_prerequisites == "yes" else 0.5 if q.has_prerequisites == "partial" else 0.0,
            ]
            q.constraint_score = sum(constraint_score_parts) / len(constraint_score_parts) if constraint_score_parts else 0.0

            # v3: Agent readiness score (coverage + constraints + terminology)
            term_score = 1.0 if q.terminology_consistent else 0.5
            spec_score = 1.0 if q.has_machine_readable_spec else 0.0
            q.agent_readiness_score = (
                q.coverage_score * 0.4
                + q.constraint_score * 0.3
                + term_score * 0.2
                + spec_score * 0.1
            )

            quality[topic_id] = q

    return TopicManifest(
        manifest_type=ManifestType.ACTUAL,
        graph_id=f"{graph.product_name}:{graph.scanned_at.isoformat()}",
        product_name=graph.product_name,
        topics=topics,
        quality=quality,
    )


# Backward compatibility alias
discover_atm = discover_content_inventory


# =============================================================================
# FULL ANALYSIS
# =============================================================================

def analyze_repository(
    repo_path: str,
    product_name: Optional[str] = None,
) -> tuple[SystemGraph, TopicManifest, TopicManifest, DriftReport]:
    """Run full documentation analysis on a repository.

    Returns:
        Tuple of (SystemGraph, ContentCoverageMatrix, ContentInventory, DriftReport)
    """
    # Layer 1: Build System Graph
    graph = build_system_graph(repo_path, product_name)

    # Layer 2: Generate default Coverage Checklist
    matrix = generate_default_itm(graph)

    # Layer 3: Discover Content Inventory from docs
    inventory = discover_content_inventory(repo_path, graph)

    # Layer 4: Compute Drift Report
    drift_report = compute_drift_report(graph, matrix, inventory)

    return graph, matrix, inventory, drift_report


def diff_system_graphs(old: SystemGraph, new: SystemGraph) -> dict:
    """Compare two system graphs and report changes.

    Args:
        old: Previous System Graph
        new: Current System Graph

    Returns:
        Dictionary with added/removed nodes and edges, plus summary stats
    """
    old_node_ids = {n.id for n in old.nodes}
    new_node_ids = {n.id for n in new.nodes}

    old_edge_keys = {
        (e.source_id, e.target_id, e.edge_type.value)
        for e in old.edges
    }
    new_edge_keys = {
        (e.source_id, e.target_id, e.edge_type.value)
        for e in new.edges
    }

    nodes_added = new_node_ids - old_node_ids
    nodes_removed = old_node_ids - new_node_ids
    edges_added = new_edge_keys - old_edge_keys
    edges_removed = old_edge_keys - new_edge_keys

    # Categorize by node type
    added_by_type = {}
    for node_id in nodes_added:
        node = new.get_node(node_id)
        if node:
            node_type = node.type.value
            added_by_type[node_type] = added_by_type.get(node_type, 0) + 1

    removed_by_type = {}
    for node_id in nodes_removed:
        node = old.get_node(node_id)
        if node:
            node_type = node.type.value
            removed_by_type[node_type] = removed_by_type.get(node_type, 0) + 1

    return {
        "nodes_added": list(nodes_added),
        "nodes_removed": list(nodes_removed),
        "nodes_unchanged": list(old_node_ids & new_node_ids),
        "edges_added": list(edges_added),
        "edges_removed": list(edges_removed),
        "summary": {
            "total_nodes_added": len(nodes_added),
            "total_nodes_removed": len(nodes_removed),
            "total_edges_added": len(edges_added),
            "total_edges_removed": len(edges_removed),
            "nodes_added_by_type": added_by_type,
            "nodes_removed_by_type": removed_by_type,
        }
    }


# Backward compatibility aliases
diff_surface_graphs = diff_system_graphs
diff_knowledge_graphs = diff_system_graphs


def print_analysis_summary(
    graph: SystemGraph,
    matrix: TopicManifest,
    inventory: TopicManifest,
    drift_report: DriftReport,
) -> None:
    """Print a summary of the documentation analysis."""
    print("=" * 60)
    print(f"DOCZOT ANALYSIS: {graph.product_name}")
    print("=" * 60)

    # System Graph stats
    print(f"\n--- System Graph ---")
    print(f"Verbs (endpoints): {len(graph.verbs)}")
    print(f"Nouns (entities): {len(graph.nouns)}")
    print(f"Concepts: {len(graph.concepts)}")
    print(f"Constraints: {len(graph.constraints)}")
    print(f"Edges: {len(graph.edges)}")

    # Coverage Checklist stats
    print(f"\n--- Coverage Checklist (Plan) ---")
    print(f"Total topics: {len(matrix.topics)}")
    by_type = {}
    for t in matrix.topics:
        by_type[t.topic_type.value] = by_type.get(t.topic_type.value, 0) + 1
    for ttype, count in by_type.items():
        print(f"  {ttype}: {count}")

    # Content Inventory stats
    print(f"\n--- Content Inventory (Reality) ---")
    print(f"Total topics discovered: {len(inventory.topics)}")
    covered = inventory.covered_surface_ids()
    total_nodes = len(graph.user_facing_nodes())
    print(f"Graph coverage: {len(covered)}/{total_nodes}")

    # Drift Report
    print(f"\n--- Drift Report ---")
    stats = drift_report.coverage_stats()
    print(f"Documentation Coverage: {stats['coverage_percentage']:.1f}%")
    print(f"Complete topics: {stats['complete']}")
    print(f"Partial topics: {stats['partial']}")
    print(f"Missing topics: {stats['missing']}")
    if stats['extra'] > 0:
        print(f"Extra topics (undocumented features): {stats['extra']}")

    # Sprint plan preview
    plan = drift_report.sprint_plan()
    if plan:
        print(f"\n--- Sprint Plan ({len(plan)} items) ---")
        for item in plan[:5]:
            print(f"  [{item['status'].upper()}] {item['topic']}")
            print(f"           {item['action']}")
        if len(plan) > 5:
            print(f"  ... and {len(plan) - 5} more")
