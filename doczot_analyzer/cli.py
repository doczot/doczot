"""DocZot CLI - Documentation coverage analysis for API projects."""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from doczot_analyzer.scanner import scan_directory
from doczot_analyzer.docs_parser import (
    scan_documentation,
    parse_markdown_chunks,
    find_markdown_files,
)
from doczot_analyzer.matcher import Matcher
from doczot_analyzer.vector_store import LocalVectorStore
from doczot_analyzer.manifest import (
    TopicManifest,
    TopicNode,
    TopicCoverage,
    QualityScore,
    TechnicalScore,
    SemanticScore,
    ExampleCoverage,
    NodeType,
    NodeClass,
    ConfidenceLevel,
)
from doczot_analyzer.storage import ManifestStore
from doczot_analyzer.visualizer import generate_visualization


def extract_nouns_from_path(path: str) -> list[str]:
    """Extract noun candidates from an API path.

    Only extracts likely entity nouns, not action words.
    """
    import re

    nouns = []

    # Strip common prefixes
    path = re.sub(r'/api/v\d+', '', path)
    path = re.sub(r'/v\d+', '', path)

    # Common action words that should NOT be extracted as nouns
    action_words = {
        'login', 'logout', 'signin', 'signout', 'signup', 'register',
        'authenticate', 'authorize', 'auth', 'oauth', 'callback',
        'forgot-password', 'reset-password', 'change-password', 'recover',
        'password', 'forgot', 'reset', 'recover-password',
        'verify', 'confirm', 'validate', 'activate', 'request-verify-token',
        'request-verify', 'verify-email', 'verify-token',
        'search', 'filter', 'export', 'import', 'download', 'upload',
        'refresh', 'revoke', 'sync', 'batch', 'bulk',
        'health', 'healthz', 'ready', 'readyz', 'live', 'livez',
        'metrics', 'status', 'ping', 'version', 'info',
        'docs', 'openapi', 'swagger', 'redoc', 'schema',
        'me', 'self', 'current', 'api', 'v1', 'v2', 'v3',
    }

    segments = [s for s in path.split('/') if s and not s.startswith('{')]

    for i, segment in enumerate(segments):
        segment_lower = segment.lower()

        if segment_lower in action_words:
            continue

        if '-' in segment_lower:
            if not segment_lower.endswith('s'):
                continue

        is_before_param = (
            i + 1 < len(path.split('/'))
            and '{' in path.split('/')[i + 1]
            if i + 1 < len(path.split('/'))
            else False
        )
        is_plural = segment_lower.endswith('s') and len(segment_lower) > 2

        if not (is_plural or is_before_param):
            continue

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


def build_manifest(repo_path: str, product_name: str | None = None) -> TopicManifest:
    """Build a complete ITM/ATM manifest for a repository."""
    repo_path = str(Path(repo_path).resolve())
    if not product_name:
        product_name = Path(repo_path).name

    # Phase 1: Build ITM (product surface)
    endpoints = scan_directory(repo_path)
    verb_nodes = []
    noun_nodes = []
    seen_nouns = set()

    # HTTP method to verb name mapping
    method_to_verb = {
        "GET": "get",
        "POST": "create",
        "PUT": "update",
        "PATCH": "patch",
        "DELETE": "delete",
    }

    for ep in endpoints:
        # Create verb node for each endpoint
        # Derive verb name from HTTP method + last path segment
        base_verb = method_to_verb.get(ep.method, ep.method.lower())
        # Extract the resource from path (last non-param segment)
        path_segments = [s for s in ep.path.split('/') if s and not s.startswith('{')]
        resource = path_segments[-1] if path_segments else "resource"
        verb_name = f"{base_verb}_{resource}"

        node_id = f"verb:{ep.method}:{ep.path}"
        verb_node = TopicNode(
            id=node_id,
            name=verb_name,
            type=NodeType.VERB,
            node_class=NodeClass.USER_FACING,
            source_location=f"{ep.file_path}:{ep.line_number}",
            code_signature=f"{ep.method} {ep.path}",
        )
        verb_nodes.append(verb_node)

        # Extract and create noun nodes
        nouns = extract_nouns_from_path(ep.path)
        for noun in nouns:
            if noun not in seen_nouns:
                seen_nouns.add(noun)
                noun_node = TopicNode(
                    id=f"noun:{noun}",
                    name=noun,
                    type=NodeType.NOUN,
                    node_class=NodeClass.USER_FACING,
                )
                noun_nodes.append(noun_node)

    all_nodes = verb_nodes + noun_nodes

    # Phase 2: Parse documentation
    doc_references = scan_documentation(repo_path)
    doc_chunks = []
    md_files = find_markdown_files(repo_path)

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

    # Phase 3: Match documentation to topics
    vector_store = LocalVectorStore(model_name="all-mpnet-base-v2")
    matcher = Matcher(vector_store)

    if doc_chunks:
        vector_store.add_chunks(doc_chunks)

    # Phase 4: Create manifest and add coverage
    manifest = TopicManifest(product_name=product_name, nodes=all_nodes)

    for node in verb_nodes:
        # Find the corresponding endpoint for this node
        endpoint_sig = node.name
        if node.code_signature:
            for ep in endpoints:
                if f"{ep.method} {ep.path}" == node.code_signature:
                    endpoint_sig = ep.semantic_signature or node.name
                    break

        results = vector_store.search(endpoint_sig, limit=1)
        is_documented = bool(results and results[0][1] >= 0.5)

        coverage = TopicCoverage(
            is_documented=is_documented,
            discovery_confidence=ConfidenceLevel.MEDIUM if is_documented else ConfidenceLevel.LOW,
            quality=QualityScore(
                technical=TechnicalScore(
                    has_parameters_docs="partial" if is_documented else "no",
                    has_return_docs="partial" if is_documented else "no",
                    has_error_docs="no",
                    has_warnings=False,
                ),
                semantic=SemanticScore(
                    has_description=is_documented,
                    has_use_cases=False,
                    has_anti_patterns=False,
                    has_context=False,
                ),
                examples=ExampleCoverage(
                    has_generic_example=is_documented,
                    has_use_case_example=False,
                    has_error_example=False,
                    example_is_runnable=False,
                ),
            ),
        )
        manifest.coverage[node.id] = coverage

    return manifest


def cmd_analyze(args):
    """Run analysis on a repository."""
    repo_path = args.repo_path or "."
    repo_path = str(Path(repo_path).resolve())

    print(f"Analyzing: {repo_path}")
    print("=" * 60)

    manifest = build_manifest(repo_path, args.name)

    # Print summary
    stats = manifest.coverage_stats()
    quality = manifest.quality_stats()
    print(f"\nProduct: {manifest.product_name}")
    print(f"Generated: {manifest.generated_at}")
    print()
    print("--- Coverage ---")
    print(f"Total topics: {stats['total_topics']}")
    print(f"Documented: {stats['documented']}")
    print(f"Undocumented: {stats['undocumented']}")
    print(f"Coverage: {stats['coverage_percentage']:.1f}%")
    print(f"Internal topics (excluded): {stats['internal_topics']}")
    print()
    print("--- By Type ---")
    for node_type, count in stats.get("by_type", {}).items():
        print(f"  {node_type}: {count}")
    print()
    print("--- Quality Gaps ---")
    print(f"Missing error docs: {quality.get('missing_error_docs', 0)}")
    print(f"Missing warnings: {quality.get('missing_warnings', 0)}")
    print(f"Missing examples: {quality.get('missing_examples', 0)}")
    print(f"Low semantic quality: {quality.get('low_semantic_quality', 0)}")

    if args.sprint_plan:
        print()
        print("--- Sprint Plan ---")
        plan = manifest.sprint_plan()
        for category, items in plan.items():
            if items:
                print(f"\n{category.replace('_', ' ').title()} ({len(items)} items):")
                for item in items[:5]:
                    loc = f"({item['location']})" if item.get('location') else ""
                    print(f"  - {item['name']} {loc}")
                if len(items) > 5:
                    print(f"  ... and {len(items) - 5} more")

    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(manifest.model_dump(), f, indent=2, default=str)
        print(f"\nSaved manifest to: {output_path}")

    if args.save:
        store = ManifestStore(args.db)
        row_id = store.save(manifest)
        print(f"\nSaved to database (id={row_id}): {store.db_path}")

    return 0


def cmd_report(args):
    """Generate a report from a saved manifest."""
    manifest_path = Path(args.manifest_file)
    if not manifest_path.exists():
        print(f"Error: Manifest file not found: {manifest_path}", file=sys.stderr)
        return 1

    with open(manifest_path) as f:
        data = json.load(f)

    manifest = TopicManifest.model_validate(data)

    print(f"Report for: {manifest.product_name}")
    print(f"Generated: {manifest.generated_at}")
    print("=" * 60)

    stats = manifest.coverage_stats()
    print(f"\nCoverage: {stats['coverage_percent']:.1f}%")
    print(f"  Documented: {stats['documented']}/{stats['total_topics']}")
    print(f"  By type: {stats['by_type']}")

    if args.format == "sprint":
        plan = manifest.sprint_plan()
        print("\n--- Sprint Plan ---")
        for category, items in plan.items():
            if items:
                print(f"\n{category.replace('_', ' ').title()}:")
                for item in items:
                    print(f"  - {item['name']}: {item['action']}")

    return 0


def cmd_visualize(args):
    """Generate interactive HTML visualization."""
    import webbrowser

    repo_path = args.repo_path or "."
    repo_path = str(Path(repo_path).resolve())

    print(f"Analyzing: {repo_path}")
    manifest = build_manifest(repo_path, args.name)

    output_path = Path(args.output)
    generate_visualization(manifest, output_path)

    print(f"Visualization saved to: {output_path}")

    if args.open:
        webbrowser.open(f"file://{output_path.resolve()}")
        print("Opened in browser")

    return 0


def cmd_history(args):
    """Show coverage history for a product."""
    store = ManifestStore(args.db)

    if not args.product_name:
        # List all products
        products = store.list_products()
        if not products:
            print("No products found in database.")
            print(f"Run: doczot analyze <path> --save")
            return 0

        print("Products in database:")
        for product in products:
            manifests = store.list_manifests(product_name=product, limit=1)
            if manifests:
                latest = manifests[0]
                print(f"  {product}: {latest['coverage_percentage']:.1f}% coverage")
        return 0

    # Show history for specific product
    history = store.get_history(args.product_name, limit=args.limit)
    if not history:
        print(f"No history found for: {args.product_name}")
        return 1

    print(f"Coverage history for: {args.product_name}")
    print("-" * 50)
    print(f"{'Date':<25} {'Coverage':>10} {'Documented':>12}")
    print("-" * 50)

    for entry in history:
        date = entry['date'][:19]  # Trim microseconds
        print(f"{date:<25} {entry['coverage']:>9.1f}% {entry['documented']:>5}/{entry['total']}")

    return 0


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="doczot",
        description="Documentation coverage analysis for API projects",
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s 0.1.0"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # analyze command
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze a repository for documentation coverage",
    )
    analyze_parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Path to the repository to analyze (default: current directory)",
    )
    analyze_parser.add_argument(
        "--name",
        help="Product name (default: directory name)",
    )
    analyze_parser.add_argument(
        "--output", "-o",
        help="Save manifest to JSON file",
    )
    analyze_parser.add_argument(
        "--sprint-plan",
        action="store_true",
        help="Include sprint plan in output",
    )
    analyze_parser.add_argument(
        "--save",
        action="store_true",
        help="Save manifest to SQLite database",
    )
    analyze_parser.add_argument(
        "--db",
        help="Path to SQLite database (default: .doczot/manifests.db)",
    )
    analyze_parser.set_defaults(func=cmd_analyze)

    # report command
    report_parser = subparsers.add_parser(
        "report",
        help="Generate a report from a saved manifest",
    )
    report_parser.add_argument(
        "manifest_file",
        help="Path to the manifest JSON file",
    )
    report_parser.add_argument(
        "--format",
        choices=["summary", "sprint"],
        default="summary",
        help="Report format",
    )
    report_parser.set_defaults(func=cmd_report)

    # history command
    history_parser = subparsers.add_parser(
        "history",
        help="Show coverage history for a product",
    )
    history_parser.add_argument(
        "product_name",
        nargs="?",
        help="Product name to show history for (omit to list all products)",
    )
    history_parser.add_argument(
        "--db",
        help="Path to SQLite database",
    )
    history_parser.add_argument(
        "--limit", "-n",
        type=int,
        default=20,
        help="Number of entries to show",
    )
    history_parser.set_defaults(func=cmd_history)

    # visualize command
    viz_parser = subparsers.add_parser(
        "visualize",
        help="Generate interactive HTML visualization of product surface",
    )
    viz_parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Path to the repository to visualize",
    )
    viz_parser.add_argument(
        "--name",
        help="Product name",
    )
    viz_parser.add_argument(
        "--output", "-o",
        default="doczot-viz.html",
        help="Output HTML file (default: doczot-viz.html)",
    )
    viz_parser.add_argument(
        "--open",
        action="store_true",
        help="Open visualization in browser",
    )
    viz_parser.set_defaults(func=cmd_visualize)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
