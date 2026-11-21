from __future__ import annotations

import csv

from tracely.analysis import analyze_exercise_1122, analyze_exercise_117
from tracely.exporter import export_results_csv


def test_export_writes_summary_and_case_evidence(sample_log, tmp_path):
    results = list(analyze_exercise_117(sample_log).values())
    results.append(analyze_exercise_1122(sample_log))
    summary_path, evidence_path = export_results_csv(results, tmp_path)

    assert summary_path.exists()
    assert evidence_path.exists()

    with summary_path.open(encoding="utf-8-sig", newline="") as handle:
        summary_rows = list(csv.DictReader(handle))
    assert len(summary_rows) == 6
    assert any(row["code"] == "11.7B" for row in summary_rows)

    with evidence_path.open(encoding="utf-8-sig", newline="") as handle:
        evidence_rows = list(csv.DictReader(handle))
    assert any(row["analysis_code"] == "11.22" and row["case_id"] == "C1" for row in evidence_rows)
