from __future__ import annotations

import pandas as pd

from bpic17_analyzer.analysis import analyze_exercise_1122
from bpic17_analyzer.event_log import normalize_event_log


def test_1122_detects_eventually_follows_not_only_adjacent(sample_log):
    result = analyze_exercise_1122(sample_log)
    assert result.case_ids == ["C1"]
    assert result.count == 1
    assert result.denominator == 4
    assert result.percentage == 25.0
    assert result.evidence[0]["intervening_events"] >= 1


def test_1122_does_not_match_when_accept_precedes_cancel():
    source = pd.DataFrame({
        "case:concept:name": ["C1", "C1"],
        "concept:name": ["O_Accepted", "O_Cancelled"],
        "time:timestamp": ["2026-01-01T08:00:00Z", "2026-01-01T09:00:00Z"],
    })
    result = analyze_exercise_1122(normalize_event_log(source))
    assert result.count == 0
    assert result.percentage == 0.0


def test_1122_denominator_is_all_cases():
    source = pd.DataFrame({
        "case:concept:name": ["C1", "C1", "C2"],
        "concept:name": ["O_Cancelled", "O_Accepted", "O_Submitted"],
        "time:timestamp": [
            "2026-01-01T08:00:00Z",
            "2026-01-01T09:00:00Z",
            "2026-01-01T10:00:00Z",
        ],
    })
    result = analyze_exercise_1122(normalize_event_log(source))
    assert result.count == 1
    assert result.denominator == 2
    assert result.percentage == 50.0


def test_1122_counts_one_case_once_when_multiple_ordered_pairs_exist():
    source = pd.DataFrame({
        "case:concept:name": ["C1"] * 4,
        "concept:name": ["O_Cancelled", "O_Accepted", "O_Cancelled", "O_Accepted"],
        "time:timestamp": [
            "2026-01-01T08:00:00Z", "2026-01-01T09:00:00Z",
            "2026-01-01T10:00:00Z", "2026-01-01T11:00:00Z",
        ],
    })
    result = analyze_exercise_1122(normalize_event_log(source))
    assert result.count == 1
    assert result.case_ids == ["C1"]


def test_1122_respects_source_order_when_timestamps_are_identical():
    source = pd.DataFrame({
        "case:concept:name": ["C1", "C1", "C2", "C2"],
        "concept:name": ["O_Cancelled", "O_Accepted", "O_Accepted", "O_Cancelled"],
        "time:timestamp": [
            "2026-01-01T10:00:00Z",
            "2026-01-01T10:00:00Z",
            "2026-01-01T10:00:00Z",
            "2026-01-01T10:00:00Z",
        ],
    })
    result = analyze_exercise_1122(normalize_event_log(source))
    assert result.case_ids == ["C1"]
    assert result.count == 1
    assert result.denominator == 2
    assert result.percentage == 50.0

