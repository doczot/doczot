#!/usr/bin/env python3
"""Build a TopicManifest (ITM + ATM) from a repository.

This script demonstrates the full ITM/ATM workflow:
1. Scan code to extract endpoints (verbs) and infer nouns
2. Parse documentation into content pieces
3. Match content to topics and assess coverage
4. Output a complete TopicManifest with quality scores

Usage:
    python scripts/build_manifest.py /path/to/repo [--output manifest.json]
"""
import sys
import os
import re
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from doczot_analyzer.scanner import scan_directory
from doczot_analyzer.docs_parser import scan_documentation, parse_markdown_chunks, find_markdown_files
from doczot_analyzer.matcher import Matcher
from doczot_analyzer.vector_store import LocalVectorStore
from doczot_analyzer.models import Endpoint, DocChunk
from doczot_analyzer.manifest import (
    TopicManifest, TopicNode, TopicEdge, TopicCoverage, ContentPiece,
    QualityScore, TechnicalScore, SemanticScore, ExampleCoverage,
    NodeType, NodeClass, NodeSource, EdgeType, ContentType, DocCategory,
    ConfidenceLevel, CompletenessLevel, ScoreWithConfidence
)


def extract_nouns_from_path(path: str) -> list[str]:
    """Extract noun candidates from an API path.

    Examples:
        /users/{user_id} -> ["user"]
        /projects/{project_id}/tasks/{task_id} -> ["project", "task"]
        /api/v1/invoices -> ["invoice"]
    """
    nouns = []

    # Remove version prefixes
    path = re.sub(r'/api/v\d+', '', path)
    path = re.sub(r'/v\d+', '', path)

    # Extract path segments (excluding parameters)
    segments = [s for s in path.split('/') if s and not s.startswith('{')]

    for segment in segments:
        # Singularize common plurals
        noun = segment.lower()
        if noun.endswith('ies'):
            noun = noun[:-3] + 'y'  # categories -> category
        elif noun.endswith('es') and not noun.endswith('ses'):
            noun = noun[:-2]  # boxes -> box (but not addresses)
        elif noun.endswith('s') and len(noun) > 2:
            noun = noun[:-1]  # users -> user

        # Skip common non-nouns
        skip_words = {'api', 'auth', 'login', 'logout', 'me', 'health', 'docs', 'openapi'}
        if noun not in skip_words and len(noun) > 1:
            nouns.append(noun)

    return list(set(nouns))  # Deduplicate


def extract_verb_from_method_and_path(method: str, path: str, function_name: str) -> str:
    """Extract a verb name from HTTP method and context.

    Examples:
        GET /users -> list_users or get_user (depending on path)
        POST /users -> create_user
        DELETE /users/{id} -> delete_user
    """
    # Get the main noun from path
    nouns = extract_nouns_from_path(path)
    noun = nouns[0] if nouns else "resource"

    # Map HTTP method to action verb
    method_verbs = {
        'GET': 'get' if '{' in path else 'list',
        'POST': 'create',
        'PUT': 'replace',
        'PATCH': 'update',
        'DELETE': 'delete',
        'OPTIONS': 'options',
        'HEAD': 'head',
    }

    verb = method_verbs.get(method.upper(), 'handle')

    # Use function name if it's more descriptive
    if function_name and '_' in function_name:
        # Function names like "recover_password" are better than "create_password"
        return function_name

    return f"{verb}_{noun}"


def endpoint_to_topic_nodes(endpoint: Endpoint) -> tuple[TopicNode, list[TopicNode], list[TopicEdge]]:
    """Convert an Endpoint to TopicNodes (verb + nouns) and edges.

    Returns:
        (verb_node, [noun_nodes], [edges])
    """
    # Create verb node
    verb_name = extract_verb_from_method_and_path(
        endpoint.method,
        endpoint.path,
        endpoint.function_name
    )

    verb_node = TopicNode(
        id=f"verb_{endpoint.method.lower()}_{endpoint.path.replace('/', '_').replace('{', '').replace('}', '')}",
        type=NodeType.VERB,
        name=verb_name,
        description=endpoint.docstring,
        node_class=NodeClass.USER_FACING,
        source=NodeSource.AUTO_API,
        source_location=f"{endpoint.file_path}:{endpoint.line_number}",
        code_signature=f"{endpoint.method} {endpoint.path}",
    )

    # Check if this is an internal/meta endpoint
    internal_patterns = ['/health', '/ready', '/metrics', '/docs', '/openapi', '/redoc']
    if any(p in endpoint.path.lower() for p in internal_patterns):
        verb_node.node_class = NodeClass.INTERNAL

    # Create noun nodes from path
    noun_nodes = []
    edges = []

    for noun in extract_nouns_from_path(endpoint.path):
        noun_node = TopicNode(
            id=f"noun_{noun}",
            type=NodeType.NOUN,
            name=noun.title(),  # "user" -> "User"
            source=NodeSource.AUTO_API,
            source_location=f"{endpoint.file_path}:{endpoint.line_number}",
        )
        noun_nodes.append(noun_node)

        # Create edge: verb operates_on noun
        edge = TopicEdge(
            source_id=verb_node.id,
            target_id=noun_node.id,
            relationship=EdgeType.OPERATES_ON,
            source=NodeSource.AUTO_API,
        )
        edges.append(edge)

    return verb_node, noun_nodes, edges


def assess_technical_quality(endpoint: Endpoint, matched_content: Optional[str]) -> TechnicalScore:
    """Assess technical documentation quality for an endpoint."""
    score = TechnicalScore()

    if not matched_content:
        return score

    content_lower = matched_content.lower()

    # Check for parameter documentation
    if endpoint.parameters:
        param_names = [p.name.lower() for p in endpoint.parameters]
        params_mentioned = sum(1 for p in param_names if p in content_lower)
        if params_mentioned == len(param_names):
            score.has_parameters_docs = "yes"
        elif params_mentioned > 0:
            score.has_parameters_docs = "partial"
        else:
            score.has_parameters_docs = "no"
    else:
        score.has_parameters_docs = "yes"  # No params to document

    # Check for return value documentation
    return_indicators = ['return', 'response', 'result', 'output', '200', '201']
    if any(ind in content_lower for ind in return_indicators):
        score.has_return_docs = "yes"
    else:
        score.has_return_docs = "no"

    # Check for error documentation
    error_indicators = ['error', 'exception', '400', '401', '403', '404', '500', 'fail']
    if any(ind in content_lower for ind in error_indicators):
        score.has_error_docs = "partial"  # Mentioned but may not be complete
    else:
        score.has_error_docs = "no"

    # Check for warnings (destructive actions)
    warning_indicators = ['warning', 'caution', 'danger', 'permanent', 'irreversible', 'careful']
    score.has_warnings = any(ind in content_lower for ind in warning_indicators)

    # Compute overall
    components = [score.has_parameters_docs, score.has_return_docs, score.has_error_docs]
    if all(c == "yes" for c in components):
        level = CompletenessLevel.COMPLETE
    elif all(c == "no" for c in components):
        level = CompletenessLevel.MISSING
    else:
        level = CompletenessLevel.PARTIAL

    score.overall = ScoreWithConfidence(level=level, confidence=ConfidenceLevel.MEDIUM)

    return score


def assess_semantic_quality(endpoint: Endpoint, matched_content: Optional[str]) -> SemanticScore:
    """Assess semantic documentation quality for an endpoint."""
    score = SemanticScore()

    if not matched_content:
        return score

    content_lower = matched_content.lower()

    # Check for description beyond just the signature
    # If content is longer than just method + path, there's probably a description
    min_description_length = 50
    score.has_description = len(matched_content) > min_description_length

    # Check for use case documentation
    use_case_indicators = ['use this', 'when to', 'example', 'for instance', 'such as', 'scenario']
    score.has_use_cases = any(ind in content_lower for ind in use_case_indicators)

    # Check for anti-patterns / warnings
    antipattern_indicators = ['don\'t', 'avoid', 'instead', 'warning', 'note:', 'caution', 'not recommended']
    score.has_anti_patterns = any(ind in content_lower for ind in antipattern_indicators)

    # Check for context (how it relates to other features)
    context_indicators = ['related', 'see also', 'before', 'after', 'requires', 'prerequisite']
    score.has_context = any(ind in content_lower for ind in context_indicators)

    # Compute overall
    has_count = sum([score.has_description, score.has_use_cases, score.has_anti_patterns, score.has_context])
    if has_count >= 3:
        level = CompletenessLevel.COMPLETE
    elif has_count == 0:
        level = CompletenessLevel.MISSING
    else:
        level = CompletenessLevel.PARTIAL

    score.overall = ScoreWithConfidence(level=level, confidence=ConfidenceLevel.MEDIUM)

    return score


def assess_example_coverage(matched_content: Optional[str]) -> ExampleCoverage:
    """Assess example coverage in documentation."""
    coverage = ExampleCoverage()

    if not matched_content:
        return coverage

    content_lower = matched_content.lower()

    # Check for code blocks (generic examples)
    coverage.has_generic_example = '```' in matched_content or '`' in matched_content

    # Check for realistic examples (usually have realistic-looking data)
    realistic_indicators = ['example', 'sample', '"name":', '"email":', 'john', 'jane', '@example']
    coverage.has_use_case_example = any(ind in content_lower for ind in realistic_indicators)

    # Check for error examples
    error_example_indicators = ['error example', 'error response', '"error":', '"detail":']
    coverage.has_error_example = any(ind in content_lower for ind in error_example_indicators)

    # Check if example looks runnable (has curl, httpie, or request format)
    runnable_indicators = ['curl ', 'http ', 'requests.', 'fetch(', 'post(', 'get(']
    coverage.example_is_runnable = any(ind in content_lower for ind in runnable_indicators)

    return coverage


def build_manifest(repo_path: str, product_name: Optional[str] = None) -> TopicManifest:
    """Build a complete TopicManifest from a repository.

    Args:
        repo_path: Path to the repository
        product_name: Name of the product (defaults to repo folder name)

    Returns:
        TopicManifest with ITM (nodes/edges) and ATM (coverage)
    """
    repo_path = os.path.abspath(repo_path)

    if not product_name:
        product_name = os.path.basename(repo_path)

    print(f"Building manifest for: {product_name}")
    print(f"Repository: {repo_path}")
    print("=" * 60)

    # ==========================================================================
    # PHASE 1: Build ITM (Intended Topic Manifest)
    # ==========================================================================
    print("\n[Phase 1] Building ITM (product surface)...")

    # Scan for endpoints
    print("  Scanning code for endpoints...")
    endpoints = scan_directory(repo_path)
    print(f"  Found {len(endpoints)} endpoints")

    # Convert to topic nodes
    all_verb_nodes = []
    all_noun_nodes = {}  # Deduplicate by ID
    all_edges = []

    for endpoint in endpoints:
        verb_node, noun_nodes, edges = endpoint_to_topic_nodes(endpoint)
        all_verb_nodes.append(verb_node)

        for noun_node in noun_nodes:
            if noun_node.id not in all_noun_nodes:
                all_noun_nodes[noun_node.id] = noun_node

        all_edges.extend(edges)

    nodes = all_verb_nodes + list(all_noun_nodes.values())
    print(f"  Created {len(all_verb_nodes)} verb nodes")
    print(f"  Created {len(all_noun_nodes)} noun nodes")
    print(f"  Created {len(all_edges)} edges")

    # ==========================================================================
    # PHASE 2: Parse Documentation
    # ==========================================================================
    print("\n[Phase 2] Parsing documentation...")

    # Get doc references and chunks
    doc_references = scan_documentation(repo_path)
    print(f"  Found {len(doc_references)} doc references")

    md_files = find_markdown_files(repo_path)
    print(f"  Found {len(md_files)} markdown files")

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
        except Exception as e:
            print(f"  Warning: Error processing {md_file}: {e}")

    print(f"  Generated {len(doc_chunks)} doc chunks")

    # Create ContentPieces from doc chunks
    content_pieces = []
    for i, chunk in enumerate(doc_chunks):
        content_piece = ContentPiece(
            id=f"content_{i}",
            type=ContentType.REFERENCE,  # Default, could be smarter
            title=chunk.section_header or f"Section {i}",
            location=f"{chunk.file_path}:{chunk.line_number}",
            content_preview=chunk.content[:200] if chunk.content else None,
            word_count=len(chunk.content.split()) if chunk.content else 0,
        )
        content_pieces.append(content_piece)

    # ==========================================================================
    # PHASE 3: Match and Build ATM (coverage)
    # ==========================================================================
    print("\n[Phase 3] Matching documentation to topics...")

    # Initialize matcher
    vector_store = LocalVectorStore(model_name="all-mpnet-base-v2")
    matcher = Matcher(vector_store)

    # Run the existing matcher (which works on endpoints)
    report = matcher.analyze(endpoints, doc_references, doc_chunks)

    # Build coverage dict
    coverage = {}

    for endpoint in endpoints:
        # Find the corresponding verb node
        verb_id = f"verb_{endpoint.method.lower()}_{endpoint.path.replace('/', '_').replace('{', '').replace('}', '')}"

        # Create coverage entry
        cov = TopicCoverage(
            is_documented=endpoint.is_documented,
            category=DocCategory.AUTO_GENERATED if endpoint.analysis_method == "vector" else (
                DocCategory.CODE_DOCSTRING if endpoint.analysis_method == "exact" else DocCategory.NONE
            ),
            discovery_confidence=ConfidenceLevel.HIGH if endpoint.confidence_score and endpoint.confidence_score > 0.7 else (
                ConfidenceLevel.MEDIUM if endpoint.confidence_score and endpoint.confidence_score > 0.5 else ConfidenceLevel.LOW
            ),
            discovery_method=endpoint.analysis_method,
            discovery_score=endpoint.confidence_score,
        )

        if endpoint.matched_doc_chunk:
            cov.doc_locations = [endpoint.matched_doc_chunk[:100] + "..."]
            cov.matched_content_preview = endpoint.matched_doc_chunk[:500]

            # Assess quality
            cov.quality = QualityScore(
                technical=assess_technical_quality(endpoint, endpoint.matched_doc_chunk),
                semantic=assess_semantic_quality(endpoint, endpoint.matched_doc_chunk),
                examples=assess_example_coverage(endpoint.matched_doc_chunk),
            )

        coverage[verb_id] = cov

    documented_count = sum(1 for c in coverage.values() if c.is_documented)
    print(f"  Matched {documented_count}/{len(coverage)} verb nodes")

    # ==========================================================================
    # PHASE 4: Create Manifest
    # ==========================================================================
    print("\n[Phase 4] Creating manifest...")

    manifest = TopicManifest(
        product_name=product_name,
        generated_at=datetime.now(),
        sources_analyzed=[repo_path],
        nodes=nodes,
        edges=all_edges,
        content=content_pieces,
        coverage=coverage,
    )

    return manifest


def print_manifest_summary(manifest: TopicManifest):
    """Print a summary of the manifest."""
    print("\n" + "=" * 60)
    print("MANIFEST SUMMARY")
    print("=" * 60)

    stats = manifest.coverage_stats()
    print(f"\nProduct: {manifest.product_name}")
    print(f"Generated: {manifest.generated_at}")

    print(f"\n--- Coverage ---")
    print(f"Total topics: {stats['total_topics']}")
    print(f"Documented: {stats['documented']}")
    print(f"Undocumented: {stats['undocumented']}")
    print(f"Coverage: {stats['coverage_percentage']}%")
    print(f"Internal topics (excluded): {stats['internal_topics']}")

    print(f"\n--- By Type ---")
    for node_type, count in stats.get('by_type', {}).items():
        print(f"  {node_type}: {count}")

    quality_stats = manifest.quality_stats()
    if 'total_documented' in quality_stats:
        print(f"\n--- Quality Gaps ---")
        print(f"Missing error docs: {quality_stats['missing_error_docs']}")
        print(f"Missing warnings: {quality_stats['missing_warnings']}")
        print(f"Missing examples: {quality_stats['missing_examples']}")
        print(f"Low semantic quality: {quality_stats['low_semantic_quality']}")

    # Sprint plan
    plan = manifest.sprint_plan()
    if plan:
        print(f"\n--- Sprint Plan ---")
        for action, items in plan.items():
            print(f"\n{action.replace('_', ' ').title()} ({len(items)} items):")
            for item in items[:3]:  # Show first 3
                print(f"  - {item['name']} ({item.get('location', 'unknown')})")
            if len(items) > 3:
                print(f"  ... and {len(items) - 3} more")


def main():
    parser = argparse.ArgumentParser(
        description="Build a TopicManifest (ITM + ATM) from a repository"
    )
    parser.add_argument("repo_path", help="Path to the repository")
    parser.add_argument("--name", help="Product name (defaults to repo folder)")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Build manifest
    manifest = build_manifest(args.repo_path, args.name)

    # Print summary
    print_manifest_summary(manifest)

    # Save if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(manifest.model_dump(mode='json'), f, indent=2, default=str)
        print(f"\n✓ Saved manifest to: {args.output}")


if __name__ == "__main__":
    main()
