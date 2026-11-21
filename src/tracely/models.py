"""Typed result models shared by analysis modules and the desktop UI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class AnalysisResult:
    """A case-level analysis result with traceable evidence."""

    code: str
    title: str
    rule: str
    count: int
    case_ids: list[str] = field(default_factory=list)
    denominator: int | None = None
    percentage: float | None = None
    mean_cycle_time_days: float | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly dictionary."""
        return asdict(self)


@dataclass(slots=True)
class DatasetOverview:
    """High-level statistics for the currently loaded event log."""

    total_cases: int
    total_events: int
    unique_activities: int
    first_timestamp: str | None
    last_timestamp: str | None
    mean_cycle_time_days: float | None
    activity_frequencies: list[dict[str, Any]]
    available_attributes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FastSlowComparison:
    """Comparison between fast cases (< threshold) and slow cases (>= threshold)."""

    threshold_days: float
    fast_result: AnalysisResult
    slow_result: AnalysisResult
    comparison_metrics: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

