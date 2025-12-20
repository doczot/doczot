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
) -> SurfaceGraph:
    """Build a SurfaceGraph from a repository.

    Scans code for endpoints and extracts:
    - Verb nodes (API endpoints)
    - Noun nodes (entities from paths)
    - Edges (verb operates_on noun)
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

        # Extract nouns and create edges
        nouns = extract_nouns_from_path(ep.path)
        for noun in nouns:
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

    return SurfaceGraph(
        product_name=product_name,
        source_paths=[repo_path],
        nodes=nodes,
        edges=edges,
    )


# =============================================================================
# ATM DISCOVERY
# =============================================================================

def discover_atm(
    repo_path: str,
    surface: SurfaceGraph,
) -> TopicManifest:
    """Discover actual topics from existing documentation.

    Parses markdown files and matches content to surface elements.
    """
    repo_path = str(Path(repo_path).resolve())

    # Find and parse docs
    md_files = find_markdown_files(repo_path)
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
            q = TopicQuality(
                has_parameters="partial" if "param" in full_content.lower() else "no",
                has_returns="partial" if "return" in full_content.lower() else "no",
                has_errors="partial" if "error" in full_content.lower() or "exception" in full_content.lower() else "no",
                has_warnings="warning" in full_content.lower() or "caution" in full_content.lower(),
                has_description=len(full_content) > 100,
                has_use_cases="example" in full_content.lower() or "use case" in full_content.lower(),
                has_examples="```" in full_content,
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
