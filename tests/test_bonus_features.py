from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from bpic17_analyzer.analysis import (
    analyze_fast_slow_cases,
    build_simple_dfg,
    run_generic_filter,
)
from bpic17_analyzer.event_log import normalize_event_log
from bpic17_analyzer.exporter import export_results_pdf


def test_fast_slow_cases_analysis_splits_and_compares():
    # C1 spans 10 days (Fast < 45), C2 spans 60 days (Slow >= 45)
    source = pd.DataFrame({
        "case:concept:name": ["C1", "C1", "C2", "C2"],
        "concept:name": ["A_Start", "O_Accepted", "A_Start", "O_Cancelled"],
        "time:timestamp": [
            "2026-01-01T00:00:00Z",
            "2026-01-11T00:00:00Z",
            "2026-01-01T00:00:00Z",
            "2026-03-02T00:00:00Z",
        ],
    })
    normalized = normalize_event_log(source)
    comp = analyze_fast_slow_cases(normalized, threshold_days=45.0)

    assert comp.fast_result.case_ids == ["C1"]
    assert comp.fast_result.count == 1
    assert comp.fast_result.percentage == 50.0
    assert comp.fast_result.mean_cycle_time_days == 10.0

    assert comp.slow_result.case_ids == ["C2"]
    assert comp.slow_result.count == 1
    assert comp.slow_result.percentage == 50.0
    assert comp.slow_result.mean_cycle_time_days == 60.0
    assert len(comp.comparison_metrics) >= 5


def test_generic_filter_supports_all_five_modes(sample_log):
    res_contains = run_generic_filter(sample_log, "contains", "O_Accepted")
    assert res_contains.case_ids == ["C1", "C2", "C3"]

    res_endpoint_end = run_generic_filter(
        sample_log, "endpoint", "O_Cancelled", endpoint_position="end"
    )
    assert res_endpoint_end.case_ids == ["C2"]

    res_min_occ = run_generic_filter(
        sample_log,
        "minimum_occurrence",
        "W_Assess Potential Fraud",
        min_count=2,
        lifecycle_filter="complete",
    )
    assert set(res_min_occ.case_ids) == {"C1", "C2"}

    res_same_res = run_generic_filter(
        sample_log,
        "same_resource",
        "W_Assess Potential Fraud",
        min_count=2,
        lifecycle_filter="complete",
    )
    assert res_same_res.case_ids == ["C1"]

    res_follows = run_generic_filter(
        sample_log,
        "eventually_follows",
        "O_Cancelled",
        activity_b="O_Accepted",
    )
    assert res_follows.case_ids == ["C1"]


def test_simple_dfg_counts_adjacent_pairs_without_process_discovery(sample_log):
    edges = build_simple_dfg(sample_log, top_n=10)
    assert len(edges) > 0
    assert all(
        {"source_activity", "target_activity", "frequency", "mean_hours"} <= set(edge.keys())
        for edge in edges
    )


def test_export_results_pdf_writes_valid_pdf_file(sample_log, tmp_path):
    from bpic17_analyzer.service import AnalysisService

    svc = AnalysisService()
    svc.set_dataframe_for_testing(sample_log)
    results = svc.run_all_required()
    fs = svc.run_fast_slow(threshold_days=45.0)

    pdf_file = tmp_path / "report.pdf"
    saved_path = export_results_pdf(
        results=results,
        output_path=pdf_file,
        overview=svc.overview(),
        fast_slow=fs,
    )
    assert Path(saved_path).exists()
    assert Path(saved_path).stat().st_size > 500
    assert Path(saved_path).read_bytes().startswith(b"%PDF")


def test_general_purpose_non_bpic17_event_log_analysis():
    """Verify the engine works on any non-BPIC17 XES event log (e.g. e-commerce / hospital)."""
    from bpic17_analyzer.analysis import (
        analyze_exercise_117,
        analyze_exercise_1115,
        analyze_exercise_1118,
        analyze_exercise_1122,
    )

    source = pd.DataFrame({
        "case:concept:name": ["ORD-1", "ORD-1", "ORD-1", "ORD-1", "ORD-2", "ORD-2"],
        "concept:name": [
            "Payment_Hold",
            "Quality_Check",
            "Quality_Check",
            "Order_Shipped",
            "Order_Rejected",
            "Order_Aborted",
        ],
        "time:timestamp": [
            "2026-02-01T08:00:00Z",
            "2026-02-01T09:00:00Z",
            "2026-02-01T10:00:00Z",
            "2026-02-02T08:00:00Z",
            "2026-02-03T08:00:00Z",
            "2026-02-04T08:00:00Z",
        ],
        "lifecycle:transition": ["complete"] * 6,
        "org:resource": ["Inspector_A", "Inspector_A", "Inspector_A", "System", "System", "User"],
    })
    log = normalize_event_log(source)

    outcomes = analyze_exercise_117(
        log,
        accepted_activity="Order_Shipped",
        refused_activity="Order_Rejected",
        cancelled_activity="Order_Aborted",
    )
    assert outcomes["11.7A"].count == 2
    assert outcomes["11.7C"].case_ids == ["ORD-1"]
    assert outcomes["11.7D"].case_ids == ["ORD-2"]
    assert outcomes["11.7E"].case_ids == ["ORD-2"]

    rework = analyze_exercise_1115(log, target_activity="Quality_Check", min_occurrences=2)
    assert rework.case_ids == ["ORD-1"]

    same_res = analyze_exercise_1118(log, target_activity="Quality_Check", min_occurrences=2)
    assert same_res.case_ids == ["ORD-1"]
    assert same_res.evidence[0]["resource"] == "Inspector_A"

    seq = analyze_exercise_1122(log, first_activity="Payment_Hold", second_activity="Order_Shipped")
    assert seq.case_ids == ["ORD-1"]
    assert seq.percentage == 50.0

