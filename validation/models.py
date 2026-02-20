"""Pydantic models for the DocZot validation framework.

Defines the data structures for validation results, reports, and
human-in-the-loop tasks.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, Any

from pydantic import BaseModel, Field


class ValidationDimension(str, Enum):
    """Dimensions along which DocZot validates its own outputs."""
    GRAPH_CONSISTENCY = "graph_consistency"
    SURFACE_COMPLETENESS = "surface_completeness"
    MAP_ACCURACY = "map_accuracy"
    MATCH_QUALITY = "match_quality"
    CROSS_LAYER = "cross_layer"
    REACHABILITY = "reachability"
    DETERMINISM = "determinism"
    STALENESS = "staleness"
    FINOPS = "finops"


class ValidationStatus(str, Enum):
    """Outcome of a validation check."""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIPPED = "skipped"


class CheckResult(BaseModel):
    """Result of a single validation check.

    Each check has a name, belongs to a dimension, and produces a
    status with a human-readable message and optional details.
    """
    name: str
    dimension: ValidationDimension
    status: ValidationStatus
    message: str
    details: list[str] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=datetime.now)


class ValidationReport(BaseModel):
    """Aggregated results from running one or more validation checks.

    Provides per-dimension status summaries and overall counts.
    """
    product_name: str
    scan_id: Optional[str] = None
    checked_at: datetime = Field(default_factory=datetime.now)
    results: list[CheckResult] = Field(default_factory=list)

    def status_by_dimension(self) -> dict[ValidationDimension, ValidationStatus]:
        """Aggregate status per dimension (worst status wins)."""
        severity = {
            ValidationStatus.FAIL: 3,
            ValidationStatus.WARN: 2,
            ValidationStatus.PASS: 1,
            ValidationStatus.SKIPPED: 0,
        }
        dims: dict[ValidationDimension, ValidationStatus] = {}
        for result in self.results:
            current = dims.get(result.dimension, ValidationStatus.SKIPPED)
            if severity[result.status] > severity[current]:
                dims[result.dimension] = result.status
        return dims

    def summary(self) -> dict[str, int]:
        """Count results by status."""
        counts = {"pass": 0, "warn": 0, "fail": 0, "skipped": 0}
        for result in self.results:
            counts[result.status.value] += 1
        return counts

    def is_healthy(self) -> bool:
        """True if no checks failed."""
        return all(r.status != ValidationStatus.FAIL for r in self.results)


class HumanTask(BaseModel):
    """A bite-sized validation task for human review.

    Designed to be completable in 5-10 minutes without deep context.
    """
    id: str
    task_type: str  # "spot_check", "match_review", "path_walk", "claim_check"
    prompt: str
    context: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"  # pending, completed, skipped
    answer: Optional[str] = None
    notes: Optional[str] = None
    answered_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
