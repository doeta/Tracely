from __future__ import annotations

from bpic17_analyzer.analysis import analyze_exercise_117, cycle_time_by_case


def test_cycle_time_uses_first_and_last_timestamp(sample_log):
    result = cycle_time_by_case(sample_log).set_index("case_id")
    # C3 spans exactly 24 hours.
    assert result.loc["C3", "cycle_time_days"] == 1.0
    # C1 runs from 08:00 to 15:00: seven hours.
    assert round(result.loc["C1", "cycle_time_days"] * 24, 6) == 7.0


def test_exercise_117_case_level_rules(sample_log):
    results = analyze_exercise_117(sample_log)

    assert results["11.7A"].count == 4
    assert results["11.7B"].count == 4
    assert results["11.7C"].case_ids == ["C1", "C2", "C3"]
    assert results["11.7D"].case_ids == ["C2", "C3"]
    assert results["11.7E"].case_ids == ["C2"]


def test_success_and_refused_groups_may_overlap(sample_log):
    results = analyze_exercise_117(sample_log)
    assert "C2" in results["11.7C"].case_ids
    assert "C2" in results["11.7D"].case_ids


def test_cancelled_event_must_be_the_last_event(sample_log):
    results = analyze_exercise_117(sample_log)
    assert "C4" not in results["11.7E"].case_ids


def test_117_contains_filters_count_a_case_once_even_when_activity_repeats():
    import pandas as pd
    from bpic17_analyzer.event_log import normalize_event_log

    source = pd.DataFrame({
        "case:concept:name": ["C1", "C1", "C1", "C1"],
        "concept:name": ["O_Accepted", "O_Accepted", "O_Refused", "O_Refused"],
        "time:timestamp": [
            "2026-01-01T08:00:00Z", "2026-01-01T09:00:00Z",
            "2026-01-01T10:00:00Z", "2026-01-01T11:00:00Z",
        ],
    })
    results = analyze_exercise_117(normalize_event_log(source))
    assert results["11.7C"].count == 1
    assert results["11.7D"].count == 1
    assert results["11.7C"].evidence[0]["occurrence_count"] == 2
    assert results["11.7D"].evidence[0]["occurrence_count"] == 2


def test_117_cycle_time_uses_full_original_trace_not_only_target_events():
    import pandas as pd
    from bpic17_analyzer.event_log import normalize_event_log

    # Case C1 starts at day 1 (A_Create), has O_Accepted on day 2, and ends on day 4 (W_Close).
    # Full trace duration must be 3.0 days, not 0.0 days (from O_Accepted alone).
    source = pd.DataFrame({
        "case:concept:name": ["C1", "C1", "C1"],
        "concept:name": ["A_Create", "O_Accepted", "W_Close"],
        "time:timestamp": [
            "2026-01-01T00:00:00Z",
            "2026-01-02T00:00:00Z",
            "2026-01-04T00:00:00Z",
        ],
    })
    results = analyze_exercise_117(normalize_event_log(source))
    assert results["11.7C"].mean_cycle_time_days == 3.0
    assert results["11.7C"].evidence[0]["cycle_time_days"] == 3.0


def test_117e_tie_breaker_preserves_source_order_when_timestamps_equal():
    import pandas as pd
    from bpic17_analyzer.event_log import normalize_event_log

    # C1 has O_Review then O_Cancelled at the exact same timestamp -> ends with O_Cancelled (qualifies)
    # C2 has O_Cancelled then O_Review at the exact same timestamp -> ends with O_Review (does not qualify)
    source = pd.DataFrame({
        "case:concept:name": ["C1", "C1", "C2", "C2"],
        "concept:name": ["O_Review", "O_Cancelled", "O_Cancelled", "O_Review"],
        "time:timestamp": [
            "2026-01-01T10:00:00Z",
            "2026-01-01T10:00:00Z",
            "2026-01-01T10:00:00Z",
            "2026-01-01T10:00:00Z",
        ],
    })
    results = analyze_exercise_117(normalize_event_log(source))
    assert results["11.7E"].case_ids == ["C1"]
    assert results["11.7E"].count == 1

