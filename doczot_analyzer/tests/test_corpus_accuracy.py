"""Accuracy regression tests driven by the hand-labeled corpus.

The rest of the suite checks mechanics — that functions return the shapes they
promise. These tests check judgment: given a repository whose documentation
state a human labeled, does DocZot reach the same conclusion?

Cases whose answer key sets ``known_failing`` are reported as xfail so a
recorded gap does not block the suite, while an unexpected pass tells us the
gap is closed and the flag should come off.

The corpus is slow (each case loads the embedding model), so the whole corpus
runs once per session via a module-scoped fixture.
"""

from __future__ import annotations

import pytest

from doczot_analyzer.tests.corpus._harness import (
    CaseResult,
    discover_cases,
    run_corpus,
)

CASE_NAMES = [c.name for c in discover_cases()]


@pytest.fixture(scope="module")
def corpus_results() -> dict[str, CaseResult]:
    """Run the whole corpus once and index results by case name."""
    return {r.name: r for r in run_corpus()}


@pytest.mark.parametrize("case_name", CASE_NAMES)
def test_case_matches_answer_key(
    case_name: str, corpus_results: dict[str, CaseResult]
) -> None:
    """Each corpus case must agree with its hand-written answer key."""
    result = corpus_results.get(case_name)
    assert result is not None, f"case {case_name} produced no result"

    if result.known_failing and not result.passed:
        pytest.xfail(result.known_failing_reason or "recorded known gap")

    if result.error:
        pytest.fail(f"{case_name} crashed during analysis: {result.error}")

    if result.failures:
        report = [f"{case_name} disagrees with its answer key:"]
        for check in result.failures:
            report.append(f"  [x] {check.name}: {check.detail}")
            for missing in check.missing:
                report.append(f"      missing:    {missing}")
            for unexpected in check.unexpected:
                report.append(f"      unexpected: {unexpected}")
        pytest.fail("\n".join(report))


def test_corpus_is_not_empty() -> None:
    """Guard against the corpus silently disappearing."""
    assert CASE_NAMES, "no corpus cases discovered"


def test_no_invented_coverage(corpus_results: dict[str, CaseResult]) -> None:
    """No case may credit an undocumented endpoint as covered.

    False positives are the worst failure mode for this tool: a gap report that
    stays quiet about undocumented endpoints is worse than no report, because
    it is trusted.
    """
    offenders = []
    for name, result in sorted(corpus_results.items()):
        if result.known_failing:
            continue
        metrics = result.metrics.get("classification")
        if metrics and metrics["false_positives"]:
            offenders.append(
                f"{name}: {metrics['false_positives']} endpoint(s) "
                f"credited as documented but labeled undocumented"
            )
    assert not offenders, "\n".join(offenders)


def test_inventory_stays_inside_repo(
    corpus_results: dict[str, CaseResult]
) -> None:
    """Documentation credited as coverage must live in the analyzed repo.

    Regression guard for the git-root walk in discover_content_inventory(),
    which harvests markdown from every ancestor directory up to the enclosing
    git root and will otherwise credit an unrelated parent project's docs.
    """
    offenders = []
    for name, result in sorted(corpus_results.items()):
        for check in result.checks:
            if check.name == "inventory_containment" and not check.passed:
                offenders.append(f"{name}: {check.detail}")
                offenders.extend(f"    {u}" for u in check.unexpected)
    assert not offenders, "\n".join(offenders)
