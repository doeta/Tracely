from __future__ import annotations

from tracely.service import AnalysisService


def test_service_runs_all_required_exercises(sample_log):
    service = AnalysisService()
    overview = service.set_dataframe_for_testing(sample_log)

    assert overview.total_cases == 4
    assert overview.total_events == len(sample_log)

    assert set(service.run_117()) == {"11.7A", "11.7B", "11.7C", "11.7D", "11.7E"}
    assert service.run_1115().code == "11.15"
    assert service.run_1118().code == "11.18"
    assert service.run_1122().code == "11.22"


def test_overview_lists_activity_frequency(sample_log):
    service = AnalysisService()
    overview = service.set_dataframe_for_testing(sample_log)
    frequencies = {item["activity"]: item["frequency"] for item in overview.activity_frequencies}
    assert frequencies["W_Assess Potential Fraud"] == 7
    assert frequencies["O_Cancelled"] == 3


def test_case_duration_search_returns_timestamp_and_duration(sample_log):
    service = AnalysisService()
    service.set_dataframe_for_testing(sample_log)
    results = service.search_case_durations("C3")
    assert len(results) == 1
    assert results[0]["case_id"] == "C3"
    assert results[0]["cycle_time_days"] == 1.0


def test_case_duration_search_limit_must_be_positive(sample_log):
    service = AnalysisService()
    service.set_dataframe_for_testing(sample_log)
    import pytest
    with pytest.raises(ValueError, match="limit"):
        service.search_case_durations("", limit=0)
