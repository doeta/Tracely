from __future__ import annotations

import pandas as pd
import pytest

from tracely.analysis import analyze_exercise_1115, analyze_exercise_1118
from tracely.event_log import normalize_event_log
from tracely.exceptions import AnalysisPrerequisiteError


def test_1115_counts_only_complete_occurrences(sample_log):
    result = analyze_exercise_1115(sample_log)
    assert set(result.case_ids) == {"C1", "C2"}
    assert result.count == 2

    c1 = next(item for item in result.evidence if item["case_id"] == "C1")
    assert c1["complete_occurrence_count"] == 3
    assert all(event["lifecycle"] == "complete" for event in c1["events"])


def test_1118_requires_same_known_resource(sample_log):
    result = analyze_exercise_1118(sample_log)
    assert result.case_ids == ["C1"]
    assert result.count == 1
    assert result.evidence[0]["resource"] == "Alice"
    assert result.evidence[0]["complete_occurrence_count"] == 2


def test_missing_resource_is_not_treated_as_same_resource():
    source = pd.DataFrame({
        "case:concept:name": ["C1", "C1"],
        "concept:name": ["W_Assess Potential Fraud"] * 2,
        "time:timestamp": ["2026-01-01", "2026-01-02"],
        "lifecycle:transition": ["complete", "complete"],
        "org:resource": [None, None],
    })
    normalized = normalize_event_log(source)
    result = analyze_exercise_1118(normalized)
    assert result.count == 0


def test_complete_only_analysis_requires_lifecycle_attribute():
    source = pd.DataFrame({
        "case_id": ["C1", "C1"],
        "activity": ["W_Assess Potential Fraud"] * 2,
        "timestamp": ["2026-01-01", "2026-01-02"],
    })
    normalized = normalize_event_log(source)
    with pytest.raises(AnalysisPrerequisiteError, match="lifecycle"):
        analyze_exercise_1115(normalized)


def test_1118_fails_clearly_when_resource_attribute_is_absent():
    source = pd.DataFrame({
        "case:concept:name": ["C1", "C1"],
        "concept:name": ["W_Assess Potential Fraud"] * 2,
        "time:timestamp": ["2026-01-01", "2026-01-02"],
        "lifecycle:transition": ["complete", "complete"],
    })
    normalized = normalize_event_log(source)
    with pytest.raises(AnalysisPrerequisiteError, match="org:resource"):
        analyze_exercise_1118(normalized)


def test_1115_fails_if_target_event_has_missing_lifecycle():
    source = pd.DataFrame({
        "case:concept:name": ["C1", "C1"],
        "concept:name": ["W_Assess Potential Fraud"] * 2,
        "time:timestamp": ["2026-01-01", "2026-01-02"],
        "lifecycle:transition": ["complete", None],
        "org:resource": ["Alice", "Alice"],
    })
    normalized = normalize_event_log(source)
    with pytest.raises(AnalysisPrerequisiteError, match="tanpa lifecycle"):
        analyze_exercise_1115(normalized)


def test_1118_counts_case_once_if_multiple_resources_qualify():
    source = pd.DataFrame({
        "case:concept:name": ["C1"] * 4,
        "concept:name": ["W_Assess Potential Fraud"] * 4,
        "time:timestamp": [
            "2026-01-01T08:00:00Z", "2026-01-01T09:00:00Z",
            "2026-01-01T10:00:00Z", "2026-01-01T11:00:00Z",
        ],
        "lifecycle:transition": ["complete"] * 4,
        "org:resource": ["Alice", "Alice", "Bob", "Bob"],
    })
    normalized = normalize_event_log(source)
    result = analyze_exercise_1118(normalized)
    assert result.count == 1
    assert result.case_ids == ["C1"]
    assert len(result.evidence) == 2


def test_1115_fails_if_target_event_has_empty_string_lifecycle():
    source = pd.DataFrame({
        "case:concept:name": ["C1", "C1"],
        "concept:name": ["W_Assess Potential Fraud"] * 2,
        "time:timestamp": ["2026-01-01T08:00:00Z", "2026-01-01T09:00:00Z"],
        "lifecycle:transition": ["complete", "   "],
        "org:resource": ["Alice", "Alice"],
    })
    normalized = normalize_event_log(source)
    with pytest.raises(AnalysisPrerequisiteError, match="tanpa lifecycle"):
        analyze_exercise_1115(normalized)


def test_1115_and_1118_match_complete_lifecycle_case_insensitively():
    source = pd.DataFrame({
        "case:concept:name": ["C1", "C1", "C1"],
        "concept:name": ["W_Assess Potential Fraud"] * 3,
        "time:timestamp": [
            "2026-01-01T08:00:00Z",
            "2026-01-01T09:00:00Z",
            "2026-01-01T10:00:00Z",
        ],
        "lifecycle:transition": ["COMPLETE", "Complete", "schedule"],
        "org:resource": ["User_1", "User_1", "User_1"],
    })
    normalized = normalize_event_log(source)
    res_1115 = analyze_exercise_1115(normalized)
    res_1118 = analyze_exercise_1118(normalized)
    assert res_1115.case_ids == ["C1"]
    assert res_1115.evidence[0]["complete_occurrence_count"] == 2
    assert res_1118.case_ids == ["C1"]
    assert res_1118.evidence[0]["complete_occurrence_count"] == 2


def test_1118_fails_when_resource_column_is_absent_even_if_zero_target_events():
    source = pd.DataFrame({
        "case:concept:name": ["C1"],
        "concept:name": ["O_Accepted"],
        "time:timestamp": ["2026-01-01T08:00:00Z"],
        "lifecycle:transition": ["complete"],
    })
    normalized = normalize_event_log(source)
    with pytest.raises(AnalysisPrerequisiteError, match="org:resource"):
        analyze_exercise_1118(normalized)


def test_1115_and_1118_match_official_bpic17_lowercase_fraud_activity_spelling():
    source = pd.DataFrame({
        "case:concept:name": ["C1", "C1"],
        "concept:name": ["W_Assess potential fraud", "W_Assess potential fraud"],
        "time:timestamp": ["2026-01-01T08:00:00Z", "2026-01-01T09:00:00Z"],
        "lifecycle:transition": ["complete", "complete"],
        "org:resource": ["User_10", "User_10"],
    })
    normalized = normalize_event_log(source)
    assert analyze_exercise_1115(normalized).case_ids == ["C1"]
    assert analyze_exercise_1118(normalized).case_ids == ["C1"]


