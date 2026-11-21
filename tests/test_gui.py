from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from app.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_tracely_navigation_and_analysis_integration(qapp, sample_log, tmp_path):
    window = MainWindow()
    assert "Tracely" in window.windowTitle()
    assert window.nav_list.count() == 11
    assert not window.export_button.isEnabled()

    # Verify all 11 navigation pages can be visited and resized cleanly
    for page_idx in range(window.nav_list.count()):
        window.navigate_to(page_idx)
        assert window.pages.currentIndex() == page_idx

    # Test collapsible sidebar and contextual inspector panel toggle
    window.toggle_sidebar()
    assert window.sidebar_collapsed is True
    assert window.sidebar_frame.width() == 64
    window.toggle_sidebar()
    assert window.sidebar_collapsed is False
    assert window.sidebar_frame.width() == 240

    window.toggle_context_panel()
    assert window.context_panel.isHidden()
    window.toggle_context_panel()
    assert not window.context_panel.isHidden()

    # Verify TopBar and StatusBar maintain locked spatial heights
    assert window.findChild(object, "TopNavBar").height() == 62
    assert window.findChild(object, "StatusBarFrame").height() == 38

    # Load synthetic data through service and trigger UI update
    overview = window.service.set_dataframe_for_testing(sample_log)
    window._on_dataset_loaded(overview)

    assert window.dash_cases_val.text() == "4"
    assert window.activity_table.rowCount() == overview.unique_activities
    assert window.case_duration_table.rowCount() == 4
    # Verify Case Explorer includes Event Count column (5 columns total)
    assert window.case_duration_table.columnCount() == 5
    assert int(window.case_duration_table.item(0, 1).text()) > 0

    # Run all exercises and verify tables & trace inspector populate without altering results
    window._on_analysis_finished("11.7", window.service.run_117())
    window._on_analysis_finished("11.15", window.service.run_1115())
    window._on_analysis_finished("11.18", window.service.run_1118())
    window._on_analysis_finished("11.22", window.service.run_1122())
    window._on_fast_slow_finished(window.service.run_fast_slow(45.0))
    window._on_custom_filter_finished(
        window.service.run_custom_filter("contains", "O_Accepted")
    )
    window._on_simple_dfg_finished(window.service.run_simple_dfg(10))

    assert {
        "11.7A", "11.7B", "11.7C", "11.7D", "11.7E", "11.15", "11.18", "11.22",
        "11.10-FAST", "11.10-SLOW", "CUSTOM-CONTAINS",
    } <= set(window.latest_results.keys())
    assert window.dashboard_table.rowCount() == 11
    assert window.reports_table.rowCount() == 11
    assert window.result_tables["11.7"].rowCount() == 5
    assert window.result_tables["11.15"].rowCount() == 1
    assert window.result_tables["11.18"].rowCount() == 1
    assert window.result_tables["11.22"].rowCount() == 1
    assert window.fast_slow_table.rowCount() >= 5
    assert window.dfg_table.rowCount() > 0

    # Verify exercise trace table and contextual inspector populate when a matching case is selected
    assert window.case_list_tables["11.18"].rowCount() == 1
    assert window.trace_tables["11.18"].rowCount() > 0
    assert window.ctx_trace_table.rowCount() > 0

    # Verify Case Explorer selection loads full trace
    window.case_duration_table.selectRow(0)
    window._on_case_duration_selected()
    assert window.case_table.rowCount() > 0

    # Verify responsive resize across all required desktop resolutions (1280x720 to 1920x1080)
    for width, height in [
        (1280, 720),
        (1366, 768),
        (1440, 900),
        (1600, 900),
        (1920, 1080),
    ]:
        window.resize(width, height)
        qapp.processEvents()
        assert window.width() == width
        assert window.height() == height
        # Ensure sidebar and topbar never shift during resize
        assert window.sidebar_frame.width() == 240
        assert window.findChild(object, "TopNavBar").height() == 62

    # Verify table tooltips are populated for full-value access on elided cells
    for row in range(window.dashboard_table.rowCount()):
        for col in range(window.dashboard_table.columnCount()):
            cell = window.dashboard_table.item(row, col)
            assert cell is not None and bool(cell.toolTip())

    # Verify Academic Reference toggle switches labels cleanly without layout shift
    window.academic_toggle_btn.click()
    assert window.show_academic_refs is False
    window.academic_toggle_btn.click()
    assert window.show_academic_refs is True

    # Verify CSV and PDF export through service from UI results
    summary_csv, evidence_csv = window.service.export(
        tmp_path, list(window.latest_results.values())
    )
    pdf_path = window.service.export_pdf(
        tmp_path / "tracely_report.pdf",
        list(window.latest_results.values()),
        fast_slow=window.latest_fast_slow,
    )
    assert Path(summary_csv).exists()
    assert Path(evidence_csv).exists()
    assert Path(pdf_path).exists()
    window.close()
    window.deleteLater()
    qapp.processEvents()
