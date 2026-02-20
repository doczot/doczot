"""CLI commands for the validation framework.

Provides `doczot validate` subcommands for running validators,
comparing against OpenAPI specs, managing golden files, and
viewing validation results.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from doczot_analyzer.models_v2 import SystemGraph
from validation.models import (
    ValidationReport,
    ValidationStatus,
    CheckResult,
)


def _status_symbol(status: ValidationStatus) -> str:
    """Text status indicator."""
    return {
        ValidationStatus.PASS: "[PASS]",
        ValidationStatus.WARN: "[WARN]",
        ValidationStatus.FAIL: "[FAIL]",
        ValidationStatus.SKIPPED: "[SKIP]",
    }[status]


def _print_results(results: list[CheckResult]) -> None:
    """Print check results to stdout."""
    for r in results:
        sym = _status_symbol(r.status)
        print(f"  {sym} {r.name}: {r.message}")
        for detail in r.details[:5]:
            print(f"         {detail}")
        if len(r.details) > 5:
            print(f"         ... and {len(r.details) - 5} more")


def _print_summary(report: ValidationReport) -> None:
    """Print summary of a validation report."""
    summary = report.summary()
    total = sum(summary.values())
    print(f"\nValidation Summary: {total} checks")
    print(f"  Pass: {summary['pass']}  Warn: {summary['warn']}  "
          f"Fail: {summary['fail']}  Skipped: {summary['skipped']}")

    if report.is_healthy():
        print("\nResult: HEALTHY")
    else:
        print("\nResult: ISSUES FOUND")


def cmd_validate_run(args: argparse.Namespace) -> int:
    """Run automated validation checks on a repository."""
    from doczot_analyzer.analyzer_v2 import build_system_graph, analyze_repository
    from validation.validators.graph_consistency import validate_graph_consistency
    from validation.validators.cross_layer import validate_cross_layer
    from validation.validators.determinism import validate_determinism_from_graphs

    repo_path = args.repo_path
    product_name = args.name or Path(repo_path).name
    dimension_filter = getattr(args, "dimension", None)

    print(f"Validating: {product_name} ({repo_path})")
    print()

    all_results: list[CheckResult] = []

    # Graph consistency
    if not dimension_filter or dimension_filter == "graph_consistency":
        print("Graph Consistency:")
        graph = build_system_graph(repo_path, product_name)
        results = validate_graph_consistency(graph)
        _print_results(results)
        all_results.extend(results)

    # Cross-layer consistency
    if not dimension_filter or dimension_filter == "cross_layer":
        print("\nCross-Layer Consistency:")
        try:
            graph, itm, atm, drift = analyze_repository(repo_path, product_name)
            results = validate_cross_layer(graph, itm, atm, drift)
            _print_results(results)
            all_results.extend(results)
        except Exception as e:
            skip = CheckResult(
                name="cross_layer",
                dimension="cross_layer",
                status=ValidationStatus.SKIPPED,
                message=f"Could not run full analysis: {e}",
            )
            _print_results([skip])
            all_results.append(skip)

    # Determinism
    if not dimension_filter or dimension_filter == "determinism":
        print("\nDeterminism:")
        graph_a = build_system_graph(repo_path, product_name)
        graph_b = build_system_graph(repo_path, product_name)
        results = validate_determinism_from_graphs(graph_a, graph_b)
        _print_results(results)
        all_results.extend(results)

    report = ValidationReport(
        product_name=product_name,
        results=all_results,
    )
    _print_summary(report)

    # Save results if db-path provided
    if hasattr(args, "db_path") and args.db_path:
        _save_results(args.db_path, report)

    return 0 if report.is_healthy() else 1


def cmd_validate_openapi(args: argparse.Namespace) -> int:
    """Compare SystemGraph against an OpenAPI spec."""
    from doczot_analyzer.analyzer_v2 import build_system_graph
    from validation.validators.openapi_compare import compare_openapi, load_openapi_spec

    repo_path = args.repo_path
    openapi_source = args.openapi_path
    product_name = args.name or Path(repo_path).name

    print(f"Comparing: {product_name} vs {openapi_source}")
    print()

    graph = build_system_graph(repo_path, product_name)
    spec = load_openapi_spec(openapi_source)
    result, comparison = compare_openapi(graph, spec)

    _print_results([result])

    if args.verbose:
        print(f"\n  Matched ({len(comparison['in_both'])}):")
        for ep in comparison["in_both"]:
            print(f"    {ep}")
        if comparison["openapi_only"]:
            print(f"\n  Missing from DocZot ({len(comparison['openapi_only'])}):")
            for ep in comparison["openapi_only"]:
                print(f"    {ep}")
        if comparison["doczot_only"]:
            print(f"\n  Extra in DocZot ({len(comparison['doczot_only'])}):")
            for ep in comparison["doczot_only"]:
                print(f"    {ep}")

    return 0 if result.status != ValidationStatus.FAIL else 1


def cmd_validate_golden_update(args: argparse.Namespace) -> int:
    """Regenerate golden files from fixtures."""
    from validation.golden.generate import regenerate_golden_files

    print("Regenerating golden files...")
    updated = regenerate_golden_files()
    for path in updated:
        print(f"  Updated: {path}")
    print(f"\n{len(updated)} golden file(s) updated.")
    return 0


def cmd_validate_report(args: argparse.Namespace) -> int:
    """Show the latest validation results from the database."""
    from doczot_analyzer.storage import ManifestStore

    db_path = args.db_path
    store = ManifestStore(db_path)

    try:
        results = _load_results(db_path, args.product)
    except Exception:
        print("No validation results found. Run `doczot validate run` first.")
        return 1

    if not results:
        print("No validation results found. Run `doczot validate run` first.")
        return 1

    _print_results(results)
    return 0


def _save_results(db_path: str, report: ValidationReport) -> None:
    """Save validation results to the database."""
    import sqlite3

    db = Path(db_path)
    db.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS validation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                scan_id TEXT,
                dimension TEXT NOT NULL,
                check_name TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                details TEXT,
                checked_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_validation_product
            ON validation_results(product_name)
        """)

        for result in report.results:
            conn.execute("""
                INSERT INTO validation_results
                (product_name, scan_id, dimension, check_name, status, message, details, checked_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report.product_name,
                report.scan_id,
                result.dimension.value if hasattr(result.dimension, "value") else str(result.dimension),
                result.name,
                result.status.value,
                result.message,
                json.dumps(result.details),
                result.checked_at.isoformat(),
            ))
        conn.commit()


def _load_results(db_path: str, product_name: str | None = None) -> list[CheckResult]:
    """Load latest validation results from the database."""
    import sqlite3

    db = Path(db_path)
    if not db.exists():
        return []

    with sqlite3.connect(db) as conn:
        if product_name:
            cursor = conn.execute("""
                SELECT dimension, check_name, status, message, details, checked_at
                FROM validation_results
                WHERE product_name = ?
                ORDER BY checked_at DESC
                LIMIT 50
            """, (product_name,))
        else:
            cursor = conn.execute("""
                SELECT dimension, check_name, status, message, details, checked_at
                FROM validation_results
                ORDER BY checked_at DESC
                LIMIT 50
            """)

        results = []
        for row in cursor.fetchall():
            results.append(CheckResult(
                name=row[1],
                dimension=row[0],
                status=ValidationStatus(row[2]),
                message=row[3],
                details=json.loads(row[4]) if row[4] else [],
                checked_at=datetime.fromisoformat(row[5]),
            ))
        return results


def register_validate_commands(subparsers: argparse._SubParsersAction) -> None:
    """Register the validate command group with the main CLI parser."""
    # validate run
    p = subparsers.add_parser("validate", help="Validate DocZot output accuracy")
    validate_sub = p.add_subparsers(dest="validate_command", help="Validation commands")

    run_p = validate_sub.add_parser("run", help="Run automated validation checks")
    run_p.add_argument("repo_path", nargs="?", default=".")
    run_p.add_argument("--name", help="Product name")
    run_p.add_argument("--dimension", choices=[
        "graph_consistency", "cross_layer", "determinism",
    ], help="Run only this dimension")
    run_p.add_argument("--db-path", default=".doczot/manifests.db", help="Database path")
    run_p.set_defaults(func=cmd_validate_run)

    # validate compare-openapi
    oa_p = validate_sub.add_parser("compare-openapi", help="Compare against OpenAPI spec")
    oa_p.add_argument("repo_path")
    oa_p.add_argument("openapi_path", help="Path or URL to OpenAPI spec")
    oa_p.add_argument("--name", help="Product name")
    oa_p.add_argument("--verbose", "-v", action="store_true")
    oa_p.set_defaults(func=cmd_validate_openapi)

    # validate golden-update
    gu_p = validate_sub.add_parser("golden-update", help="Regenerate golden files")
    gu_p.set_defaults(func=cmd_validate_golden_update)

    # validate report
    rp_p = validate_sub.add_parser("report", help="Show latest validation results")
    rp_p.add_argument("--product", help="Filter by product name")
    rp_p.add_argument("--db-path", default=".doczot/manifests.db", help="Database path")
    rp_p.set_defaults(func=cmd_validate_report)
