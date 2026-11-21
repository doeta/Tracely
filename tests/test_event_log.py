from __future__ import annotations

import pandas as pd
import pytest

from bpic17_analyzer.event_log import normalize_event_log
from bpic17_analyzer.exceptions import DatasetValidationError


def test_normalize_maps_xes_columns_and_sorts_stably():
    source = pd.DataFrame({
        "case:concept:name": ["B", "A", "A"],
        "concept:name": ["Second", "First", "Second"],
        "time:timestamp": [
            "2026-01-02T00:00:00Z",
            "2026-01-01T00:00:00Z",
            "2026-01-02T00:00:00Z",
        ],
    })

    result = normalize_event_log(source)

    assert list(result.columns) == [
        "case_id", "activity", "timestamp", "source_order", "lifecycle", "resource"
    ]
    assert result["case_id"].tolist() == ["A", "A", "B"]
    assert result["source_order"].tolist() == [1, 2, 0]


def test_missing_required_column_raises():
    source = pd.DataFrame({"case_id": ["C1"], "activity": ["A"]})
    with pytest.raises(DatasetValidationError, match="timestamp"):
        normalize_event_log(source)


def test_missing_required_values_are_not_silently_dropped():
    source = pd.DataFrame({
        "case_id": ["C1", None],
        "activity": ["A", "B"],
        "timestamp": ["2026-01-01", "2026-01-02"],
    })
    with pytest.raises(DatasetValidationError, match="case_id"):
        normalize_event_log(source)


def test_empty_event_log_raises():
    with pytest.raises(DatasetValidationError, match="kosong"):
        normalize_event_log(pd.DataFrame())


def test_resource_attribute_presence_is_recorded_even_when_values_are_empty():
    source = pd.DataFrame({
        "case:concept:name": ["C1"],
        "concept:name": ["A"],
        "time:timestamp": ["2026-01-01"],
        "org:resource": [None],
    })
    result = normalize_event_log(source)
    assert "resource" in result.attrs["available_attributes"]
    assert result["resource"].isna().all()


def test_missing_resource_attribute_is_not_reported_as_present():
    source = pd.DataFrame({
        "case:concept:name": ["C1"],
        "concept:name": ["A"],
        "time:timestamp": ["2026-01-01"],
    })
    result = normalize_event_log(source)
    assert "resource" not in result.attrs["available_attributes"]


def test_whitespace_lifecycle_and_resource_are_normalized_to_na():
    source = pd.DataFrame({
        "case:concept:name": ["C1", "C1"],
        "concept:name": ["A", "B"],
        "time:timestamp": ["2026-01-01T08:00:00Z", "2026-01-01T09:00:00Z"],
        "lifecycle:transition": ["   ", "complete"],
        "org:resource": ["", "   "],
    })
    result = normalize_event_log(source)
    assert pd.isna(result.loc[0, "lifecycle"])
    assert result.loc[1, "lifecycle"] == "complete"
    assert result["resource"].isna().all()

