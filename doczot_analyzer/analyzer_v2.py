"""DocZot v2 Analyzer - Build Surface Graph, ITM, and ATM.

This module provides functions to:
1. Build a SurfaceGraph from code scanning
2. Generate default ITM from surface
3. Discover ATM from existing documentation
4. Compute gap reports
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
    SurfaceGraph,
    SurfaceNode,
    SurfaceEdge,
    NodeType,
    NodeClass,
    EdgeType,
    TopicManifest,
    Topic,
    TopicType,
    TopicQuality,
    ManifestType,
    GapReport,
    ConfidenceLevel,
    generate_default_itm,
    compute_gap_report,
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


def build_surface_graph_nodejs(
    repo_path: str,
    product_name: Optional[str] = None,
) -> SurfaceGraph:
    """Build a SurfaceGraph from a Node.js CLI repository.

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

    nodes: list[SurfaceNode] = []
    edges: list[SurfaceEdge] = []
    seen_flags: set[str] = set()

    # Create verb nodes for each command and noun nodes for flags
    for cmd in commands:
        verb_node = SurfaceNode(
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

            flag_node = SurfaceNode(
                id=f"noun:flag:{flag_name}",
                type=NodeType.NOUN,
                name=flag_name,
                description=flag.get('description', f'CLI flag: {flag_name}'),
                source_file=cmd.file_path,
                source_line=1,  # Default to line 1 for flags
            )
            nodes.append(flag_node)

            # Create edge: command operates_on flag
            edge = SurfaceEdge(
                source_id=verb_node.id,
                target_id=flag_node.id,
                edge_type=EdgeType.OPERATES_ON,
                confidence=ConfidenceLevel.HIGH,
            )
            edges.append(edge)

    return SurfaceGraph(
        product_name=product_name,
        source_paths=[repo_path],
        nodes=nodes,
        edges=edges,
    )


def build_surface_graph_python(
    repo_path: str,
    product_name: Optional[str] = None,
) -> SurfaceGraph:
    """Build a SurfaceGraph from a Python/FastAPI repository.

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

    nodes: list[SurfaceNode] = []
    edges: list[SurfaceEdge] = []
    seen_nouns: set[str] = set()

    for ep in endpoints:
        # Create verb node
        base_verb = HTTP_METHOD_TO_VERB.get(ep.method, ep.method.lower())
        path_segments = [s for s in ep.path.split('/') if s and not s.startswith('{')]
        resource = path_segments[-1] if path_segments else "resource"
        verb_name = f"{base_verb}_{resource}"

        verb_node = SurfaceNode(
            id=f"verb:{ep.method}:{ep.path}",
            type=NodeType.VERB,
            name=verb_name,
            source_file=ep.file_path,
            source_line=ep.line_number,
            code_signature=f"{ep.method} {ep.path}",
            http_method=ep.method,
            http_path=ep.path,
        )
        nodes.append(verb_node)

        # Extract nouns from path AND from code analysis
        path_nouns = extract_nouns_from_path(ep.path)

        # Filter code nouns: skip plurals, compound types, and infrastructure
        skip_code_nouns = {'items', 'users', 'access', 'userregister', 'privateuser',
                          'userbase', 'usercreate', 'userupdate', 'userpublic',
                          'itembase', 'itemcreate', 'itemupdate', 'itempublic'}
        code_nouns = [n for n in ep.entity_references if n not in skip_code_nouns]

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
                noun_node = SurfaceNode(
                    id=noun_id,
                    type=NodeType.NOUN,
                    name=noun,
                )
                nodes.append(noun_node)

            # Create edge: verb operates_on noun
            edge = SurfaceEdge(
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

            constraint_node = SurfaceNode(
                id=constraint_id,
                type=NodeType.CONSTRAINT,
                name=constraint['type'],
                description=description,
                source_file=ep.file_path,
                source_line=ep.line_number,
            )
            nodes.append(constraint_node)

            # Create constrained_by edge
            edge = SurfaceEdge(
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

        edges.append(SurfaceEdge(
            source_id=child_id,
            target_id=parent_id,
            edge_type=EdgeType.PART_OF,
            confidence=ConfidenceLevel.HIGH,
        ))

    # v3: Detect prerequisite relationships (auth-protected → auth endpoints)
    prereq_rels = detect_prerequisite_relationships(nodes, edges)

    for source_id, target_id in prereq_rels:
        edges.append(SurfaceEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=EdgeType.PREREQUISITE,
            confidence=ConfidenceLevel.MEDIUM,
        ))

    # v3: Extract concepts from docstrings and README
    docstring_concepts = extract_concepts_from_docstrings(endpoints)
    readme_concepts = extract_concepts_from_readme(repo_path)

    all_concepts = docstring_concepts + readme_concepts
    seen_concept_names = set()

    for concept_data in all_concepts:
        if concept_data['name'] in seen_concept_names:
            continue
        seen_concept_names.add(concept_data['name'])

        concept_node = SurfaceNode(
            id=f"concept:{concept_data['name']}",
            type=NodeType.CONCEPT,
            name=concept_data['name'],
            description=concept_data.get('definition'),
            source_file=concept_data.get('source_file'),
            source_line=concept_data.get('source_line'),
        )
        nodes.append(concept_node)

    return SurfaceGraph(
        product_name=product_name,
        source_paths=[repo_path],
        nodes=nodes,
        edges=edges,
    )


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
    nodes: list[SurfaceNode],
    edges: list[SurfaceEdge]
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
    """Extract concepts from endpoint docstrings.

    Looks for capitalized words in docstrings that might be domain concepts.

    Args:
        endpoints: List of endpoint objects

    Returns:
        List of concept dictionaries with name, definition, source_file, source_line
    """
    concepts = {}  # Use dict to dedupe by name

    for ep in endpoints:
        if not ep.docstring:
            continue

        # Get first sentence
        sentences = ep.docstring.split('.')
        if not sentences:
            continue

        first_sentence = sentences[0].strip()
        words = first_sentence.split()

        for word in words:
            # Look for capitalized words (potential entities/concepts)
            clean = word.strip('.,;:()"\'')
            if len(clean) > 3 and clean[0].isupper():
                # Skip common action words
                if clean in {'Create', 'Update', 'Delete', 'Get', 'List', 'Retrieve', 'Check', 'Return'}:
                    continue

                concept_name = clean.lower()
                if concept_name not in concepts:
                    concepts[concept_name] = {
                        "name": concept_name,
                        "definition": first_sentence,
                        "source_file": ep.file_path,
                        "source_line": ep.line_number,
                    }

    return list(concepts.values())


def extract_concepts_from_readme(repo_path: str) -> list[dict]:
    """Extract concepts from README headers and definitions.

    Looks for markdown headers followed by definition text.

    Args:
        repo_path: Path to the repository

    Returns:
        List of concept dictionaries
    """
    concepts = []

    readme_path = Path(repo_path) / "README.md"
    if not readme_path.exists():
        return concepts

    try:
        content = readme_path.read_text(encoding='utf-8')
    except Exception:
        return concepts

    # Pattern: ## Header followed by definition text
    header_pattern = r'^##\s+(.+?)\n+(.+?)(?=\n##|\n\n##|\Z)'
    matches = re.findall(header_pattern, content, re.MULTILINE | re.DOTALL)

    for header, text in matches:
        # Skip common headers
        if header.lower() in {'install', 'installation', 'usage', 'license', 'contributing', 'features', 'setup'}:
            continue

        # Get first meaningful sentence
        first_sentence = text.strip().split('.')[0] + '.'

        if len(first_sentence) > 20:  # Meaningful definition
            concepts.append({
                "name": header.strip().lower(),
                "definition": first_sentence[:200],  # Limit length
                "source_file": str(readme_path),
                "source_line": 0,
            })

    return concepts


def extract_nouns_from_path(path: str) -> list[str]:
    """Extract noun candidates from an API path."""
    nouns = []

    # Strip common prefixes
    path = re.sub(r'/api/v\d+', '', path)
    path = re.sub(r'/v\d+', '', path)

    segments = [s for s in path.split('/') if s and not s.startswith('{')]

    for i, segment in enumerate(segments):
        segment_lower = segment.lower()

        if segment_lower in ACTION_WORDS:
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

        if noun and noun not in nouns:
            nouns.append(noun)

    return nouns


def build_surface_graph(
    repo_path: str,
    product_name: Optional[str] = None,
    force_type: Optional[str] = None,
) -> SurfaceGraph:
    """Build a SurfaceGraph from a repository (auto-detects type).

    Supports:
    - Python/FastAPI repositories (REST APIs)
    - Node.js/oclif repositories (CLI tools)

    Args:
        repo_path: Path to the repository root
        product_name: Optional product name (defaults to directory name)
        force_type: Optional type override ('python' or 'nodejs')

    Returns:
        SurfaceGraph with nodes and edges extracted from code
    """
    repo_type = force_type or detect_repo_type(repo_path)

    if repo_type == "nodejs":
        return build_surface_graph_nodejs(repo_path, product_name)
    elif repo_type == "python":
        return build_surface_graph_python(repo_path, product_name)
    else:
        raise ValueError(f"Unknown repository type: {repo_type}. Expected 'python' or 'nodejs'.")


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


def discover_atm(
    repo_path: str,
    surface: SurfaceGraph,
) -> TopicManifest:
    """Discover actual topics from existing documentation.

    Parses markdown files and matches content to surface elements.
    Searches in the scanned directory and parent directories (up to git root).
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

    # Group doc chunks by file (each file = potential topic)
    files_to_chunks: dict[str, list] = {}
    for chunk in doc_chunks:
        if chunk.file_path not in files_to_chunks:
            files_to_chunks[chunk.file_path] = []
        files_to_chunks[chunk.file_path].append(chunk)

    for file_path, chunks in files_to_chunks.items():
        topic_id_counter += 1
        topic_id = f"atm_topic_{topic_id_counter}"

        # Derive topic name from file
        name = Path(file_path).stem.replace("-", " ").replace("_", " ").title()

        # Match chunks to surface elements
        covered_ids = set()
        for node in surface.user_facing_nodes():
            # Create search signature
            if node.type == NodeType.VERB and node.code_signature:
                sig = node.code_signature
            else:
                sig = node.name

            results = vector_store.search(sig, limit=1)
            if results:
                chunk, score = results[0]
                # Check if this chunk is in current file
                if chunk.file_path == file_path and score >= 0.4:
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
            auth_mentioned = any(kw in content_lower for kw in ['authentication', 'auth', 'login', 'token'])
            rate_mentioned = any(kw in content_lower for kw in ['rate limit', 'throttle', 'quota'])

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
            ]
            q.constraint_score = sum(constraint_score_parts) / len(constraint_score_parts) if constraint_score_parts else 0.0

            # v3: Agent readiness score (combination of coverage and constraints)
            q.agent_readiness_score = (q.coverage_score + q.constraint_score) / 2

            quality[topic_id] = q

    return TopicManifest(
        manifest_type=ManifestType.ACTUAL,
        surface_id=f"{surface.product_name}:{surface.scanned_at.isoformat()}",
        product_name=surface.product_name,
        topics=topics,
        quality=quality,
    )


# =============================================================================
# FULL ANALYSIS
# =============================================================================

def analyze_repository(
    repo_path: str,
    product_name: Optional[str] = None,
) -> tuple[SurfaceGraph, TopicManifest, TopicManifest, GapReport]:
    """Run full analysis on a repository.

    Returns:
        Tuple of (SurfaceGraph, ITM, ATM, GapReport)
    """
    # Layer 1: Build surface graph
    surface = build_surface_graph(repo_path, product_name)

    # Layer 2: Generate default ITM
    itm = generate_default_itm(surface)

    # Layer 3: Discover ATM from docs
    atm = discover_atm(repo_path, surface)

    # Layer 4: Compute gap report
    gap_report = compute_gap_report(surface, itm, atm)

    return surface, itm, atm, gap_report


def diff_surface_graphs(old: SurfaceGraph, new: SurfaceGraph) -> dict:
    """Compare two surface graphs and report changes.

    Args:
        old: Previous Surface Graph
        new: Current Surface Graph

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


def print_analysis_summary(
    surface: SurfaceGraph,
    itm: TopicManifest,
    atm: TopicManifest,
    gap_report: GapReport,
) -> None:
    """Print a summary of the analysis."""
    print("=" * 60)
    print(f"DOCZOT ANALYSIS: {surface.product_name}")
    print("=" * 60)

    # Surface stats
    print(f"\n--- Surface Graph ---")
    print(f"Verbs (endpoints): {len(surface.verbs)}")
    print(f"Nouns (entities): {len(surface.nouns)}")
    print(f"Concepts: {len(surface.concepts)}")
    print(f"Constraints: {len(surface.constraints)}")  # v3
    print(f"Edges: {len(surface.edges)}")

    # ITM stats
    print(f"\n--- ITM (Intended Topics) ---")
    print(f"Total topics: {len(itm.topics)}")
    by_type = {}
    for t in itm.topics:
        by_type[t.topic_type.value] = by_type.get(t.topic_type.value, 0) + 1
    for ttype, count in by_type.items():
        print(f"  {ttype}: {count}")

    # ATM stats
    print(f"\n--- ATM (Actual Topics) ---")
    print(f"Total topics discovered: {len(atm.topics)}")
    covered = atm.covered_surface_ids()
    total_surface = len(surface.user_facing_nodes())
    print(f"Surface coverage: {len(covered)}/{total_surface}")

    # Gap report
    print(f"\n--- Gap Report ---")
    stats = gap_report.coverage_stats()
    print(f"Coverage: {stats['coverage_percentage']:.1f}%")
    print(f"Complete topics: {stats['complete']}")
    print(f"Partial topics: {stats['partial']}")
    print(f"Missing topics: {stats['missing']}")
    if stats['extra'] > 0:
        print(f"Extra topics (in ATM but not ITM): {stats['extra']}")

    # Sprint plan preview
    plan = gap_report.sprint_plan()
    if plan:
        print(f"\n--- Sprint Plan ({len(plan)} items) ---")
        for item in plan[:5]:
            print(f"  [{item['status'].upper()}] {item['topic']}")
            print(f"           {item['action']}")
        if len(plan) > 5:
            print(f"  ... and {len(plan) - 5} more")
