from __future__ import annotations

import sys
import types

import pandas as pd
import pytest

from tracely.exceptions import DatasetLoadError
from tracely.xes_loader import read_xes_dataframe


def test_xes_loader_calls_pm4py_and_normalizes_dataframe(tmp_path, monkeypatch):
    source = pd.DataFrame({
        "case:concept:name": ["C1", "C1"],
        "concept:name": ["A", "B"],
        "time:timestamp": ["2026-01-01T08:00:00Z", "2026-01-01T09:00:00Z"],
    })
    calls = {}

    def fake_read_xes(path, return_legacy_log_object=False):
        calls["path"] = path
        calls["legacy"] = return_legacy_log_object
        return source

    fake_pm4py = types.SimpleNamespace(read_xes=fake_read_xes)
    monkeypatch.setitem(sys.modules, "pm4py", fake_pm4py)
    xes_file = tmp_path / "synthetic.xes"
    xes_file.write_text("<log />", encoding="utf-8")

    result = read_xes_dataframe(xes_file)

    assert calls["path"] == str(xes_file.resolve())
    assert calls["legacy"] is False
    assert result["activity"].tolist() == ["A", "B"]
    assert result["case_id"].tolist() == ["C1", "C1"]


def test_xes_loader_rejects_non_xes_file(tmp_path):
    file_path = tmp_path / "events.csv"
    file_path.write_text("case,activity,timestamp\n", encoding="utf-8")
    with pytest.raises(DatasetLoadError, match="ekstensi .xes"):
        read_xes_dataframe(file_path)


def test_xes_loader_accepts_xes_gz_file(tmp_path, monkeypatch):
    source = pd.DataFrame({
        "case:concept:name": ["C1"],
        "concept:name": ["A"],
        "time:timestamp": ["2026-01-01T08:00:00Z"],
    })
    fake_pm4py = types.SimpleNamespace(read_xes=lambda path, return_legacy_log_object=False: source)
    monkeypatch.setitem(sys.modules, "pm4py", fake_pm4py)
    gz_file = tmp_path / "bpic17.xes.gz"
    gz_file.write_bytes(b"fake-gzip")

    result = read_xes_dataframe(gz_file)
    assert result["case_id"].tolist() == ["C1"]



def test_synthetic_xes_example_is_well_formed():
    import xml.etree.ElementTree as ET
    from pathlib import Path

    example = Path(__file__).parents[1] / "examples" / "synthetic_bpic17_demo.xes"
    root = ET.parse(example).getroot()
    assert root.tag == "log"
    traces = root.findall("trace")
    assert len(traces) == 4
    assert all(trace.findall("event") for trace in traces)
