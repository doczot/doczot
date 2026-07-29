"""Corpus runner and scorer.

Runs DocZot against each hand-labeled case and compares the result to the
answer key. Reports per-dimension checks plus precision/recall/F1 for the
central question: does DocZot classify each endpoint's documentation status the
way a human labeler did?

Usage:
    python -m doczot_analyzer.tests.corpus._harness
    python -m doczot_analyzer.tests.corpus._harness --case fastapi_partial -v
    python -m doczot_analyzer.tests.corpus._harness --json report.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

CASES_DIR = Path(__file__).parent / "cases"


# =============================================================================
# RESULT TYPES
# =============================================================================

@dataclass
class Check:
    """One scored assertion."""

    name: str
    passed: bool
    detail: str = ""
    missing: list[str] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"name": self.name, "passed": self.passed}
        if self.detail:
            d["detail"] = self.detail
        if self.missing:
            d["missing"] = self.missing
        if self.unexpected:
            d["unexpected"] = self.unexpected
        return d


@dataclass
class CaseResult:
    """Outcome of running one case."""

    name: str
    description: str = ""
    checks: list[Check] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    known_failing: bool = False
    known_failing_reason: str = ""

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]

    @property
    def passed(self) -> bool:
        return self.error is None and not self.failures

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "passed": self.passed,
            "known_failing": self.known_failing,
            "known_failing_reason": self.known_failing_reason,
            "error": self.error,
            "checks": [c.to_dict() for c in self.checks],
            "metrics": self.metrics,
        }


# =============================================================================
# HELPERS
# =============================================================================

def _ep_key(method: str, path: str) -> str:
    """Canonical label for an endpoint in reports."""
    return f"{method.upper()} {path}"


def _verb_id(method: str, path: str) -> str:
    """Node ID the analyzer assigns to an HTTP endpoint."""
    return f"verb:{method.upper()}:{path}"


def _cli_verb_id(name: str) -> str:
    """Node ID the analyzer assigns to a CLI command."""
    return f"verb:CLI:{name}"


def _set_check(
    name: str,
    expected: set[str],
    actual: set[str],
    *,
    exact: bool = True,
) -> Check:
    """Compare two label sets.

    With exact=True, extras count as failures too: a scanner that invents
    endpoints is as broken as one that misses them.
    """
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    passed = not missing and (not unexpected or not exact)
    if passed:
        detail = f"{len(expected)} expected, all found"
    else:
        bits = []
        if missing:
            bits.append(f"{len(missing)} missing")
        if unexpected and exact:
            bits.append(f"{len(unexpected)} unexpected")
        detail = ", ".join(bits)
    return Check(
        name=name,
        passed=passed,
        detail=detail,
        missing=missing,
        unexpected=unexpected if exact else [],
    )


def _prf(true_pos: int, false_pos: int, false_neg: int) -> dict[str, float]:
    """Precision, recall and F1 for the documented/undocumented decision."""
    precision = true_pos / (true_pos + false_pos) if (true_pos + false_pos) else 1.0
    recall = true_pos / (true_pos + false_neg) if (true_pos + false_neg) else 1.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )
    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "true_positives": true_pos,
        "false_positives": false_pos,
        "false_negatives": false_neg,
    }


# =============================================================================
# ISOLATION
# =============================================================================

def _materialize(case_dir: Path, dest: Path) -> Path:
    """Copy a case's repo into an isolated directory with its own git root.

    discover_content_inventory() walks upward from the scan path to the
    enclosing git root and harvests markdown from every directory on the way.
    Analyzing a case in place would therefore credit DocZot's own README and
    docs/ as coverage for the fixture. Creating a .git marker inside the
    destination stops that walk at the fixture boundary, which is what happens
    for a real user analyzing a real repository.
    """
    repo_src = case_dir / "repo"
    repo_dst = dest / case_dir.name
    shutil.copytree(repo_src, repo_dst)
    (repo_dst / ".git").mkdir()
    return repo_dst


# =============================================================================
# SCORING
# =============================================================================

def score_case(case_dir: Path, tmp_root: Path) -> CaseResult:
    """Run one case and score it against its answer key."""
    from doczot_analyzer.analyzer_v2 import analyze_repository, detect_repo_type

    key = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
    result = CaseResult(
        name=key.get("name", case_dir.name),
        description=key.get("description", ""),
        known_failing=key.get("known_failing", False),
        known_failing_reason=key.get("known_failing_reason", ""),
    )

    repo = _materialize(case_dir, tmp_root)

    try:
        graph, checklist, inventory, drift = analyze_repository(
            str(repo), product_name=result.name
        )
    except Exception as exc:  # noqa: BLE001 - a crash is a finding, not a stop
        result.error = f"{type(exc).__name__}: {exc}"
        return result

    # --- repo type ---------------------------------------------------------
    if "repo_type" in key:
        actual_type = detect_repo_type(str(repo))
        result.checks.append(
            Check(
                name="repo_type",
                passed=actual_type == key["repo_type"],
                detail=f"expected {key['repo_type']!r}, got {actual_type!r}",
            )
        )

    # --- HTTP endpoint detection -------------------------------------------
    http_verbs = [v for v in graph.verbs if v.http_method and v.http_path]
    if "endpoints" in key:
        expected = {_ep_key(e["method"], e["path"]) for e in key["endpoints"]}
        actual = {_ep_key(v.http_method, v.http_path) for v in http_verbs}
        result.checks.append(_set_check("endpoints", expected, actual))

    # --- CLI command detection ---------------------------------------------
    if "cli_commands" in key:
        expected = set(key["cli_commands"])
        actual = {
            v.id[len("verb:CLI:"):]
            for v in graph.verbs
            if v.id.startswith("verb:CLI:")
        }
        result.checks.append(_set_check("cli_commands", expected, actual))

    # --- nouns -------------------------------------------------------------
    if "nouns" in key:
        expected = {n.lower() for n in key["nouns"]}
        actual = {n.name.lower() for n in graph.nouns}
        result.checks.append(_set_check("nouns", expected, actual))

    # --- concepts ----------------------------------------------------------
    concept_names = {c.name.lower() for c in graph.concepts}
    if "required_concepts" in key:
        expected = {c.lower() for c in key["required_concepts"]}
        result.checks.append(
            _set_check(
                "required_concepts", expected, concept_names, exact=False
            )
        )
    if "forbidden_concepts" in key:
        hits = sorted(
            name
            for name in concept_names
            if any(bad.lower() in name for bad in key["forbidden_concepts"])
        )
        result.checks.append(
            Check(
                name="forbidden_concepts",
                passed=not hits,
                detail=(
                    "no noise concepts"
                    if not hits
                    else f"{len(hits)} sentence-fragment concepts extracted"
                ),
                unexpected=hits,
            )
        )

    # --- constraints -------------------------------------------------------
    if "constraints" in key:
        expected = {
            f"{c['type']} on {_ep_key(c['method'], c['path'])}"
            for c in key["constraints"]
        }
        actual = set()
        for edge in graph.edges:
            if edge.edge_type.value != "constrained_by":
                continue
            target = graph.get_node(edge.target_id)
            source = graph.get_node(edge.source_id)
            if not target or not source or not source.http_method:
                continue
            ctype = target.name.split(":")[0].strip()
            actual.add(
                f"{ctype} on {_ep_key(source.http_method, source.http_path or '')}"
            )
        result.checks.append(_set_check("constraints", expected, actual))

    # --- edges -------------------------------------------------------------
    if "edges" in key:
        expected = {
            f"{e['source']} -{e['type']}-> {e['target']}" for e in key["edges"]
        }
        actual = {
            f"{e.source_id} -{e.edge_type.value}-> {e.target_id}"
            for e in graph.edges
        }
        result.checks.append(
            _set_check("edges", expected, actual, exact=False)
        )

    # --- THE CORE CHECK: coverage classification ---------------------------
    covered_ids = inventory.covered_surface_ids()

    if "documented_endpoints" in key or "undocumented_endpoints" in key:
        doc_labels = {
            _ep_key(e["method"], e["path"]): True
            for e in key.get("documented_endpoints", [])
        }
        doc_labels.update(
            {
                _ep_key(e["method"], e["path"]): False
                for e in key.get("undocumented_endpoints", [])
            }
        )
        result.checks.append(
            _classify_check(
                "endpoint_coverage_classification",
                doc_labels,
                {
                    _ep_key(e["method"], e["path"]): _verb_id(
                        e["method"], e["path"]
                    )
                    for e in key.get("documented_endpoints", [])
                    + key.get("undocumented_endpoints", [])
                },
                covered_ids,
                result,
            )
        )

    if "documented_cli_commands" in key or "undocumented_cli_commands" in key:
        cli_labels = {
            c: True for c in key.get("documented_cli_commands", [])
        }
        cli_labels.update(
            {c: False for c in key.get("undocumented_cli_commands", [])}
        )
        result.checks.append(
            _classify_check(
                "cli_coverage_classification",
                cli_labels,
                {c: _cli_verb_id(c) for c in cli_labels},
                covered_ids,
                result,
                metric_key="cli_classification",
            )
        )

    # --- headline coverage percentage --------------------------------------
    stats = drift.coverage_stats()
    pct = stats.get("operation_coverage_percentage", 0.0)
    result.metrics["reported_coverage_percentage"] = pct
    result.metrics["topic_weighted_coverage_percentage"] = stats.get(
        "coverage_percentage", 0.0
    )
    result.metrics["drift_stats"] = stats
    result.metrics["checklist_topics"] = len(checklist.topics)
    result.metrics["inventory_topics"] = len(inventory.topics)
    result.metrics["inventory_source_files"] = sorted(
        {t.source_file for t in inventory.topics if t.source_file}
    )

    if "coverage_percentage" in key:
        band = key["coverage_percentage"]
        lo, hi = band["min"], band["max"]
        result.checks.append(
            Check(
                name="coverage_percentage",
                passed=lo <= pct <= hi,
                detail=f"reported {pct}%, expected {lo}–{hi}%",
            )
        )
        result.checks.append(_band_matches_labels(key, lo, hi))

    # --- inventory containment --------------------------------------------
    # Every documentation source credited as coverage must live inside the
    # analyzed repository. Anything outside it is borrowed credit.
    repo_resolved = repo.resolve()
    outside = []
    for topic in inventory.topics:
        if not topic.source_file:
            continue
        src = Path(topic.source_file)
        try:
            candidate = src if src.is_absolute() else (repo_resolved / src)
            candidate.resolve().relative_to(repo_resolved)
        except (ValueError, OSError):
            outside.append(f"{topic.name} <- {topic.source_file}")
    result.checks.append(
        Check(
            name="inventory_containment",
            passed=not outside,
            detail=(
                "all doc sources inside the analyzed repo"
                if not outside
                else f"{len(outside)} topics sourced from outside the repo"
            ),
            unexpected=sorted(outside),
        )
    )

    # --- duplicate checklist topic names ----------------------------------
    if "max_duplicate_topic_names" in key:
        counts = Counter(t.name for t in checklist.topics if t.covers)
        dupes = sorted(
            f"{name} x{n}" for name, n in counts.items() if n > 1
        )
        limit = key["max_duplicate_topic_names"]
        result.checks.append(
            Check(
                name="duplicate_topic_names",
                passed=len(dupes) <= limit,
                detail=f"{len(dupes)} duplicated titles, limit {limit}",
                unexpected=dupes,
            )
        )

    return result


def _band_matches_labels(key: dict, lo: float, hi: float) -> Check:
    """Verify the expected coverage band is what the labels imply.

    Operation coverage is a plain ratio of documented operations to total
    operations, so the expected value is not a matter of taste — it follows
    arithmetically from the documented/undocumented lists. Checking that here
    makes a band physically unable to drift from its own labels, which is the
    one edit that would quietly destroy this corpus's value: widening a
    tolerance, or nudging a number, to make a failing case pass.

    A case that genuinely needs a range (because operation counting excludes
    some endpoints, say) must say so by disagreeing here deliberately.
    """
    documented = (
        len(key.get("documented_endpoints", []))
        + len(key.get("documented_cli_commands", []))
    )
    total = documented + (
        len(key.get("undocumented_endpoints", []))
        + len(key.get("undocumented_cli_commands", []))
    )

    if not total:
        return Check(
            name="coverage_band_matches_labels",
            passed=True,
            detail="no operation labels to derive from",
        )

    derived = round(documented / total * 100, 1)
    passed = lo <= derived <= hi

    return Check(
        name="coverage_band_matches_labels",
        passed=passed,
        detail=(
            f"labels imply {derived}% ({documented}/{total}), "
            f"band is {lo}–{hi}%"
        ),
    )


def _classify_check(
    check_name: str,
    labels: dict[str, bool],
    id_map: dict[str, str],
    covered_ids: set[str],
    result: CaseResult,
    metric_key: str = "classification",
) -> Check:
    """Score DocZot's documented/undocumented verdict against human labels.

    A true positive is an item the human labeled documented that DocZot also
    credits as covered. A false positive is coverage DocZot invented — the
    failure mode that makes a gap report untrustworthy.
    """
    tp = fp = fn = tn = 0
    wrong: list[str] = []

    for label_name, human_says_documented in sorted(labels.items()):
        node_id = id_map[label_name]
        doczot_says_documented = node_id in covered_ids

        if human_says_documented and doczot_says_documented:
            tp += 1
        elif human_says_documented and not doczot_says_documented:
            fn += 1
            wrong.append(f"{label_name}: documented, reported as a gap")
        elif not human_says_documented and doczot_says_documented:
            fp += 1
            wrong.append(f"{label_name}: undocumented, credited as covered")
        else:
            tn += 1

    metrics = _prf(tp, fp, fn)
    metrics["true_negatives"] = tn
    result.metrics[metric_key] = metrics

    return Check(
        name=check_name,
        passed=not wrong,
        detail=(
            f"{tp} TP / {tn} TN / {fp} FP / {fn} FN, F1={metrics['f1']}"
        ),
        unexpected=wrong,
    )


# =============================================================================
# RUNNER
# =============================================================================

def discover_cases() -> list[Path]:
    """All case directories, sorted by name."""
    if not CASES_DIR.exists():
        return []
    return sorted(
        d for d in CASES_DIR.iterdir()
        if d.is_dir() and (d / "expected.json").exists()
    )


def run_corpus(case_names: Optional[list[str]] = None) -> list[CaseResult]:
    """Run every case (or the named subset) in an isolated temp directory."""
    cases = discover_cases()
    if case_names:
        wanted = set(case_names)
        cases = [c for c in cases if c.name in wanted]
        unknown = wanted - {c.name for c in cases}
        if unknown:
            raise SystemExit(
                f"unknown case(s): {', '.join(sorted(unknown))}\n"
                f"available: {', '.join(c.name for c in discover_cases())}"
            )

    results = []
    with tempfile.TemporaryDirectory(prefix="doczot-corpus-") as tmp:
        tmp_root = Path(tmp)
        for case in cases:
            results.append(score_case(case, tmp_root))
    return results


# =============================================================================
# REPORTING
# =============================================================================

def format_report(results: list[CaseResult], verbose: bool = False) -> str:
    """Human-readable report, failures first and fully explained.

    Kept to ASCII: the default Windows console codepage is cp1252 and cannot
    encode box-drawing or check-mark characters.
    """
    lines: list[str] = []
    lines.append("=" * 74)
    lines.append("DocZot content-coverage accuracy corpus")
    lines.append("=" * 74)
    lines.append("")

    real_failures = [
        r for r in results if not r.passed and not r.known_failing
    ]
    known = [r for r in results if not r.passed and r.known_failing]
    passing = [r for r in results if r.passed]
    unexpected_pass = [r for r in results if r.passed and r.known_failing]

    for r in results:
        if r.passed and r.known_failing:
            status = "XPASS"
        elif r.passed:
            status = "PASS "
        elif r.known_failing:
            status = "XFAIL"
        else:
            status = "FAIL "
        pct = r.metrics.get("reported_coverage_percentage")
        pct_str = f"  coverage={pct}%" if pct is not None else ""
        lines.append(f"[{status}] {r.name}{pct_str}")

    lines.append("")

    if real_failures:
        lines.append("-" * 74)
        lines.append("FAILURES")
        lines.append("-" * 74)
        for r in real_failures:
            lines.append("")
            lines.append(f"### {r.name}")
            if r.description:
                lines.append(f"    {r.description}")
            if r.error:
                lines.append(f"    CRASHED: {r.error}")
            for c in r.failures:
                lines.append(f"    [x] {c.name}: {c.detail}")
                for m in c.missing:
                    lines.append(f"        missing:    {m}")
                for u in c.unexpected:
                    lines.append(f"        unexpected: {u}")
        lines.append("")

    if known:
        lines.append("-" * 74)
        lines.append("KNOWN FAILING (recorded gaps, not regressions)")
        lines.append("-" * 74)
        for r in known:
            lines.append(f"  {r.name}: {r.known_failing_reason}")
        lines.append("")

    if unexpected_pass:
        lines.append("-" * 74)
        lines.append("UNEXPECTEDLY PASSING — clear the known_failing flag")
        lines.append("-" * 74)
        for r in unexpected_pass:
            lines.append(f"  {r.name}")
        lines.append("")

    if verbose:
        lines.append("-" * 74)
        lines.append("METRICS")
        lines.append("-" * 74)
        for r in results:
            lines.append("")
            lines.append(f"### {r.name}")
            for c in r.checks:
                mark = "[ok]" if c.passed else "[x] "
                lines.append(f"    {mark} {c.name}: {c.detail}")
            for k, v in r.metrics.items():
                lines.append(f"    -  {k}: {json.dumps(v, default=str)}")
        lines.append("")

    lines.append("=" * 74)
    lines.append(
        f"{len(passing)} passed, {len(real_failures)} failed, "
        f"{len(known)} known-failing, {len(unexpected_pass)} unexpectedly passing"
    )

    graded = [
        r for r in results
        if "classification" in r.metrics and not r.known_failing
    ]
    if graded:
        f1s = [r.metrics["classification"]["f1"] for r in graded]
        fps = sum(
            r.metrics["classification"]["false_positives"] for r in graded
        )
        fns = sum(
            r.metrics["classification"]["false_negatives"] for r in graded
        )
        lines.append(
            f"endpoint coverage classification: mean F1="
            f"{round(sum(f1s) / len(f1s), 3)}, "
            f"{fps} invented coverage, {fns} missed coverage"
        )
    lines.append("=" * 74)

    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the DocZot content-coverage accuracy corpus."
    )
    parser.add_argument(
        "--case", action="append", dest="cases",
        help="Run only this case (repeatable).",
    )
    parser.add_argument(
        "--json", dest="json_path",
        help="Also write a machine-readable report to this path.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Include all checks and metrics, not just failures.",
    )
    args = parser.parse_args(argv)

    results = run_corpus(args.cases)
    print(format_report(results, verbose=args.verbose))

    if args.json_path:
        Path(args.json_path).write_text(
            json.dumps([r.to_dict() for r in results], indent=2, default=str),
            encoding="utf-8",
        )
        print(f"\nwrote {args.json_path}")

    real_failures = [r for r in results if not r.passed and not r.known_failing]
    return 1 if real_failures else 0


if __name__ == "__main__":
    sys.exit(main())
