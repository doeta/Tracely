"""Application-facing orchestration service."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .analysis import (
    analyze_exercise_1115,
    analyze_exercise_1118,
    analyze_exercise_1122,
    analyze_exercise_117,
    analyze_fast_slow_cases,
    build_overview,
    build_simple_dfg,
    cycle_time_by_case,
    run_generic_filter,
)
from .exporter import export_results_csv, export_results_pdf
from .models import AnalysisResult, DatasetOverview, FastSlowComparison
from .xes_loader import read_xes_dataframe


def _search_from_cached(cycle_times: pd.DataFrame, query: str, limit: int):
    if limit < 1:
        raise ValueError("limit harus lebih besar dari nol.")
    selected = cycle_times
    normalized_query = query.strip().casefold()
    if normalized_query:
        selected = cycle_times.loc[
            cycle_times["case_id"].astype(str).str.casefold().str.contains(
                normalized_query, regex=False
            )
        ]
    return [
        {
            "case_id": str(row.case_id),
            "event_count": int(getattr(row, "event_count", 0)),
            "start_time": row.start_time.isoformat(),
            "end_time": row.end_time.isoformat(),
            "cycle_time_days": float(row.cycle_time_days),
        }
        for row in selected.head(limit).itertuples()
    ]


class AnalysisService:
    """Keeps the active normalized event log and exposes assignment analyses."""

    def __init__(self) -> None:
        self._data: pd.DataFrame | None = None
        self._source_path: Path | None = None
        self._cycle_times: pd.DataFrame | None = None

    @property
    def is_loaded(self) -> bool:
        return self._data is not None

    @property
    def source_path(self) -> Path | None:
        return self._source_path

    @property
    def data(self) -> pd.DataFrame:
        if self._data is None:
            raise RuntimeError("Belum ada event log yang dimuat.")
        return self._data

    def load_xes(self, path: str | Path) -> DatasetOverview:
        loaded = read_xes_dataframe(path)
        cycle_times = cycle_time_by_case(loaded)
        overview = build_overview(loaded, cycle_times)
        self._data = loaded
        self._cycle_times = cycle_times
        self._source_path = Path(path).expanduser().resolve()
        return overview

    def set_dataframe_for_testing(self, data: pd.DataFrame) -> DatasetOverview:
        """Inject normalized data for tests and synthetic demonstrations."""
        from .event_log import normalize_event_log
        loaded = normalize_event_log(data)
        cycle_times = cycle_time_by_case(loaded)
        overview = build_overview(loaded, cycle_times)
        self._data = loaded
        self._cycle_times = cycle_times
        self._source_path = None
        return overview

    def overview(self) -> DatasetOverview:
        return build_overview(self.data, self._cycle_times)

    def search_case_durations(self, query: str = "", limit: int = 500):
        if self._cycle_times is None:
            self._cycle_times = cycle_time_by_case(self.data)
        # Reuse cached durations rather than grouping a large event log on every search.
        return _search_from_cached(self._cycle_times, query, limit)

    def run_117(
        self,
        accepted_activity: str = "O_Accepted",
        refused_activity: str = "O_Refused",
        cancelled_activity: str = "O_Cancelled",
    ) -> dict[str, AnalysisResult]:
        return analyze_exercise_117(
            self.data,
            accepted_activity=accepted_activity,
            refused_activity=refused_activity,
            cancelled_activity=cancelled_activity,
        )

    def run_1115(
        self,
        target_activity: str = "W_Assess Potential Fraud",
        min_occurrences: int = 2,
        target_lifecycle: str = "complete",
    ) -> AnalysisResult:
        return analyze_exercise_1115(
            self.data,
            target_activity=target_activity,
            min_occurrences=min_occurrences,
            target_lifecycle=target_lifecycle,
        )

    def run_1118(
        self,
        target_activity: str = "W_Assess Potential Fraud",
        min_occurrences: int = 2,
        target_lifecycle: str = "complete",
    ) -> AnalysisResult:
        return analyze_exercise_1118(
            self.data,
            target_activity=target_activity,
            min_occurrences=min_occurrences,
            target_lifecycle=target_lifecycle,
        )

    def run_1122(
        self,
        first_activity: str = "O_Cancelled",
        second_activity: str = "O_Accepted",
    ) -> AnalysisResult:
        return analyze_exercise_1122(
            self.data,
            first_activity=first_activity,
            second_activity=second_activity,
        )

    def run_all_required(self) -> list[AnalysisResult]:
        """Run all required analyses; complete-only tasks require lifecycle data."""
        results: list[AnalysisResult] = list(self.run_117().values())
        results.append(self.run_1115())
        results.append(self.run_1118())
        results.append(self.run_1122())
        return results

    def export(self, output_dir: str | Path, results: list[AnalysisResult]):
        return export_results_csv(results, output_dir)

    def export_pdf(
        self,
        output_path: str | Path,
        results: list[AnalysisResult],
        fast_slow: FastSlowComparison | None = None,
    ) -> Path:
        ov = self.overview() if self.is_loaded else None
        return export_results_pdf(
            results=results,
            output_path=output_path,
            overview=ov,
            source_path=self._source_path,
            fast_slow=fast_slow,
        )

    def run_fast_slow(self, threshold_days: float = 45.0) -> FastSlowComparison:
        if self._cycle_times is None:
            self._cycle_times = cycle_time_by_case(self.data)
        return analyze_fast_slow_cases(self.data, threshold_days=threshold_days, cycle_times=self._cycle_times)

    def run_custom_filter(
        self,
        filter_type: str,
        activity_a: str,
        activity_b: str = "",
        min_count: int = 2,
        lifecycle_filter: str = "",
        endpoint_position: str = "end",
    ) -> AnalysisResult:
        if self._cycle_times is None:
            self._cycle_times = cycle_time_by_case(self.data)
        return run_generic_filter(
            self.data,
            filter_type=filter_type,
            activity_a=activity_a,
            activity_b=activity_b,
            min_count=min_count,
            lifecycle_filter=lifecycle_filter,
            endpoint_position=endpoint_position,
            cycle_times=self._cycle_times,
        )

    def run_simple_dfg(self, top_n: int = 25, include_self_loops: bool = False) -> list[dict]:
        return build_simple_dfg(self.data, top_n=top_n, include_self_loops=include_self_loops)

    def get_cycle_times_df(self) -> pd.DataFrame:
        if self._cycle_times is None:
            self._cycle_times = cycle_time_by_case(self.data)
        return self._cycle_times

