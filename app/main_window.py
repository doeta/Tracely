"""Tracely — Professional Neubrutalist Process Mining Desktop Application."""

from __future__ import annotations

import json
import math
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Callable

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import FancyArrowPatch
import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bpic17_analyzer.analysis import get_case_events
from bpic17_analyzer.models import AnalysisResult, DatasetOverview, FastSlowComparison
from bpic17_analyzer.service import AnalysisService
from .dfg_canvas import DfgInteractiveCanvas
from .theme import (
    BTN_HEIGHT_COMPACT,
    BTN_HEIGHT_STANDARD,
    BTN_ICON_SIZE,
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_BORDER,
    COLOR_DANGER,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    SIDEBAR_WIDTH_COLLAPSED,
    SIDEBAR_WIDTH_EXPANDED,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    STATUSBAR_HEIGHT,
    TOPBAR_HEIGHT,
    apply_hard_shadow,
    autofit_table_columns,
    build_global_stylesheet,
    make_button,
    make_kpi_card,
    make_neubrutal_card,
    make_ref_badge,
    make_table,
    set_kpi_value,
)
from .worker import TaskWorker

MAX_EVIDENCE_PREVIEW = 100
MAX_CASE_LIST_PREVIEW = 500

# Clean SaaS display names for analytical result codes (no textbook exercise numbers in UI)
MODULE_DISPLAY_NAMES: dict[str, str] = {
    "11.7A": "Total Case Volume",
    "11.7B": "Overall Cycle Time",
    "11.7C": "Positive Outcome Cohort",
    "11.7D": "Negative Outcome Cohort",
    "11.7E": "Terminal Cancellation Cohort",
    "11.15": "Repeated Activity Rework",
    "11.18": "Same-Resource Rework",
    "11.22": "Eventually-Follows Sequence",
    "11.10-FAST": "Fast Throughput Segment",
    "11.10-SLOW": "Slow Throughput Segment",
}


class _NavListProxy:
    """Compatibility proxy so existing tests or callers can query nav_list.count() / setCurrentRow()."""

    def __init__(self, window: "MainWindow") -> None:
        self._window = window

    def count(self) -> int:
        return len(self._window.nav_buttons)

    def currentRow(self) -> int:
        return self._window.pages.currentIndex()

    def setCurrentRow(self, index: int) -> None:
        self._window.navigate_to(index)


class MainWindow(QMainWindow):
    """Tracely Desktop Process Intelligence Workspace."""

    PAGE_OVERVIEW = 0
    PAGE_PROJECTS = 1
    PAGE_EVENT_LOGS = 2
    PAGE_OUTCOMES = 3
    PAGE_REWORK = 4
    PAGE_RESOURCE = 5
    PAGE_SEQUENCE = 6
    PAGE_EXPLORER = 7
    PAGE_REPORTS = 8
    PAGE_SETTINGS = 9
    PAGE_ABOUT = 10

    # Compatibility aliases
    PAGE_DASHBOARD = PAGE_OVERVIEW
    PAGE_IMPORT = PAGE_EVENT_LOGS
    PAGE_EX_117 = PAGE_OUTCOMES
    PAGE_EX_1115 = PAGE_REWORK
    PAGE_EX_1118 = PAGE_RESOURCE
    PAGE_EX_1122 = PAGE_SEQUENCE

    def __init__(self) -> None:
        super().__init__()
        self.service = AnalysisService()
        self.worker: TaskWorker | None = None
        self.latest_results: dict[str, AnalysisResult] = {}
        self.overview: DatasetOverview | None = None
        self.latest_fast_slow: FastSlowComparison | None = None
        self.latest_dfg_edges: list[dict[str, Any]] = []
        self.sidebar_collapsed: bool = False
        self.show_academic_refs: bool = True

        self.result_tables: dict[str, QTableWidget] = {}
        self.evidence_boxes: dict[str, QTextEdit] = {}
        self.case_list_tables: dict[str, QTableWidget] = {}
        self.trace_tables: dict[str, QTableWidget] = {}
        self.run_buttons: dict[str, QPushButton] = {}
        self.academic_badges: list[QLabel] = []
        self.nav_buttons: list[QPushButton] = []
        self.nav_section_labels: list[QLabel] = []
        self._nav_specs: list[tuple[int, str, str]] = []
        self.param_act_combos: dict[str, QComboBox] = {}
        self.param_lc_combos: dict[str, QComboBox] = {}
        self.param_min_spins: dict[str, QSpinBox] = {}

        self.setWindowTitle("Tracely — Process Mining & Event Log Intelligence")
        self.resize(1460, 900)
        self.setMinimumSize(1024, 680)
        self.setStyleSheet(build_global_stylesheet())
        self._build_ui()
        self.nav_list = _NavListProxy(self)
        self._set_analysis_enabled(False)
        self.navigate_to(self.PAGE_OVERVIEW)

    # ------------------------------------------------------------------
    # Shell Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_top_nav())

        body_frame = QWidget()
        body_layout = QHBoxLayout(body_frame)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.sidebar_frame = self._build_sidebar()
        body_layout.addWidget(self.sidebar_frame)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setHandleWidth(2)

        workspace_container = QWidget()
        workspace_layout = QVBoxLayout(workspace_container)
        workspace_layout.setContentsMargins(18, 14, 18, 14)
        workspace_layout.setSpacing(12)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_overview_page())        # 0: Overview
        self.pages.addWidget(self._build_projects_page())        # 1: Projects
        self.pages.addWidget(self._build_event_logs_page())      # 2: Event Logs
        self.pages.addWidget(self._build_outcomes_page())        # 3: Process Outcomes
        self.pages.addWidget(self._build_rework_page())          # 4: Rework Analysis
        self.pages.addWidget(self._build_resource_page())        # 5: Resource Analysis
        self.pages.addWidget(self._build_sequence_page())        # 6: Event Sequence
        self.pages.addWidget(self._build_case_explorer_page())   # 7: Case Explorer
        self.pages.addWidget(self._build_reports_page())         # 8: Reports & Export
        self.pages.addWidget(self._build_settings_page())        # 9: Settings
        self.pages.addWidget(self._build_about_page())           # 10: About

        workspace_layout.addWidget(self.pages, 1)
        self.main_splitter.addWidget(workspace_container)

        self.context_panel = self._build_contextual_panel()
        self.main_splitter.addWidget(self.context_panel)
        self.main_splitter.setStretchFactor(0, 7)
        self.main_splitter.setStretchFactor(1, 3)
        self.main_splitter.setSizes([1020, 420])

        body_layout.addWidget(self.main_splitter, 1)
        root_layout.addWidget(body_frame, 1)
        root_layout.addWidget(self._build_status_bar())
        self.setCentralWidget(central)

    def _build_top_nav(self) -> QFrame:
        top_bar = QFrame()
        top_bar.setObjectName("TopNavBar")
        top_bar.setFixedHeight(TOPBAR_HEIGHT)
        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(SPACE_LG, SPACE_SM, SPACE_LG, SPACE_SM)
        layout.setSpacing(SPACE_SM)

        self.sidebar_toggle_btn = make_button(
            "☰", variant="icon", tooltip="Toggle Collapsible Sidebar"
        )
        self.sidebar_toggle_btn.clicked.connect(self.toggle_sidebar)
        layout.addWidget(self.sidebar_toggle_btn)

        logo = QLabel("T")
        logo.setObjectName("BrandLogo")
        logo.setFixedHeight(34)
        brand = QLabel("TRACELY")
        brand.setObjectName("BrandTitle")
        layout.addWidget(logo)
        layout.addWidget(brand)

        self.breadcrumb_badge = make_ref_badge("WORKSPACE / OVERVIEW", COLOR_ACCENT)
        layout.addWidget(self.breadcrumb_badge)
        layout.addSpacing(4)

        self.dataset_label = QLabel("No Active Event Log")
        self.dataset_label.setFixedHeight(34)
        self.dataset_label.setStyleSheet(
            f"background-color: {COLOR_BG}; border: 2px solid {COLOR_BORDER}; "
            "border-radius: 6px; padding: 4px 12px; font-weight: 700;"
        )
        self.dataset_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.dataset_label, 1)

        self.open_button = make_button("Import Event Log", variant="accent")
        self.open_button.clicked.connect(self._choose_xes)
        layout.addWidget(self.open_button)

        self.run_all_button = make_button("Run All Analyses", variant="primary")
        self.run_all_button.clicked.connect(self._run_all_analyses)
        layout.addWidget(self.run_all_button)

        self.export_button = make_button("Export CSV", variant="secondary")
        self.export_button.clicked.connect(self._export_results)
        self.export_button.setEnabled(False)
        layout.addWidget(self.export_button)

        self.export_pdf_button = make_button("Export PDF", variant="secondary")
        self.export_pdf_button.clicked.connect(self._export_pdf_report)
        self.export_pdf_button.setEnabled(False)
        layout.addWidget(self.export_pdf_button)

        self.academic_toggle_btn = make_button(
            "Academic Refs: ON",
            variant="secondary",
            tooltip="Show/Hide Academic Exercise Reference Codes (11.7, 11.15, 11.18, 11.22)",
        )
        self.academic_toggle_btn.setCheckable(True)
        self.academic_toggle_btn.setChecked(True)
        self.academic_toggle_btn.clicked.connect(self.toggle_academic_references)
        layout.addWidget(self.academic_toggle_btn)

        self.context_toggle_btn = make_button("Trace Inspector", variant="secondary")
        self.context_toggle_btn.setCheckable(True)
        self.context_toggle_btn.setChecked(True)
        self.context_toggle_btn.clicked.connect(self.toggle_context_panel)
        layout.addWidget(self.context_toggle_btn)

        return top_bar

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("SidebarFrame")
        sidebar.setFixedWidth(SIDEBAR_WIDTH_EXPANDED)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(4)

        sections: list[tuple[str, list[tuple[int, str, str]]]] = [
            (
                "WORKSPACE",
                [
                    (self.PAGE_OVERVIEW, "■  Overview", "■"),
                    (self.PAGE_PROJECTS, "◆  Projects", "◆"),
                    (self.PAGE_EVENT_LOGS, "▤  Event Logs", "▤"),
                ],
            ),
            (
                "ANALYTICS",
                [
                    (self.PAGE_OUTCOMES, "●  Process Outcomes", "●"),
                    (self.PAGE_REWORK, "↻  Rework Analysis", "↻"),
                    (self.PAGE_RESOURCE, "◈  Resource Analysis", "◈"),
                    (self.PAGE_SEQUENCE, "⇄  Event Sequence", "⇄"),
                ],
            ),
            (
                "DATA",
                [
                    (self.PAGE_EXPLORER, "⌕  Case Explorer", "⌕"),
                    (self.PAGE_REPORTS, "⇪  Reports & Export", "⇪"),
                ],
            ),
            (
                "APPLICATION",
                [
                    (self.PAGE_SETTINGS, "⚙  Settings", "⚙"),
                    (self.PAGE_ABOUT, "ⓘ  About", "ⓘ"),
                ],
            ),
        ]

        for sec_title, items in sections:
            sec_lbl = QLabel(sec_title)
            sec_lbl.setObjectName("SidebarSectionHeader")
            layout.addWidget(sec_lbl)
            self.nav_section_labels.append(sec_lbl)

            for page_idx, full_text, short_icon in items:
                btn = QPushButton(full_text)
                btn.setObjectName("NavButton")
                btn.setFixedHeight(36)
                btn.setProperty("active", "false")
                btn.clicked.connect(lambda _=False, idx=page_idx: self.navigate_to(idx))
                layout.addWidget(btn)
                self.nav_buttons.append(btn)
                self._nav_specs.append((page_idx, full_text, short_icon))

        layout.addStretch(1)

        self.sidebar_status_card = make_neubrutal_card(shadow_offset=2)
        self.sidebar_status_card.setStyleSheet(
            f"background-color: {COLOR_BG}; border: 2px solid {COLOR_BORDER}; border-radius: 7px;"
        )
        sb_layout = QVBoxLayout(self.sidebar_status_card)
        sb_layout.setContentsMargins(10, 8, 10, 8)
        sb_layout.setSpacing(2)
        sb_title = QLabel("ENGINE STATUS")
        sb_title.setStyleSheet("font-size: 10px; font-weight: 900;")
        self.sidebar_engine_lbl = QLabel("PM4Py Engine • Idle")
        self.sidebar_engine_lbl.setStyleSheet("font-size: 11px; font-weight: 700;")
        sb_layout.addWidget(sb_title)
        sb_layout.addWidget(self.sidebar_engine_lbl)
        layout.addWidget(self.sidebar_status_card)

        return sidebar

    def _build_contextual_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("ContextPanel")
        panel.setMinimumWidth(360)
        panel.setMaximumWidth(540)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        title = QLabel("TRACE INSPECTOR")
        title.setObjectName("SectionHeading")
        self.ctx_case_badge = make_ref_badge("NO CASE", COLOR_ACCENT)
        hdr.addWidget(title)
        hdr.addStretch(1)
        hdr.addWidget(self.ctx_case_badge)
        layout.addLayout(hdr)

        self.ctx_summary_label = QLabel(
            "Select any Case ID row in an analytical module or Case Explorer to inspect "
            "its chronological event trace and timestamp evidence."
        )
        self.ctx_summary_label.setWordWrap(True)
        self.ctx_summary_label.setStyleSheet(
            f"background-color: {COLOR_BG}; border: 2px solid {COLOR_BORDER}; "
            "border-radius: 7px; padding: 8px 10px; font-weight: 600; font-size: 12px;"
        )
        layout.addWidget(self.ctx_summary_label)

        self.ctx_trace_table = make_table([
            "#",
            "Timestamp (UTC)",
            "Activity",
            "Lifecycle",
            "Resource",
        ])
        layout.addWidget(self.ctx_trace_table, 1)

        # Hidden dummy box kept only for backward compatibility with internal handlers (no raw JSON in UI)
        self.ctx_evidence_text = QTextEdit()
        self.ctx_evidence_text.setVisible(False)

        return panel

    def _build_status_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("StatusBarFrame")
        bar.setFixedHeight(STATUSBAR_HEIGHT)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(SPACE_LG, 4, SPACE_LG, 4)
        layout.setSpacing(SPACE_MD)

        self.status_indicator_dot = QLabel("● READY")
        self.status_indicator_dot.setFixedHeight(24)
        self.status_indicator_dot.setStyleSheet(
            f"background-color: {COLOR_SUCCESS}; border: 1.5px solid {COLOR_BORDER}; "
            "border-radius: 5px; padding: 2px 8px; font-size: 11px; font-weight: 900;"
        )
        layout.addWidget(self.status_indicator_dot)

        self.status_label = QLabel("Tracely ready. Import an IEEE XES event log (.xes or .xes.gz) to start.")
        self.status_label.setStyleSheet("font-weight: 700; font-size: 12px;")
        layout.addWidget(self.status_label, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedWidth(220)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        return bar

    # ------------------------------------------------------------------
    # Navigation & Collapsible Behavior
    # ------------------------------------------------------------------
    def toggle_sidebar(self) -> None:
        self.sidebar_collapsed = not self.sidebar_collapsed
        if self.sidebar_collapsed:
            self.sidebar_frame.setFixedWidth(SIDEBAR_WIDTH_COLLAPSED)
            for lbl in self.nav_section_labels:
                lbl.setVisible(False)
            self.sidebar_status_card.setVisible(False)
            for btn, (_, full_text, short_icon) in zip(self.nav_buttons, self._nav_specs):
                btn.setText(short_icon)
                btn.setToolTip(full_text)
                btn.setStyleSheet("text-align: center; padding: 6px 4px; font-size: 15px;")
        else:
            self.sidebar_frame.setFixedWidth(SIDEBAR_WIDTH_EXPANDED)
            for lbl in self.nav_section_labels:
                lbl.setVisible(True)
            self.sidebar_status_card.setVisible(True)
            for btn, (_, full_text, _) in zip(self.nav_buttons, self._nav_specs):
                btn.setText(full_text)
                btn.setToolTip("")
                btn.setStyleSheet("")
        self._refresh_nav_styles(self.pages.currentIndex())

    def toggle_context_panel(self) -> None:
        visible = self.context_panel.isHidden()
        self.context_panel.setVisible(visible)
        self.context_toggle_btn.setChecked(visible)

    def toggle_academic_references(self) -> None:
        self.show_academic_refs = self.academic_toggle_btn.isChecked()
        self.academic_toggle_btn.setText(
            "Academic Refs: ON" if self.show_academic_refs else "Academic Refs: OFF"
        )
        for badge in self.academic_badges:
            badge.setVisible(self.show_academic_refs)
        self.navigate_to(self.pages.currentIndex())
        self._refresh_dashboard_table()
        for key in ("11.7", "11.15", "11.18", "11.22"):
            if key == "11.7":
                items = [
                    self.latest_results[c]
                    for c in ("11.7A", "11.7B", "11.7C", "11.7D", "11.7E")
                    if c in self.latest_results
                ]
                if items:
                    self._on_analysis_finished("11.7", {i.code: i for i in items})
            elif key in self.latest_results:
                self._on_analysis_finished(key, self.latest_results[key])

    def navigate_to(self, page_index: int) -> None:
        if not (0 <= page_index < self.pages.count()):
            return
        self.pages.setCurrentIndex(page_index)
        self._refresh_nav_styles(page_index)

        if self.show_academic_refs:
            breadcrumbs = {
                self.PAGE_OVERVIEW: "WORKSPACE / OVERVIEW",
                self.PAGE_PROJECTS: "WORKSPACE / PROJECTS",
                self.PAGE_EVENT_LOGS: "WORKSPACE / EVENT LOGS",
                self.PAGE_OUTCOMES: "ANALYTICS / PROCESS OUTCOMES [EX 11.7 A–E & EX 11.10]",
                self.PAGE_REWORK: "ANALYTICS / REWORK ANALYSIS [EX 11.15]",
                self.PAGE_RESOURCE: "ANALYTICS / RESOURCE ANALYSIS [EX 11.18]",
                self.PAGE_SEQUENCE: "ANALYTICS / EVENT SEQUENCE [EX 11.22]",
                self.PAGE_EXPLORER: "DATA / CASE EXPLORER",
                self.PAGE_REPORTS: "DATA / REPORTS & EXPORT",
                self.PAGE_SETTINGS: "APPLICATION / SETTINGS",
                self.PAGE_ABOUT: "APPLICATION / ABOUT",
            }
        else:
            breadcrumbs = {
                self.PAGE_OVERVIEW: "WORKSPACE / OVERVIEW",
                self.PAGE_PROJECTS: "WORKSPACE / PROJECTS",
                self.PAGE_EVENT_LOGS: "WORKSPACE / EVENT LOGS",
                self.PAGE_OUTCOMES: "ANALYTICS / PROCESS OUTCOMES",
                self.PAGE_REWORK: "ANALYTICS / REWORK ANALYSIS",
                self.PAGE_RESOURCE: "ANALYTICS / RESOURCE ANALYSIS",
                self.PAGE_SEQUENCE: "ANALYTICS / EVENT SEQUENCE",
                self.PAGE_EXPLORER: "DATA / CASE EXPLORER",
                self.PAGE_REPORTS: "DATA / REPORTS & EXPORT",
                self.PAGE_SETTINGS: "APPLICATION / SETTINGS",
                self.PAGE_ABOUT: "APPLICATION / ABOUT",
            }
        self.breadcrumb_badge.setText(breadcrumbs.get(page_index, "TRACELY WORKSPACE"))

    def _refresh_nav_styles(self, active_index: int) -> None:
        for btn, (idx, _, _) in zip(self.nav_buttons, self._nav_specs):
            is_active = idx == active_index
            btn.setProperty("active", "true" if is_active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    # ------------------------------------------------------------------
    # Page 0: Overview Dashboard
    # ------------------------------------------------------------------
    def _build_overview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        hdr = QHBoxLayout()
        title_col = QVBoxLayout()
        t_lbl = QLabel("Overview Dashboard")
        t_lbl.setObjectName("PageTitle")
        s_lbl = QLabel(
            "Real-time Process Mining intelligence workspace. All metrics are computed dynamically from the active event log."
        )
        s_lbl.setObjectName("PageSubtitle")
        title_col.addWidget(t_lbl)
        title_col.addWidget(s_lbl)
        hdr.addLayout(title_col, 1)

        self.ov_import_btn = QPushButton("Import Event Log (.xes / .xes.gz)")
        self.ov_import_btn.setObjectName("AccentButton")
        apply_hard_shadow(self.ov_import_btn, 3, 3)
        self.ov_import_btn.clicked.connect(self._choose_xes)
        hdr.addWidget(self.ov_import_btn)

        self.dash_run_all_btn = QPushButton("Run All Analyses")
        apply_hard_shadow(self.dash_run_all_btn, 3, 3)
        self.dash_run_all_btn.clicked.connect(self._run_all_analyses)
        hdr.addWidget(self.dash_run_all_btn)
        layout.addLayout(hdr)

        self.empty_state_banner = QFrame()
        self.empty_state_banner.setObjectName("EmptyStateBanner")
        apply_hard_shadow(self.empty_state_banner, 3, 3)
        eb_layout = QHBoxLayout(self.empty_state_banner)
        eb_layout.setContentsMargins(14, 10, 14, 10)
        self.dash_status_text = QLabel(
            "EMPTY WORKSPACE — No XES event log loaded yet. Click 'Import Event Log' or open the Projects page "
            "to load an event log from your workspace."
        )
        self.dash_status_text.setWordWrap(True)
        self.dash_status_text.setStyleSheet("font-weight: 800; font-size: 12.5px;")
        eb_layout.addWidget(self.dash_status_text, 1)
        layout.addWidget(self.empty_state_banner)

        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(12)
        c1, self.dash_cases_val, self.dash_cases_sub = make_kpi_card(
            "Total Cases", "—", "CASES", COLOR_ACCENT
        )
        c2, self.dash_events_val, self.dash_events_sub = make_kpi_card(
            "Total Events", "—", "EVENTS", COLOR_SUCCESS
        )
        c3, self.dash_activities_val, self.dash_activities_sub = make_kpi_card(
            "Unique Activities", "—", "ACTIVITIES", COLOR_ACCENT
        )
        c4, self.dash_cycle_val, self.dash_cycle_sub = make_kpi_card(
            "Average Cycle Time", "—", "DURATION", COLOR_SUCCESS
        )
        kpi_grid.addWidget(c1, 0, 0)
        kpi_grid.addWidget(c2, 0, 1)
        kpi_grid.addWidget(c3, 0, 2)
        kpi_grid.addWidget(c4, 0, 3)
        layout.addLayout(kpi_grid)

        lower_split = QSplitter(Qt.Horizontal)

        freq_card = make_neubrutal_card(shadow_offset=3)
        freq_layout = QVBoxLayout(freq_card)
        freq_layout.setContentsMargins(14, 12, 14, 12)
        freq_title = QLabel("Activity Frequency & Dataset Information")
        freq_title.setObjectName("SectionHeading")
        freq_layout.addWidget(freq_title)

        self.overview_label = QLabel("Dataset Information: Awaiting XES import.")
        self.overview_label.setWordWrap(True)
        self.overview_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        freq_layout.addWidget(self.overview_label)

        self.activity_table = make_table([
            "Activity Name",
            "Event Count",
            "Share (%)",
        ])
        freq_layout.addWidget(self.activity_table, 1)
        lower_split.addWidget(freq_card)

        rec_card = make_neubrutal_card(shadow_offset=3)
        rec_layout = QVBoxLayout(rec_card)
        rec_layout.setContentsMargins(14, 12, 14, 12)
        rec_title = QLabel("Recent Analysis Summary (Double-click row to open module)")
        rec_title.setObjectName("SectionHeading")
        rec_layout.addWidget(rec_title)

        self.dashboard_table = make_table([
            "Metric ID",
            "Analytical Module",
            "Cases",
            "Total",
            "Share",
            "Avg Cycle (d)",
            "Rule Summary",
        ])
        self.dashboard_table.cellDoubleClicked.connect(self._on_dashboard_row_activated)
        rec_layout.addWidget(self.dashboard_table, 1)
        lower_split.addWidget(rec_card)

        lower_split.setStretchFactor(0, 2)
        lower_split.setStretchFactor(1, 3)
        layout.addWidget(lower_split, 1)

        return page

    # ------------------------------------------------------------------
    # Page 1: Projects
    # ------------------------------------------------------------------
    def _build_projects_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        t_lbl = QLabel("Projects & Event Log Repository")
        t_lbl.setObjectName("PageTitle")
        s_lbl = QLabel(
            "Manage event log analysis sessions, open discovered XES files in the workspace, or import external logs."
        )
        s_lbl.setObjectName("PageSubtitle")
        layout.addWidget(t_lbl)
        layout.addWidget(s_lbl)

        card = make_neubrutal_card(shadow_offset=3)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(14, 14, 14, 14)
        c_layout.setSpacing(10)

        top_row = QHBoxLayout()
        lbl = QLabel("Available Event Logs in Workspace")
        lbl.setObjectName("SectionHeading")
        top_row.addWidget(lbl)
        top_row.addStretch(1)

        refresh_btn = QPushButton("Rescan Workspace")
        refresh_btn.setObjectName("SecondaryButton")
        refresh_btn.clicked.connect(self._refresh_projects_table)
        load_selected_btn = QPushButton("Load Selected Event Log")
        load_selected_btn.setObjectName("AccentButton")
        load_selected_btn.clicked.connect(self._load_selected_project_log)
        browse_new_btn = QPushButton("Browse External XES...")
        browse_new_btn.clicked.connect(self._choose_xes)

        top_row.addWidget(refresh_btn)
        top_row.addWidget(load_selected_btn)
        top_row.addWidget(browse_new_btn)
        c_layout.addLayout(top_row)

        self.projects_table = make_table([
            "Event Log File",
            "Source Folder",
            "Size",
            "File Path",
            "Status",
        ])
        self.projects_table.cellDoubleClicked.connect(lambda _r, _c: self._load_selected_project_log())
        c_layout.addWidget(self.projects_table, 1)
        layout.addWidget(card, 1)

        self._refresh_projects_table()
        return page

    def _refresh_projects_table(self) -> None:
        candidates: list[tuple[str, Path]] = []
        root = Path.cwd()
        for folder, category in [
            (root / "data", "Workspace Data"),
            (root / "data" / "raw", "Raw Event Logs"),
            (root / "examples", "Sample Demo Log"),
        ]:
            if folder.exists():
                for p in sorted(folder.iterdir()):
                    if p.is_file() and (
                        p.name.casefold().endswith(".xes") or p.name.casefold().endswith(".xes.gz")
                    ):
                        candidates.append((category, p))

        self.projects_table.setRowCount(len(candidates))
        for idx, (cat, path) in enumerate(candidates):
            size_mb = path.stat().st_size / (1024 * 1024)
            size_str = f"{size_mb:.2f} MB" if size_mb >= 0.1 else f"{path.stat().st_size:,} B"
            is_active = self.service.source_path is not None and self.service.source_path == path.resolve()
            status = "ACTIVE LOG" if is_active else "Available"
            for col, val in enumerate((path.name, cat, size_str, str(path.resolve()), status)):
                self.projects_table.setItem(idx, col, QTableWidgetItem(val))
        autofit_table_columns(self.projects_table)

    def _load_selected_project_log(self) -> None:
        selected = self.projects_table.selectedItems()
        if not selected:
            QMessageBox.information(
                self, "Select Event Log", "Please select an event log row in the table first."
            )
            return
        row = selected[0].row()
        path_item = self.projects_table.item(row, 3)
        if path_item is not None:
            self.load_xes_file(path_item.text())

    # ------------------------------------------------------------------
    # Page 2: Event Logs (Import, Schema Validation & Duration Distribution)
    # ------------------------------------------------------------------
    def _build_event_logs_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        hdr = QHBoxLayout()
        title_col = QVBoxLayout()
        t_lbl = QLabel("Event Logs — Import, Schema & Distribution")
        t_lbl.setObjectName("PageTitle")
        s_lbl = QLabel(
            "IEEE XES event log ingestion via PM4Py, attribute schema verification, and case cycle time distribution."
        )
        s_lbl.setObjectName("PageSubtitle")
        title_col.addWidget(t_lbl)
        title_col.addWidget(s_lbl)
        hdr.addLayout(title_col, 1)
        hdr.addWidget(make_ref_badge("IEEE XES / PM4PY", COLOR_ACCENT))
        layout.addLayout(hdr)

        import_card = make_neubrutal_card(shadow_offset=3)
        imp_layout = QVBoxLayout(import_card)
        imp_layout.setContentsMargins(14, 12, 14, 12)
        imp_layout.setSpacing(8)

        path_row = QHBoxLayout()
        self.import_path_edit = QLineEdit()
        self.import_path_edit.setReadOnly(True)
        self.import_path_edit.setPlaceholderText("Select an IEEE .xes or .xes.gz event log file...")
        browse_btn = QPushButton("Select & Load XES File...")
        browse_btn.setObjectName("AccentButton")
        browse_btn.clicked.connect(self._choose_xes)
        path_row.addWidget(self.import_path_edit, 1)
        path_row.addWidget(browse_btn)
        imp_layout.addLayout(path_row)

        self.import_details_label = QLabel(
            "No dataset loaded. Core XES attributes: case:concept:name, concept:name, time:timestamp."
        )
        self.import_details_label.setWordWrap(True)
        self.import_details_label.setStyleSheet("font-weight: 600;")
        imp_layout.addWidget(self.import_details_label)
        layout.addWidget(import_card)

        self.ov_cases_val = QLabel("—")
        self.ov_events_val = QLabel("—")
        self.ov_activities_val = QLabel("—")
        self.ov_cycle_val = QLabel("—")

        split = QSplitter(Qt.Horizontal)

        schema_card = make_neubrutal_card(shadow_offset=3)
        sc_layout = QVBoxLayout(schema_card)
        sc_layout.setContentsMargins(14, 12, 14, 12)
        sc_title = QLabel("XES Attribute Schema Validation")
        sc_title.setObjectName("SectionHeading")
        sc_layout.addWidget(sc_title)
        self.schema_table = make_table([
            "Canonical Field",
            "XES Standard Key",
            "Analytical Scope",
            "Status",
        ])
        self._populate_schema_table([])
        sc_layout.addWidget(self.schema_table, 1)
        split.addWidget(schema_card)

        dist_card = make_neubrutal_card(shadow_offset=3)
        dc_layout = QVBoxLayout(dist_card)
        dc_layout.setContentsMargins(14, 12, 14, 12)
        dc_hdr = QHBoxLayout()
        dc_title = QLabel("Case Cycle Time Distribution (Days)")
        dc_title.setObjectName("SectionHeading")
        self.refresh_dist_btn = QPushButton("Refresh Chart")
        self.refresh_dist_btn.setObjectName("SecondaryButton")
        self.refresh_dist_btn.clicked.connect(self._plot_duration_distribution)
        dc_hdr.addWidget(dc_title)
        dc_hdr.addStretch(1)
        dc_hdr.addWidget(self.refresh_dist_btn)
        dc_layout.addLayout(dc_hdr)

        self.dist_figure = Figure(figsize=(5.5, 3.6), tight_layout=True)
        self.dist_canvas = FigureCanvas(self.dist_figure)
        dc_layout.addWidget(self.dist_canvas, 1)
        split.addWidget(dist_card)

        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        layout.addWidget(split, 1)
        return page

    # ------------------------------------------------------------------
    # Page 3: Process Outcomes
    # ------------------------------------------------------------------
    def _build_outcomes_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        hdr = QHBoxLayout()
        title_col = QVBoxLayout()
        t_lbl = QLabel("Process Outcomes & Cycle Time Performance")
        t_lbl.setObjectName("PageTitle")
        s_lbl = QLabel(
            "Evaluate process completion cohorts (positive outcome, negative outcome, terminal cancellation) "
            "and compare Fast vs Slow throughput segments."
        )
        s_lbl.setObjectName("PageSubtitle")
        s_lbl.setWordWrap(True)
        title_col.addWidget(t_lbl)
        title_col.addWidget(s_lbl)
        hdr.addLayout(title_col, 1)

        out_badge = make_ref_badge("EX 11.7 A–E & EX 11.10", COLOR_ACCENT)
        self.academic_badges.append(out_badge)
        hdr.addWidget(out_badge)

        preset_btn = QPushButton("Auto-Detect Outcomes")
        preset_btn.setObjectName("SecondaryButton")
        preset_btn.clicked.connect(self._apply_bpic17_outcomes_preset)
        hdr.addWidget(preset_btn)

        run_btn = QPushButton("Run Outcome Analysis")
        apply_hard_shadow(run_btn, 3, 3)
        run_btn.clicked.connect(
            lambda: self._run_analysis(
                "11.7",
                lambda: self.service.run_117(
                    accepted_activity=self.out_acc_combo.currentText(),
                    refused_activity=self.out_ref_combo.currentText(),
                    cancelled_activity=self.out_can_combo.currentText(),
                ),
            )
        )
        self.run_buttons["11.7"] = run_btn
        hdr.addWidget(run_btn)
        layout.addLayout(hdr)

        # Clean Grid Parameter Bar so dropdowns never clip
        param_card = make_neubrutal_card(shadow_offset=2)
        param_grid = QGridLayout(param_card)
        param_grid.setContentsMargins(12, 8, 12, 8)
        param_grid.setHorizontalSpacing(10)
        param_grid.setVerticalSpacing(4)

        param_grid.addWidget(QLabel("Positive Outcome (Contains):"), 0, 0)
        self.out_acc_combo = QComboBox()
        self.out_acc_combo.setEditable(True)
        self.out_acc_combo.setCurrentText("O_Accepted")
        param_grid.addWidget(self.out_acc_combo, 0, 1)

        param_grid.addWidget(QLabel("Negative Outcome (Contains):"), 0, 2)
        self.out_ref_combo = QComboBox()
        self.out_ref_combo.setEditable(True)
        self.out_ref_combo.setCurrentText("O_Refused")
        param_grid.addWidget(self.out_ref_combo, 0, 3)

        param_grid.addWidget(QLabel("Terminal Cancellation (Final Event):"), 0, 4)
        self.out_can_combo = QComboBox()
        self.out_can_combo.setEditable(True)
        self.out_can_combo.setCurrentText("O_Cancelled")
        param_grid.addWidget(self.out_can_combo, 0, 5)
        param_grid.setColumnStretch(1, 1)
        param_grid.setColumnStretch(3, 1)
        param_grid.setColumnStretch(5, 1)
        layout.addWidget(param_card)

        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(10)
        k1, self.out_total_val, _ = make_kpi_card("Total Cases", "—", "11.7A", COLOR_ACCENT)
        k2, self.out_accepted_val, self.out_accepted_sub = make_kpi_card("Positive Outcome", "—", "11.7C", COLOR_SUCCESS)
        k3, self.out_refused_val, self.out_refused_sub = make_kpi_card("Negative Outcome", "—", "11.7D", COLOR_DANGER)
        k4, self.out_cancelled_val, self.out_cancelled_sub = make_kpi_card("Terminal Cancelled", "—", "11.7E", COLOR_ACCENT)
        k5, self.out_cycle_val, _ = make_kpi_card("Avg Cycle Time", "—", "11.7B", COLOR_SUCCESS)
        kpi_grid.addWidget(k1, 0, 0)
        kpi_grid.addWidget(k2, 0, 1)
        kpi_grid.addWidget(k3, 0, 2)
        kpi_grid.addWidget(k4, 0, 3)
        kpi_grid.addWidget(k5, 0, 4)
        layout.addLayout(kpi_grid)

        tabs = QTabWidget()

        tab_117 = QWidget()
        t117_layout = QVBoxLayout(tab_117)
        t117_layout.setContentsMargins(10, 10, 10, 10)
        t117_layout.setSpacing(8)

        table_117 = make_table([
            "Cohort Metric",
            "Matching Cases",
            "Total Cases",
            "Share (%)",
            "Avg Cycle Time (days)",
            "Sample Case IDs",
        ])
        table_117.setMaximumHeight(175)
        table_117.itemSelectionChanged.connect(lambda: self._on_result_row_selected("11.7"))
        t117_layout.addWidget(table_117)

        split_117 = QSplitter(Qt.Horizontal)
        case_table_117 = make_table(["Cohort", "Case ID", "Outcome & Cycle Time Evidence"])
        case_table_117.itemSelectionChanged.connect(lambda: self._on_exercise_case_selected("11.7"))
        trace_table_117 = make_table(["#", "Timestamp (UTC)", "Activity", "Lifecycle", "Resource"])
        ev_box_117 = QTextEdit()
        ev_box_117.setReadOnly(True)
        ev_box_117.setPlaceholderText("Rule specification and structured case evidence...")

        left_w = QWidget()
        lw_layout = QVBoxLayout(left_w)
        lw_layout.setContentsMargins(0, 0, 4, 0)
        lw_layout.addWidget(QLabel("Matching Cases (Select row to inspect full trace):"))
        lw_layout.addWidget(case_table_117, 1)
        lw_layout.addWidget(QLabel("Selected Case Event Trace:"))
        lw_layout.addWidget(trace_table_117, 1)

        right_w = QWidget()
        rw_layout = QVBoxLayout(right_w)
        rw_layout.setContentsMargins(4, 0, 0, 0)
        rw_layout.addWidget(QLabel("Cohort Rule & Evidence Summary:"))
        rw_layout.addWidget(ev_box_117, 1)

        split_117.addWidget(left_w)
        split_117.addWidget(right_w)
        split_117.setStretchFactor(0, 3)
        split_117.setStretchFactor(1, 2)
        t117_layout.addWidget(split_117, 1)

        self.result_tables["11.7"] = table_117
        self.case_list_tables["11.7"] = case_table_117
        self.trace_tables["11.7"] = trace_table_117
        self.evidence_boxes["11.7"] = ev_box_117
        tabs.addTab(tab_117, "Outcome Cohorts & Cycle Time")

        tab_fs = QWidget()
        fs_layout = QVBoxLayout(tab_fs)
        fs_layout.setContentsMargins(10, 10, 10, 10)
        fs_layout.setSpacing(8)

        fs_ctrl = QHBoxLayout()
        fs_ctrl.addWidget(QLabel("Cycle Time Threshold (Days):"))
        self.fast_slow_spin = QDoubleSpinBox()
        self.fast_slow_spin.setRange(0.1, 1000.0)
        self.fast_slow_spin.setValue(45.0)
        self.fast_slow_spin.setDecimals(1)
        self.fast_slow_btn = QPushButton("Compare Fast vs Slow Cases")
        self.fast_slow_btn.clicked.connect(self._run_fast_slow_analysis)
        fs_ctrl.addWidget(self.fast_slow_spin)
        fs_ctrl.addWidget(self.fast_slow_btn)
        fs_ctrl.addStretch(1)

        self.fs_fast_count_val = QLabel("—")
        self.fs_fast_mean_val = QLabel("—")
        self.fs_slow_count_val = QLabel("—")
        self.fs_slow_mean_val = QLabel("—")
        fs_layout.addLayout(fs_ctrl)

        self.fast_slow_table = make_table([
            "Process Characteristic / Metric",
            "Fast Cases (< Threshold)",
            "Slow Cases (>= Threshold)",
        ])
        fs_layout.addWidget(self.fast_slow_table, 2)

        self.fast_slow_evidence_box = QTextEdit()
        self.fast_slow_evidence_box.setReadOnly(True)
        self.fast_slow_evidence_box.setPlaceholderText("Fast vs Slow throughput comparison details...")
        fs_layout.addWidget(self.fast_slow_evidence_box, 1)
        tabs.addTab(tab_fs, "Fast vs Slow Throughput Segmentation")

        layout.addWidget(tabs, 1)
        return page

    # ------------------------------------------------------------------
    # Page 4: Rework Analysis
    # ------------------------------------------------------------------
    def _build_rework_page(self) -> QWidget:
        return self._build_specialized_analysis_page(
            key="11.15",
            page_title="Rework Analysis — Repeated Activity Execution",
            subtitle=(
                "Identify cases where a target activity is executed repeatedly with a specific "
                "lifecycle transition (e.g., complete >= 2 occurrences within the same case)."
            ),
            button_label="Run Rework Analysis",
            callback=lambda: self.service.run_1115(
                target_activity=self.param_act_combos["11.15"].currentText(),
                min_occurrences=self.param_min_spins["11.15"].value(),
                target_lifecycle=self.param_lc_combos["11.15"].currentText(),
            ),
            kpi_defs=[
                ("Target Activity", "W_Assess potential fraud", "ACTIVITY", COLOR_ACCENT),
                ("Lifecycle Filter", "complete (>= 2x)", "TRANSITION", COLOR_SUCCESS),
                ("Matching Case Count", "—", "REWORK COHORT", COLOR_ACCENT),
            ],
        )

    # ------------------------------------------------------------------
    # Page 5: Resource Analysis
    # ------------------------------------------------------------------
    def _build_resource_page(self) -> QWidget:
        return self._build_specialized_analysis_page(
            key="11.18",
            page_title="Resource Analysis — Same-Resource Repeated Execution",
            subtitle=(
                "Identify cases where the exact same identified org:resource completes the target activity "
                "multiple times within one case. Missing resources are excluded from grouping."
            ),
            button_label="Run Resource Analysis",
            callback=lambda: self.service.run_1118(
                target_activity=self.param_act_combos["11.18"].currentText(),
                min_occurrences=self.param_min_spins["11.18"].value(),
                target_lifecycle=self.param_lc_combos["11.18"].currentText(),
            ),
            kpi_defs=[
                ("Target Activity", "W_Assess potential fraud", "ACTIVITY", COLOR_ACCENT),
                ("Resource Constraint", "Same Known Resource (>= 2x)", "ORG:RESOURCE", COLOR_SUCCESS),
                ("Matching Case Count", "—", "RESOURCE COHORT", COLOR_ACCENT),
            ],
        )

    def _build_specialized_analysis_page(
        self,
        key: str,
        page_title: str,
        subtitle: str,
        button_label: str,
        callback: Callable[[], Any],
        kpi_defs: list[tuple[str, str, str, str]],
    ) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        hdr = QHBoxLayout()
        title_col = QVBoxLayout()
        t_lbl = QLabel(page_title)
        t_lbl.setObjectName("PageTitle")
        s_lbl = QLabel(subtitle)
        s_lbl.setObjectName("PageSubtitle")
        s_lbl.setWordWrap(True)
        title_col.addWidget(t_lbl)
        title_col.addWidget(s_lbl)
        hdr.addLayout(title_col, 1)

        spec_badge = make_ref_badge(f"EX {key}", COLOR_ACCENT)
        self.academic_badges.append(spec_badge)
        hdr.addWidget(spec_badge)

        preset_btn = QPushButton("Reset Defaults")
        preset_btn.setObjectName("SecondaryButton")
        preset_btn.clicked.connect(lambda _=False, k=key: self._apply_bpic17_rework_preset(k))
        hdr.addWidget(preset_btn)

        run_btn = QPushButton(button_label)
        apply_hard_shadow(run_btn, 3, 3)
        run_btn.clicked.connect(lambda: self._run_analysis(key, callback))
        self.run_buttons[key] = run_btn
        hdr.addWidget(run_btn)
        layout.addLayout(hdr)

        p_card = make_neubrutal_card(shadow_offset=2)
        p_grid = QGridLayout(p_card)
        p_grid.setContentsMargins(12, 8, 12, 8)
        p_grid.setHorizontalSpacing(10)
        p_grid.addWidget(QLabel("Target Activity:"), 0, 0)
        act_combo = QComboBox()
        act_combo.setEditable(True)
        act_combo.setCurrentText("W_Assess potential fraud")
        p_grid.addWidget(act_combo, 0, 1)

        p_grid.addWidget(QLabel("Lifecycle Transition:"), 0, 2)
        lc_combo = QComboBox()
        lc_combo.setEditable(True)
        lc_combo.addItems(["complete", "start", "schedule", "suspend", "resume"])
        lc_combo.setCurrentText("complete")
        p_grid.addWidget(lc_combo, 0, 3)

        p_grid.addWidget(QLabel("Min Occurrences (>=):"), 0, 4)
        min_spin = QSpinBox()
        min_spin.setRange(2, 100)
        min_spin.setValue(2)
        p_grid.addWidget(min_spin, 0, 5)
        p_grid.setColumnStretch(1, 2)
        p_grid.setColumnStretch(3, 1)
        layout.addWidget(p_card)

        self.param_act_combos[key] = act_combo
        self.param_lc_combos[key] = lc_combo
        self.param_min_spins[key] = min_spin

        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(10)
        match_val_label: QLabel | None = None
        act_val_label: QLabel | None = None
        for idx, (k_title, k_init, k_badge, k_color) in enumerate(kpi_defs):
            card, val_lbl, _ = make_kpi_card(k_title, k_init, k_badge, k_color)
            kpi_grid.addWidget(card, 0, idx)
            if idx == 0:
                act_val_label = val_lbl
            elif idx == 2:
                match_val_label = val_lbl
        if act_val_label is not None:
            act_combo.currentTextChanged.connect(
                lambda txt, lbl=act_val_label: set_kpi_value(lbl, txt)
            )
        if match_val_label is not None:
            setattr(self, f"kpi_match_{key.replace('.', '_')}", match_val_label)
        layout.addLayout(kpi_grid)

        res_table = make_table([
            "Cohort Metric",
            "Matching Cases",
            "Total Cases",
            "Share (%)",
            "Avg Cycle Time (days)",
            "Sample Case IDs",
        ])
        res_table.setMaximumHeight(92)
        layout.addWidget(res_table)

        splitter = QSplitter(Qt.Horizontal)

        left_card = make_neubrutal_card(shadow_offset=3)
        lc_layout = QVBoxLayout(left_card)
        lc_layout.setContentsMargins(12, 10, 12, 10)
        lc_lbl = QLabel("Matching Cases & Occurrence Summary (Select row to inspect trace)")
        lc_lbl.setObjectName("SectionHeading")
        lc_layout.addWidget(lc_lbl)
        case_table = make_table(["Cohort", "Case ID", "Evidence Summary"])
        case_table.itemSelectionChanged.connect(lambda k=key: self._on_exercise_case_selected(k))
        lc_layout.addWidget(case_table, 1)

        trace_lbl = QLabel("Selected Case Event Trace")
        trace_lbl.setObjectName("SectionHeading")
        lc_layout.addWidget(trace_lbl)
        trace_table = make_table(["#", "Timestamp (UTC)", "Activity", "Lifecycle", "Resource"])
        lc_layout.addWidget(trace_table, 1)

        right_card = make_neubrutal_card(shadow_offset=3)
        rc_layout = QVBoxLayout(right_card)
        rc_layout.setContentsMargins(12, 10, 12, 10)
        rc_lbl = QLabel("Evidence Events & Diagnostic Warnings")
        rc_lbl.setObjectName("SectionHeading")
        rc_layout.addWidget(rc_lbl)
        ev_box = QTextEdit()
        ev_box.setReadOnly(True)
        ev_box.setPlaceholderText("Run the analysis to view case-level and event-level evidence...")
        rc_layout.addWidget(ev_box, 1)

        splitter.addWidget(left_card)
        splitter.addWidget(right_card)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        self.result_tables[key] = res_table
        self.case_list_tables[key] = case_table
        self.trace_tables[key] = trace_table
        self.evidence_boxes[key] = ev_box
        return page

    # ------------------------------------------------------------------
    # Page 6: Event Sequence
    # ------------------------------------------------------------------
    def _build_sequence_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        hdr = QHBoxLayout()
        title_col = QVBoxLayout()
        t_lbl = QLabel("Event Sequence & Behavioral Flow Analysis")
        t_lbl.setObjectName("PageTitle")
        s_lbl = QLabel(
            "Analyze eventually-follows ordering between any two activities (Position i followed later by Position j > i), "
            "custom rule filters, and directly-follows transitions."
        )
        s_lbl.setObjectName("PageSubtitle")
        s_lbl.setWordWrap(True)
        title_col.addWidget(t_lbl)
        title_col.addWidget(s_lbl)
        hdr.addLayout(title_col, 1)

        seq_badge = make_ref_badge("EX 11.22", COLOR_ACCENT)
        self.academic_badges.append(seq_badge)
        hdr.addWidget(seq_badge)

        preset_btn = make_button("Reset Defaults", variant="secondary")
        preset_btn.clicked.connect(self._apply_bpic17_sequence_preset)
        hdr.addWidget(preset_btn)

        run_btn = make_button("Run Sequence Analysis", variant="primary")
        apply_hard_shadow(run_btn, 3, 3)
        run_btn.clicked.connect(
            lambda: self._run_analysis(
                "11.22",
                lambda: self.service.run_1122(
                    first_activity=self.seq_first_combo.currentText(),
                    second_activity=self.seq_second_combo.currentText(),
                ),
            )
        )
        self.run_buttons["11.22"] = run_btn
        hdr.addWidget(run_btn)
        layout.addLayout(hdr)

        tabs = QTabWidget()

        # Tab 1: Eventually-Follows Sequence (Exercise 11.22)
        tab_1122 = QWidget()
        t_layout = QVBoxLayout(tab_1122)
        t_layout.setContentsMargins(12, 10, 12, 10)
        t_layout.setSpacing(8)

        seq_param_card = make_neubrutal_card(shadow_offset=2)
        seq_grid = QGridLayout(seq_param_card)
        seq_grid.setContentsMargins(12, 8, 12, 8)
        seq_grid.setHorizontalSpacing(10)
        seq_grid.addWidget(QLabel("Preceding Activity (Step i):"), 0, 0)
        self.seq_first_combo = QComboBox()
        self.seq_first_combo.setEditable(True)
        self.seq_first_combo.setCurrentText("O_Cancelled")
        seq_grid.addWidget(self.seq_first_combo, 0, 1)

        seq_grid.addWidget(QLabel("Eventually Followed By (Step j > i):"), 0, 2)
        self.seq_second_combo = QComboBox()
        self.seq_second_combo.setEditable(True)
        self.seq_second_combo.setCurrentText("O_Accepted")
        seq_grid.addWidget(self.seq_second_combo, 0, 3)
        seq_grid.setColumnStretch(1, 1)
        seq_grid.setColumnStretch(3, 1)
        t_layout.addWidget(seq_param_card)

        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(10)
        k1, self.seq_first_kpi, _ = make_kpi_card("Preceding Event (i)", "O_Cancelled", "STEP 1", COLOR_DANGER)
        k2, self.seq_second_kpi, _ = make_kpi_card("Subsequent Event (j > i)", "O_Accepted", "STEP 2", COLOR_SUCCESS)
        k3, self.seq_match_val, _ = make_kpi_card("Matching Cases", "—", "SEQUENCE", COLOR_ACCENT)
        k4, self.seq_pct_val, _ = make_kpi_card("Share of Total Log", "—", "PERCENTAGE", COLOR_ACCENT)
        self.seq_first_combo.currentTextChanged.connect(
            lambda txt: set_kpi_value(self.seq_first_kpi, txt)
        )
        self.seq_second_combo.currentTextChanged.connect(
            lambda txt: set_kpi_value(self.seq_second_kpi, txt)
        )
        kpi_grid.addWidget(k1, 0, 0)
        kpi_grid.addWidget(k2, 0, 1)
        kpi_grid.addWidget(k3, 0, 2)
        kpi_grid.addWidget(k4, 0, 3)
        t_layout.addLayout(kpi_grid)

        res_table = make_table([
            "Cohort Metric",
            "Matching Cases",
            "Total Cases",
            "Share (%)",
            "Avg Cycle Time (days)",
            "Sample Case IDs",
        ])
        res_table.setMaximumHeight(90)
        t_layout.addWidget(res_table)

        split = QSplitter(Qt.Horizontal)
        left_w = QWidget()
        lw_l = QVBoxLayout(left_w)
        lw_l.setContentsMargins(0, 0, 4, 0)
        lw_l.addWidget(QLabel("Matching Cases (Step i -> ... -> Step j):"))
        case_table = make_table(["Cohort", "Case ID", "Ordered Event Pair Timeline"])
        case_table.itemSelectionChanged.connect(lambda: self._on_exercise_case_selected("11.22"))
        lw_l.addWidget(case_table, 1)
        lw_l.addWidget(QLabel("Selected Case Event Trace:"))
        trace_table = make_table(["#", "Timestamp (UTC)", "Activity", "Lifecycle", "Resource"])
        lw_l.addWidget(trace_table, 1)

        right_w = QWidget()
        rw_l = QVBoxLayout(right_w)
        rw_l.setContentsMargins(4, 0, 0, 0)
        rw_l.addWidget(QLabel("Ordered Event Pair Evidence:"))
        ev_box = QTextEdit()
        ev_box.setReadOnly(True)
        rw_l.addWidget(ev_box, 1)

        split.addWidget(left_w)
        split.addWidget(right_w)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        t_layout.addWidget(split, 1)

        self.result_tables["11.22"] = res_table
        self.case_list_tables["11.22"] = case_table
        self.trace_tables["11.22"] = trace_table
        self.evidence_boxes["11.22"] = ev_box
        tabs.addTab(tab_1122, "Eventually-Follows Sequence")

        # Tab 2: Custom Rule & Filter Builder
        tab_cf = QWidget()
        cf_layout = QVBoxLayout(tab_cf)
        cf_layout.setContentsMargins(12, 10, 12, 10)
        cf_layout.setSpacing(8)

        form_grid = QGridLayout()
        form_grid.setSpacing(8)
        form_grid.addWidget(QLabel("Rule Pattern:"), 0, 0)
        self.cf_type_combo = QComboBox()
        self.cf_type_combo.addItem("Contains (At least 1 of Activity A)", "contains")
        self.cf_type_combo.addItem("Endpoint (First / Last Event = A)", "endpoint")
        self.cf_type_combo.addItem("Minimum Occurrence (>= N of Activity A)", "minimum_occurrence")
        self.cf_type_combo.addItem("Same Resource (>= N of A by Same Resource)", "same_resource")
        self.cf_type_combo.addItem("Eventually Follows (A followed later by B)", "eventually_follows")
        form_grid.addWidget(self.cf_type_combo, 0, 1)

        form_grid.addWidget(QLabel("Activity A:"), 0, 2)
        self.cf_act_a_combo = QComboBox()
        self.cf_act_a_combo.setEditable(True)
        form_grid.addWidget(self.cf_act_a_combo, 0, 3)

        form_grid.addWidget(QLabel("Activity B:"), 0, 4)
        self.cf_act_b_combo = QComboBox()
        self.cf_act_b_combo.setEditable(True)
        form_grid.addWidget(self.cf_act_b_combo, 0, 5)

        form_grid.addWidget(QLabel("Min Count (N):"), 1, 0)
        self.cf_min_spin = QSpinBox()
        self.cf_min_spin.setRange(1, 100)
        self.cf_min_spin.setValue(2)
        form_grid.addWidget(self.cf_min_spin, 1, 1)

        form_grid.addWidget(QLabel("Lifecycle:"), 1, 2)
        self.cf_lifecycle_combo = QComboBox()
        self.cf_lifecycle_combo.setEditable(True)
        self.cf_lifecycle_combo.addItems(["all", "complete", "start", "schedule", "suspend", "resume"])
        form_grid.addWidget(self.cf_lifecycle_combo, 1, 3)

        form_grid.addWidget(QLabel("Endpoint:"), 1, 4)
        self.cf_endpoint_combo = QComboBox()
        self.cf_endpoint_combo.addItem("Last Event (End)", "end")
        self.cf_endpoint_combo.addItem("First Event (Start)", "start")
        form_grid.addWidget(self.cf_endpoint_combo, 1, 5)

        self.cf_run_btn = make_button("Evaluate Custom Rule", variant="accent")
        self.cf_run_btn.clicked.connect(self._run_custom_filter_analysis)
        form_grid.addWidget(self.cf_run_btn, 0, 6, 2, 1)
        cf_layout.addLayout(form_grid)

        self.cf_result_table = make_table([
            "Rule ID",
            "Rule Title",
            "Matching Cases",
            "Total Cases",
            "Share (%)",
            "Avg Cycle Time (days)",
        ])
        self.cf_result_table.setMaximumHeight(90)
        cf_layout.addWidget(self.cf_result_table)

        cf_cases_lbl = QLabel("Matching Cases (Select any row to inspect full trace in Trace Inspector)")
        cf_cases_lbl.setObjectName("SectionHeading")
        cf_layout.addWidget(cf_cases_lbl)

        self.cf_case_table = make_table([
            "Case ID",
            "Rule Match Summary",
        ])
        self.cf_case_table.itemSelectionChanged.connect(self._on_custom_case_selected)
        cf_layout.addWidget(self.cf_case_table, 1)

        # Hidden dummy box for backward compatibility
        self.cf_evidence_box = QTextEdit()
        self.cf_evidence_box.setVisible(False)
        tabs.addTab(tab_cf, "Custom Rule & Filter Builder")

        # Tab 3: Directly-Follows Graph (Full-Width Disco / React-Flow Activity Map + Toggleable Table Drawer)
        tab_dfg = QWidget()
        dfg_layout = QVBoxLayout(tab_dfg)
        dfg_layout.setContentsMargins(12, 10, 12, 10)
        dfg_layout.setSpacing(8)

        dfg_ctrl = QHBoxLayout()
        dfg_ctrl.setSpacing(8)
        dfg_ctrl.addWidget(QLabel("Top-N Edges:"))
        self.dfg_top_spin = QSpinBox()
        self.dfg_top_spin.setRange(5, 80)
        self.dfg_top_spin.setValue(18)
        dfg_ctrl.addWidget(self.dfg_top_spin)

        dfg_ctrl.addWidget(QLabel("Min Freq:"))
        self.dfg_min_edge_spin = QSpinBox()
        self.dfg_min_edge_spin.setRange(1, 500_000)
        self.dfg_min_edge_spin.setValue(1)
        self.dfg_min_edge_spin.valueChanged.connect(lambda _: self._render_dfg_visual(self.latest_dfg_edges))
        dfg_ctrl.addWidget(self.dfg_min_edge_spin)

        self.dfg_self_loop_chk = QCheckBox("Self-Loops (A -> A)")
        self.dfg_self_loop_chk.setChecked(False)
        self.dfg_self_loop_chk.toggled.connect(lambda _: self._run_simple_dfg_analysis())
        dfg_ctrl.addWidget(self.dfg_self_loop_chk)

        dfg_ctrl.addWidget(QLabel("Mode:"))
        self.dfg_view_combo = QComboBox()
        self.dfg_view_combo.addItem("Performance — Bottleneck Map (Disco)", "performance")
        self.dfg_view_combo.addItem("Frequency — Case Volume Map", "frequency")
        self.dfg_view_combo.currentIndexChanged.connect(
            lambda _: self._render_dfg_visual(self.latest_dfg_edges)
        )
        dfg_ctrl.addWidget(self.dfg_view_combo)

        self.dfg_dark_chk = QCheckBox("Dark Canvas")
        self.dfg_dark_chk.setChecked(False)
        self.dfg_dark_chk.toggled.connect(lambda _: self._render_dfg_visual(self.latest_dfg_edges))
        dfg_ctrl.addWidget(self.dfg_dark_chk)

        self.dfg_animate_btn = make_button(
            "▶ Animate Flow", variant="success", compact=True, tooltip="Play/Pause Disco-style Live Token Flow Animation"
        )
        self.dfg_animate_btn.setCheckable(True)
        self.dfg_animate_btn.toggled.connect(self._toggle_dfg_animation)
        dfg_ctrl.addWidget(self.dfg_animate_btn)

        self.dfg_speed_combo = QComboBox()
        self.dfg_speed_combo.addItem("0.5x", 0.5)
        self.dfg_speed_combo.addItem("1x", 1.0)
        self.dfg_speed_combo.addItem("2x", 2.0)
        self.dfg_speed_combo.addItem("4x", 4.0)
        self.dfg_speed_combo.setCurrentIndex(1)
        self.dfg_speed_combo.setFixedWidth(68)
        self.dfg_speed_combo.currentIndexChanged.connect(self._on_dfg_speed_changed)
        dfg_ctrl.addWidget(self.dfg_speed_combo)

        zoom_in_btn = make_button("Zoom +", variant="secondary", compact=True, tooltip="Zoom In Process Map")
        zoom_out_btn = make_button("Zoom −", variant="secondary", compact=True, tooltip="Zoom Out Process Map")
        fit_btn = make_button("Fit Map", variant="secondary", compact=True, tooltip="Fit Entire Map on Screen")

        self.dfg_toggle_table_btn = make_button(
            "Edge Table", variant="secondary", compact=True, tooltip="Show/Hide Transition Table"
        )
        self.dfg_toggle_table_btn.setCheckable(True)
        self.dfg_toggle_table_btn.setChecked(False)

        self.dfg_run_btn = make_button("▶ Run DFG", variant="accent", compact=True)
        self.dfg_run_btn.clicked.connect(self._run_simple_dfg_analysis)

        dfg_ctrl.addWidget(zoom_in_btn)
        dfg_ctrl.addWidget(zoom_out_btn)
        dfg_ctrl.addWidget(fit_btn)
        dfg_ctrl.addWidget(self.dfg_toggle_table_btn)
        dfg_ctrl.addWidget(self.dfg_run_btn)
        dfg_ctrl.addStretch(1)
        dfg_layout.addLayout(dfg_ctrl)

        self.dfg_stats_label = QLabel("Directly-Follows Activity Map — Click '▶ Run DFG' to render full process graph")
        self.dfg_stats_label.setObjectName("SectionHeading")
        dfg_layout.addWidget(self.dfg_stats_label)

        # Full-Width Interactive Disco / React-Flow Top-to-Bottom Process Map Canvas
        self.dfg_interactive_view = DfgInteractiveCanvas()
        zoom_in_btn.clicked.connect(self.dfg_interactive_view.zoom_in)
        zoom_out_btn.clicked.connect(self.dfg_interactive_view.zoom_out)
        fit_btn.clicked.connect(self.dfg_interactive_view.reset_fit)
        dfg_layout.addWidget(self.dfg_interactive_view, 4)

        # Collapsible Bottom Transition Table (hidden by default so the Process Map gets 100% full width & height!)
        self.dfg_table = make_table([
            "Source Activity (A)",
            "Target Activity (B)",
            "Events (Cases)",
            "Avg Duration (h)",
        ])
        self.dfg_table.setMaximumHeight(165)
        self.dfg_table.setVisible(False)
        self.dfg_toggle_table_btn.toggled.connect(self.dfg_table.setVisible)
        dfg_layout.addWidget(self.dfg_table, 1)

        # Keep dummy figure/canvas attributes so any existing cleanup references remain safe
        self.dfg_figure = Figure(figsize=(2, 2))
        self.dfg_canvas = FigureCanvas(self.dfg_figure)

        tabs.addTab(tab_dfg, "Directly-Follows Graph (Activity Map)")

        layout.addWidget(tabs, 1)
        return page

    # ------------------------------------------------------------------
    # Page 7: Case Explorer
    # ------------------------------------------------------------------
    def _build_case_explorer_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        hdr = QHBoxLayout()
        title_col = QVBoxLayout()
        t_lbl = QLabel("Case Explorer & Event Timeline")
        t_lbl.setObjectName("PageTitle")
        s_lbl = QLabel(
            "Inspect individual cases: event count, start/end timestamps, full cycle time, "
            "and chronological event trace."
        )
        s_lbl.setObjectName("PageSubtitle")
        title_col.addWidget(t_lbl)
        title_col.addWidget(s_lbl)
        hdr.addLayout(title_col, 1)
        hdr.addWidget(make_ref_badge("TRACE EXPLORER", COLOR_SUCCESS))
        layout.addLayout(hdr)

        search_card = make_neubrutal_card(shadow_offset=3)
        search_row = QHBoxLayout(search_card)
        search_row.setContentsMargins(12, 8, 12, 8)
        self.case_input = QLineEdit()
        self.case_input.setPlaceholderText("Filter by Case ID (press Enter or click Search)...")
        self.case_input.returnPressed.connect(self._search_case)

        self.case_filter_combo = QComboBox()
        self.case_filter_combo.addItem("All Cases in Active Log", "ALL")
        for code, desc in [
            ("11.7C", "Positive Outcome Cohort"),
            ("11.7D", "Negative Outcome Cohort"),
            ("11.7E", "Terminal Cancelled Cohort"),
            ("11.15", "Repeated Activity Rework Cohort"),
            ("11.18", "Same-Resource Rework Cohort"),
            ("11.22", "Eventually-Follows Sequence Cohort"),
            ("11.10-FAST", "Fast Throughput Cohort (< Threshold)"),
            ("11.10-SLOW", "Slow Throughput Cohort (>= Threshold)"),
        ]:
            self.case_filter_combo.addItem(desc, code)
        self.case_filter_combo.currentIndexChanged.connect(lambda _: self._search_case())

        self.case_search_button = QPushButton("Search Cases")
        self.case_search_button.setObjectName("AccentButton")
        self.case_search_button.clicked.connect(self._search_case)

        search_row.addWidget(QLabel("Case Search:"))
        search_row.addWidget(self.case_input, 1)
        search_row.addWidget(QLabel("Cohort Filter:"))
        search_row.addWidget(self.case_filter_combo)
        search_row.addWidget(self.case_search_button)
        layout.addWidget(search_card)

        self.case_search_status = QLabel("Import an event log to browse cases and timelines.")
        self.case_search_status.setStyleSheet("font-weight: 700;")
        layout.addWidget(self.case_search_status)

        self.case_duration_table = make_table([
            "Case ID",
            "Event Count",
            "First Event (UTC)",
            "Last Event (UTC)",
            "Cycle Time (days)",
        ])
        self.case_duration_table.itemSelectionChanged.connect(self._on_case_duration_selected)
        layout.addWidget(self.case_duration_table, 2)

        lower_split = QSplitter(Qt.Horizontal)

        table_card = make_neubrutal_card(shadow_offset=3)
        tc_layout = QVBoxLayout(table_card)
        tc_layout.setContentsMargins(12, 10, 12, 10)
        tc_title = QLabel("Selected Case Event Timeline (Chronological Trace)")
        tc_title.setObjectName("SectionHeading")
        tc_layout.addWidget(tc_title)
        self.case_table = make_table([
            "Timestamp (UTC)",
            "Activity",
            "Lifecycle",
            "Resource",
            "Source Order",
        ])
        tc_layout.addWidget(self.case_table, 1)
        lower_split.addWidget(table_card)

        chart_card = make_neubrutal_card(shadow_offset=3)
        cc_layout = QVBoxLayout(chart_card)
        cc_layout.setContentsMargins(12, 10, 12, 10)
        cc_hdr = QHBoxLayout()
        cc_title = QLabel("Visual Case Timeline Plot")
        cc_title.setObjectName("SectionHeading")
        self.timeline_case_combo = QComboBox()
        self.timeline_case_combo.setEditable(True)
        self.timeline_case_combo.setMinimumWidth(160)
        self.timeline_plot_btn = QPushButton("Plot Timeline")
        self.timeline_plot_btn.setObjectName("SecondaryButton")
        self.timeline_plot_btn.clicked.connect(self._plot_selected_case_timeline)
        cc_hdr.addWidget(cc_title)
        cc_hdr.addStretch(1)
        cc_hdr.addWidget(self.timeline_case_combo)
        cc_hdr.addWidget(self.timeline_plot_btn)
        cc_layout.addLayout(cc_hdr)

        self.tl_figure = Figure(figsize=(5.5, 3.4), tight_layout=True)
        self.tl_canvas = FigureCanvas(self.tl_figure)
        cc_layout.addWidget(self.tl_canvas, 1)
        lower_split.addWidget(chart_card)

        lower_split.setStretchFactor(0, 3)
        lower_split.setStretchFactor(1, 2)
        layout.addWidget(lower_split, 3)
        return page

    # ------------------------------------------------------------------
    # Page 8: Reports & Export
    # ------------------------------------------------------------------
    def _build_reports_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        t_lbl = QLabel("Reports & Evidence Export")
        t_lbl.setObjectName("PageTitle")
        s_lbl = QLabel(
            "Export dynamic analysis summaries, matching Case IDs, and event-level evidence to CSV or PDF reports."
        )
        s_lbl.setObjectName("PageSubtitle")
        layout.addWidget(t_lbl)
        layout.addWidget(s_lbl)

        btn_card = make_neubrutal_card(shadow_offset=3)
        b_layout = QHBoxLayout(btn_card)
        b_layout.setContentsMargins(14, 12, 14, 12)
        b_layout.setSpacing(12)

        self.sidebar_export_button = QPushButton("Export CSV Bundle (analysis_summary.csv + case_evidence.csv)")
        self.sidebar_export_button.setObjectName("AccentButton")
        self.sidebar_export_button.setEnabled(False)
        self.sidebar_export_button.clicked.connect(self._export_results)

        self.sidebar_pdf_button = QPushButton("Generate Automated PDF Report")
        self.sidebar_pdf_button.setEnabled(False)
        self.sidebar_pdf_button.clicked.connect(self._export_pdf_report)

        run_all_rep_btn = QPushButton("Run All Analyses Before Export")
        run_all_rep_btn.setObjectName("SecondaryButton")
        run_all_rep_btn.clicked.connect(self._run_all_analyses)

        b_layout.addWidget(self.sidebar_export_button)
        b_layout.addWidget(self.sidebar_pdf_button)
        b_layout.addWidget(run_all_rep_btn)
        b_layout.addStretch(1)
        layout.addWidget(btn_card)

        preview_card = make_neubrutal_card(shadow_offset=3)
        p_layout = QVBoxLayout(preview_card)
        p_layout.setContentsMargins(14, 12, 14, 12)
        p_title = QLabel("Exportable Analysis Results Queue")
        p_title.setObjectName("SectionHeading")
        p_layout.addWidget(p_title)

        self.reports_table = make_table([
            "Metric ID",
            "Analytical Module",
            "Matching Cases",
            "Total Cases",
            "Share (%)",
            "Mean Cycle Time (days)",
            "Evidence Records",
        ])
        p_layout.addWidget(self.reports_table, 1)
        layout.addWidget(preview_card, 1)
        return page

    # ------------------------------------------------------------------
    # Page 9: Settings
    # ------------------------------------------------------------------
    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        t_lbl = QLabel("Application & Workspace Settings")
        t_lbl.setObjectName("PageTitle")
        s_lbl = QLabel("Configure throughput thresholds, workspace panels, and deterministic event log policies.")
        s_lbl.setObjectName("PageSubtitle")
        layout.addWidget(t_lbl)
        layout.addWidget(s_lbl)

        card = make_neubrutal_card(shadow_offset=3)
        grid = QGridLayout(card)
        grid.setContentsMargins(18, 18, 18, 18)
        grid.setSpacing(14)

        grid.addWidget(QLabel("Fast vs Slow Default Threshold (Days):"), 0, 0)
        self.set_threshold_spin = QDoubleSpinBox()
        self.set_threshold_spin.setRange(1.0, 365.0)
        self.set_threshold_spin.setValue(45.0)
        self.set_threshold_spin.valueChanged.connect(self.fast_slow_spin.setValue)
        grid.addWidget(self.set_threshold_spin, 0, 1)

        grid.addWidget(QLabel("Timestamp Tie-Breaker Policy:"), 1, 0)
        policy_lbl = QLabel("Deterministic (case_id -> time:timestamp UTC -> original XES source_order via mergesort)")
        policy_lbl.setStyleSheet("font-weight: 800;")
        grid.addWidget(policy_lbl, 1, 1)

        grid.addWidget(QLabel("Cycle Time Calculation Policy:"), 2, 0)
        ct_lbl = QLabel("Full Original Trace Duration: max(timestamp) - min(timestamp) without event truncation")
        ct_lbl.setStyleSheet("font-weight: 800;")
        grid.addWidget(ct_lbl, 2, 1)

        grid.addWidget(QLabel("Missing Lifecycle / Resource Policy:"), 3, 0)
        miss_lbl = QLabel("Strict Validation — Never guess 'complete' status or group empty resources together")
        miss_lbl.setStyleSheet("font-weight: 800;")
        grid.addWidget(miss_lbl, 3, 1)

        toggle_sb_btn = QPushButton("Toggle Collapsible Sidebar")
        toggle_sb_btn.setObjectName("SecondaryButton")
        toggle_sb_btn.clicked.connect(self.toggle_sidebar)
        grid.addWidget(toggle_sb_btn, 4, 0)

        toggle_ctx_btn = QPushButton("Toggle Trace Inspector Panel")
        toggle_ctx_btn.setObjectName("SecondaryButton")
        toggle_ctx_btn.clicked.connect(self.toggle_context_panel)
        grid.addWidget(toggle_ctx_btn, 4, 1)

        layout.addWidget(card)
        layout.addStretch(1)
        return page

    # ------------------------------------------------------------------
    # Page 10: About
    # ------------------------------------------------------------------
    def _build_about_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        t_lbl = QLabel("About Tracely")
        t_lbl.setObjectName("PageTitle")
        s_lbl = QLabel("Universal Desktop Process Mining & Event Log Intelligence Platform.")
        s_lbl.setObjectName("PageSubtitle")
        layout.addWidget(t_lbl)
        layout.addWidget(s_lbl)

        def pkg_ver(name: str) -> str:
            try:
                return version(name)
            except PackageNotFoundError:
                return "not installed"

        card = make_neubrutal_card(shadow_offset=3)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(18, 18, 18, 18)
        c_layout.setSpacing(10)

        info_html = (
            "<h3>Tracely — Process Mining Desktop Suite (v0.1.0)</h3>"
            "<p>Built with a <b>Professional Neubrutalism + Modern SaaS Analytics</b> design language "
            "for high-precision, deterministic analysis of IEEE XES event logs with full case-level "
            "and event-level evidence traceability.</p>"
            "<h4>Core Analytical Capabilities:</h4>"
            "<ul>"
            "<li><b>Process Outcomes</b> &rarr; Case volume, full-trace cycle time, outcome cohorts, and Fast vs Slow segmentation</li>"
            "<li><b>Rework Analysis</b> &rarr; Repeated activity execution filtered by lifecycle transition</li>"
            "<li><b>Resource Analysis</b> &rarr; Repeated activity execution by the same identified organizational resource</li>"
            "<li><b>Event Sequence</b> &rarr; Eventually-follows behavioral patterns, custom rule builder, and Directly-Follows Graph</li>"
            "</ul>"
            f"<p><b>Runtime Stack:</b> Python {sys.version.split()[0]} &bull; "
            f"PM4Py {pkg_ver('pm4py')} &bull; Pandas {pkg_ver('pandas')} &bull; PySide6 {pkg_ver('PySide6')}</p>"
        )
        about_lbl = QLabel(info_html)
        about_lbl.setWordWrap(True)
        about_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        c_layout.addWidget(about_lbl)

        self.about_button = QPushButton("Show System Version Dialog")
        self.about_button.setObjectName("SecondaryButton")
        self.about_button.clicked.connect(self._show_about)
        c_layout.addWidget(self.about_button, 0, Qt.AlignLeft)

        layout.addWidget(card)
        layout.addStretch(1)
        return page

    # ------------------------------------------------------------------
    # Core Event Handlers & Service Integration
    # ------------------------------------------------------------------
    def _on_dashboard_row_activated(self, row: int, _column: int) -> None:
        code_item = self.dashboard_table.item(row, 0)
        if code_item is None:
            return
        code = code_item.data(Qt.UserRole) or code_item.text()
        if str(code).startswith("11.7") or str(code).startswith("11.10"):
            self.navigate_to(self.PAGE_OUTCOMES)
        elif code == "11.15":
            self.navigate_to(self.PAGE_REWORK)
        elif code == "11.18":
            self.navigate_to(self.PAGE_RESOURCE)
        elif code == "11.22" or str(code).startswith("CUSTOM"):
            self.navigate_to(self.PAGE_SEQUENCE)

    def _populate_schema_table(self, available_attrs: list[str]) -> None:
        available_set = set(available_attrs)
        rows = [
            ("case_id", "case:concept:name", "Mandatory (Case Identification)"),
            ("activity", "concept:name", "Mandatory (Activity & Flow Analysis)"),
            ("timestamp", "time:timestamp", "Mandatory (Cycle Time & Ordering)"),
            ("lifecycle", "lifecycle:transition", "Required for Lifecycle Rework Analysis"),
            ("resource", "org:resource", "Required for Organizational Resource Analysis"),
        ]
        self.schema_table.setRowCount(len(rows))
        for r_idx, (internal_name, xes_name, req_text) in enumerate(rows):
            if not self.service.is_loaded:
                status = "Awaiting Import"
            elif internal_name in ("case_id", "activity", "timestamp") or internal_name in available_set:
                status = "VALIDATED"
            else:
                status = "MISSING / EMPTY"
            for c_idx, val in enumerate((internal_name, xes_name, req_text, status)):
                self.schema_table.setItem(r_idx, c_idx, QTableWidgetItem(val))
        autofit_table_columns(self.schema_table)

    def _reset_analysis_views(self) -> None:
        self.latest_results.clear()
        self.latest_fast_slow = None
        self._update_export_buttons()
        self.dashboard_table.setRowCount(0)
        self.reports_table.setRowCount(0)
        for key in self.result_tables:
            self.result_tables[key].setRowCount(0)
            self.evidence_boxes[key].clear()
            self.case_list_tables[key].setRowCount(0)
            self.trace_tables[key].setRowCount(0)
        self.case_duration_table.setRowCount(0)
        self.case_table.setRowCount(0)
        self.ctx_trace_table.setRowCount(0)
        self.ctx_evidence_text.clear()
        self.ctx_case_badge.setText("NO CASE")
        self.fast_slow_table.setRowCount(0)
        self.fast_slow_evidence_box.clear()
        self.cf_result_table.setRowCount(0)
        self.cf_evidence_box.clear()
        self.dfg_table.setRowCount(0)
        self.out_total_val.setText("—")
        self.out_accepted_val.setText("—")
        self.out_refused_val.setText("—")
        self.out_cancelled_val.setText("—")
        self.out_cycle_val.setText("—")
        self.seq_match_val.setText("—")
        self.seq_pct_val.setText("—")
        if hasattr(self, "kpi_match_11_15"):
            self.kpi_match_11_15.setText("—")
        if hasattr(self, "kpi_match_11_18"):
            self.kpi_match_11_18.setText("—")

    def _update_export_buttons(self) -> None:
        has_results = bool(self.latest_results)
        self.export_button.setEnabled(has_results)
        self.sidebar_export_button.setEnabled(has_results)
        self.export_pdf_button.setEnabled(has_results)
        self.sidebar_pdf_button.setEnabled(has_results)

    def _choose_xes(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select IEEE XES Event Log",
            str(Path.cwd()),
            "XES Event Log (*.xes *.xes.gz);;All Files (*)",
        )
        if not path:
            return
        self.load_xes_file(path)

    def load_xes_file(self, path: str | Path) -> None:
        self._set_status_busy(f"Loading XES file via PM4Py: {Path(path).name} ...")
        self.open_button.setEnabled(False)
        self._start_worker(lambda: self.service.load_xes(path), self._on_dataset_loaded)

    def _on_dataset_loaded(self, overview: DatasetOverview) -> None:
        self._reset_analysis_views()
        self.overview = overview
        source_text = str(self.service.source_path) if self.service.source_path else "In-Memory DataFrame"
        short_name = self.service.source_path.name if self.service.source_path else "In-Memory Log"
        self.dataset_label.setText(f"ACTIVE LOG: {short_name} ({overview.total_cases:,} cases)")
        self.import_path_edit.setText(source_text)

        mean_text = (
            f"{overview.mean_cycle_time_days:.4f} d"
            if overview.mean_cycle_time_days is not None
            else "—"
        )
        self.dash_cases_val.setText(f"{overview.total_cases:,}")
        self.dash_cases_sub.setText("Unique case identifiers")
        self.dash_events_val.setText(f"{overview.total_events:,}")
        self.dash_events_sub.setText(f"{overview.total_events / max(1, overview.total_cases):.1f} events / case avg")
        self.dash_activities_val.setText(f"{overview.unique_activities:,}")
        self.dash_activities_sub.setText("Distinct process activities")
        self.dash_cycle_val.setText(mean_text)
        self.dash_cycle_sub.setText("Full trace duration average")

        self.ov_cases_val.setText(f"{overview.total_cases:,}")
        self.ov_events_val.setText(f"{overview.total_events:,}")
        self.ov_activities_val.setText(f"{overview.unique_activities:,}")
        self.ov_cycle_val.setText(mean_text)

        attrs_str = ", ".join(overview.available_attributes) if overview.available_attributes else "none"
        self.empty_state_banner.setObjectName("SuccessBanner")
        self.empty_state_banner.style().unpolish(self.empty_state_banner)
        self.empty_state_banner.style().polish(self.empty_state_banner)
        self.dash_status_text.setText(
            f"ACTIVE EVENT LOG: {source_text}  •  "
            f"Time Span (UTC): {overview.first_timestamp or '-'} to {overview.last_timestamp or '-'}  •  "
            f"Optional Attributes: {attrs_str}"
        )
        self.import_details_label.setText(
            f"Loaded: {source_text}\n"
            f"Cases: {overview.total_cases:,} | Events: {overview.total_events:,} | "
            f"Activities: {overview.unique_activities:,} | Mean Cycle Time: {mean_text}\n"
            f"Time Range (UTC): {overview.first_timestamp or '-'} — {overview.last_timestamp or '-'}"
        )
        self.overview_label.setText(
            f"Time Range (UTC): {overview.first_timestamp or '-'} to {overview.last_timestamp or '-'}  |  "
            f"Attributes: {attrs_str}"
        )

        self._populate_schema_table(overview.available_attributes)

        total_ev = max(1, overview.total_events)
        self.activity_table.setRowCount(len(overview.activity_frequencies))
        act_names = []
        for row, item in enumerate(overview.activity_frequencies):
            act_name = str(item["activity"])
            act_names.append(act_name)
            freq = int(item["frequency"])
            pct = freq / total_ev * 100.0
            self.activity_table.setItem(row, 0, QTableWidgetItem(act_name))
            self.activity_table.setItem(row, 1, QTableWidgetItem(f"{freq:,}"))
            self.activity_table.setItem(row, 2, QTableWidgetItem(f"{pct:.2f}%"))
        autofit_table_columns(self.activity_table)

        self.cf_act_a_combo.clear()
        self.cf_act_b_combo.clear()
        self.cf_act_a_combo.addItems(act_names)
        self.cf_act_b_combo.addItems(act_names)

        self._populate_activity_selector(self.out_acc_combo, act_names, "O_Accepted", fallback_idx=0)
        self._populate_activity_selector(self.out_ref_combo, act_names, "O_Refused", fallback_idx=min(1, len(act_names) - 1))
        self._populate_activity_selector(self.out_can_combo, act_names, "O_Cancelled", fallback_idx=min(2, len(act_names) - 1))
        for k in ("11.15", "11.18"):
            if k in self.param_act_combos:
                self._populate_activity_selector(
                    self.param_act_combos[k], act_names, "W_Assess potential fraud", fallback_idx=0
                )
        self._populate_activity_selector(self.seq_first_combo, act_names, "O_Cancelled", fallback_idx=0)
        self._populate_activity_selector(self.seq_second_combo, act_names, "O_Accepted", fallback_idx=min(1, len(act_names) - 1))

        sample_cases = [c["case_id"] for c in self.service.search_case_durations("", limit=200)]
        self.timeline_case_combo.clear()
        self.timeline_case_combo.addItems(sample_cases)

        self._set_analysis_enabled(True)
        self._search_case()
        self._plot_duration_distribution()
        if sample_cases:
            self._plot_selected_case_timeline()
        # Automatically compute and render the DFG Process Map upon dataset load so it's never blank
        try:
            top_n = int(self.dfg_top_spin.value())
            include_loops = bool(self.dfg_self_loop_chk.isChecked())
            self._on_simple_dfg_finished(
                self.service.run_simple_dfg(top_n=top_n, include_self_loops=include_loops)
            )
        except Exception:
            pass
        self._refresh_projects_table()
        self.sidebar_engine_lbl.setText(f"Loaded • {overview.total_cases:,} cases")
        self._set_status_ready(
            f"Event log loaded ({overview.total_cases:,} cases, {overview.total_events:,} events)."
        )

    def _populate_activity_selector(
        self,
        combo: QComboBox,
        activities: list[str],
        preferred: str,
        fallback_idx: int = 0,
    ) -> None:
        combo.clear()
        combo.addItems(activities)
        pref_cf = preferred.casefold()
        for act in activities:
            if act.casefold() == pref_cf:
                combo.setCurrentText(act)
                return
        if activities and 0 <= fallback_idx < len(activities):
            combo.setCurrentText(activities[fallback_idx])
        else:
            combo.setCurrentText(preferred)

    def _apply_bpic17_outcomes_preset(self) -> None:
        acts = [self.out_acc_combo.itemText(i) for i in range(self.out_acc_combo.count())]
        self._populate_activity_selector(self.out_acc_combo, acts, "O_Accepted", 0)
        self._populate_activity_selector(self.out_ref_combo, acts, "O_Refused", min(1, len(acts) - 1))
        self._populate_activity_selector(self.out_can_combo, acts, "O_Cancelled", min(2, len(acts) - 1))

    def _apply_bpic17_rework_preset(self, key: str) -> None:
        if key in self.param_act_combos:
            combo = self.param_act_combos[key]
            acts = [combo.itemText(i) for i in range(combo.count())]
            self._populate_activity_selector(combo, acts, "W_Assess potential fraud", 0)
            self.param_lc_combos[key].setCurrentText("complete")
            self.param_min_spins[key].setValue(2)

    def _apply_bpic17_sequence_preset(self) -> None:
        acts = [self.seq_first_combo.itemText(i) for i in range(self.seq_first_combo.count())]
        self._populate_activity_selector(self.seq_first_combo, acts, "O_Cancelled", 0)
        self._populate_activity_selector(self.seq_second_combo, acts, "O_Accepted", min(1, len(acts) - 1))

    def _run_analysis(self, key: str, callback: Callable[[], Any]) -> None:
        if not self.service.is_loaded:
            QMessageBox.warning(self, "No Active Event Log", "Please import an XES file first.")
            return
        self._set_status_busy("Running process analysis...")
        self._start_worker(callback, lambda result: self._on_analysis_finished(key, result))

    def _run_all_analyses(self) -> None:
        if not self.service.is_loaded:
            QMessageBox.warning(self, "No Active Event Log", "Please import an XES file first.")
            return

        threshold = float(self.fast_slow_spin.value())
        acc_act = self.out_acc_combo.currentText()
        ref_act = self.out_ref_combo.currentText()
        can_act = self.out_can_combo.currentText()
        rw_act = self.param_act_combos["11.15"].currentText() if "11.15" in self.param_act_combos else "W_Assess potential fraud"
        rw_lc = self.param_lc_combos["11.15"].currentText() if "11.15" in self.param_lc_combos else "complete"
        rw_min = self.param_min_spins["11.15"].value() if "11.15" in self.param_min_spins else 2
        res_act = self.param_act_combos["11.18"].currentText() if "11.18" in self.param_act_combos else "W_Assess potential fraud"
        res_lc = self.param_lc_combos["11.18"].currentText() if "11.18" in self.param_lc_combos else "complete"
        res_min = self.param_min_spins["11.18"].value() if "11.18" in self.param_min_spins else 2
        seq_a = self.seq_first_combo.currentText()
        seq_b = self.seq_second_combo.currentText()

        def _batch_task() -> dict[str, Any]:
            batch: dict[str, Any] = {
                "11.7": self.service.run_117(
                    accepted_activity=acc_act,
                    refused_activity=ref_act,
                    cancelled_activity=can_act,
                )
            }
            errors: list[str] = []
            for key, fn in (
                ("11.15", lambda: self.service.run_1115(rw_act, rw_min, rw_lc)),
                ("11.18", lambda: self.service.run_1118(res_act, res_min, res_lc)),
                ("11.22", lambda: self.service.run_1122(seq_a, seq_b)),
            ):
                try:
                    batch[key] = fn()
                except Exception as exc:
                    errors.append(str(exc))
            try:
                batch["fast_slow"] = self.service.run_fast_slow(threshold_days=threshold)
            except Exception as exc:
                errors.append(str(exc))
            batch["_errors"] = errors
            return batch

        self._set_status_busy("Running all analytical modules (Outcomes, Rework, Resource, Sequence)...")
        self._start_worker(_batch_task, self._on_all_analyses_finished)

    def _on_all_analyses_finished(self, payload: dict[str, Any]) -> None:
        for key in ("11.7", "11.15", "11.18", "11.22"):
            if key in payload:
                self._on_analysis_finished(key, payload[key])
        if "fast_slow" in payload:
            self._on_fast_slow_finished(payload["fast_slow"])
        errors = payload.get("_errors") or []
        if errors:
            QMessageBox.warning(
                self,
                "Attribute Prerequisite Notice",
                "Some analytical modules reported missing prerequisites:\n\n" + "\n".join(errors),
            )
        self._set_status_ready("All analytical modules finished executing.")

    def _display_name_for_code(self, code: str, fallback_title: str = "") -> str:
        base = MODULE_DISPLAY_NAMES.get(code, fallback_title or code)
        if self.show_academic_refs:
            return f"{code} • {base}"
        return base

    def _on_analysis_finished(self, key: str, result: Any) -> None:
        results: list[AnalysisResult] = (
            list(result.values()) if isinstance(result, dict) else [result]
        )
        for item in results:
            self.latest_results[item.code] = item

        if key == "11.7":
            if "11.7A" in self.latest_results:
                self.out_total_val.setText(f"{self.latest_results['11.7A'].count:,}")
            if "11.7B" in self.latest_results and self.latest_results["11.7B"].mean_cycle_time_days is not None:
                self.out_cycle_val.setText(f"{self.latest_results['11.7B'].mean_cycle_time_days:.2f} d")
            if "11.7C" in self.latest_results:
                r = self.latest_results["11.7C"]
                self.out_accepted_val.setText(f"{r.count:,}")
                self.out_accepted_sub.setText(
                    f"Avg cycle: {r.mean_cycle_time_days:.2f} d" if r.mean_cycle_time_days is not None else "Positive cohort"
                )
            if "11.7D" in self.latest_results:
                r = self.latest_results["11.7D"]
                self.out_refused_val.setText(f"{r.count:,}")
                self.out_refused_sub.setText(
                    f"Avg cycle: {r.mean_cycle_time_days:.2f} d" if r.mean_cycle_time_days is not None else "Negative cohort"
                )
            if "11.7E" in self.latest_results:
                r = self.latest_results["11.7E"]
                self.out_cancelled_val.setText(f"{r.count:,}")
                self.out_cancelled_sub.setText(
                    f"Avg cycle: {r.mean_cycle_time_days:.2f} d" if r.mean_cycle_time_days is not None else "Terminal cohort"
                )
        elif key == "11.15" and hasattr(self, "kpi_match_11_15"):
            self.kpi_match_11_15.setText(f"{results[0].count:,}")
        elif key == "11.18" and hasattr(self, "kpi_match_11_18"):
            self.kpi_match_11_18.setText(f"{results[0].count:,}")
        elif key == "11.22":
            self.seq_match_val.setText(f"{results[0].count:,}")
            self.seq_pct_val.setText(
                f"{results[0].percentage:.4f}%" if results[0].percentage is not None else "—"
            )

        table = self.result_tables[key]
        table.setRowCount(len(results))
        evidence_parts: list[str] = []

        for row, item in enumerate(results):
            clean_label = self._display_name_for_code(item.code, item.title)
            first_cell = QTableWidgetItem(clean_label)
            first_cell.setData(Qt.UserRole, item.code)
            table.setItem(row, 0, first_cell)

            other_values = [
                f"{item.count:,}",
                "-" if item.denominator is None else f"{item.denominator:,}",
                "-" if item.percentage is None else f"{item.percentage:.4f}%",
                "-" if item.mean_cycle_time_days is None else f"{item.mean_cycle_time_days:.4f}",
                ", ".join(item.case_ids[:15]) + (" ..." if len(item.case_ids) > 15 else ""),
            ]
            for column, value in enumerate(other_values, start=1):
                table.setItem(row, column, QTableWidgetItem(value))

            pct_str = "-" if item.percentage is None else f"{item.percentage:.2f}%"
            ct_str = "-" if item.mean_cycle_time_days is None else f"{item.mean_cycle_time_days:.4f} days"
            denom_str = "-" if item.denominator is None else f"{item.denominator:,}"
            warn_html = (
                f"<div style='margin-top:4px; color:#991B1B;'><b>Note:</b> {'; '.join(item.warnings)}</div>"
                if item.warnings
                else ""
            )
            evidence_parts.append(
                f"<div style='margin-bottom:12px; padding:10px; border:1.5px solid #171717; border-radius:6px; background:#F7F5EF;'>"
                f"<div style='font-weight:900; font-size:13px; color:#171717;'>{clean_label}</div>"
                f"<div style='margin-top:3px; color:#404040;'><b>Rule:</b> {item.rule}</div>"
                f"<div style='margin-top:4px;'>"
                f"<b>Matching Cases:</b> {item.count:,} &nbsp;|&nbsp; "
                f"<b>Denominator:</b> {denom_str} &nbsp;|&nbsp; "
                f"<b>Share:</b> {pct_str} &nbsp;|&nbsp; "
                f"<b>Avg Cycle Time:</b> {ct_str}"
                f"</div>"
                f"{warn_html}"
                f"</div>"
            )

        autofit_table_columns(table)
        summary_html = (
            "<div style='font-family: Segoe UI, Inter, Arial, sans-serif; font-size: 12.5px;'>"
            + "".join(evidence_parts)
            + "<div style='color:#666666; font-size:11.5px;'>Tip: Click any Case ID row on the left to inspect its full chronological event trace, or use <b>Export CSV / PDF</b> for full dataset evidence.</div>"
            + "</div>"
        )
        self.evidence_boxes[key].setHtml(summary_html)
        self._populate_exercise_case_list(key, results)
        self._refresh_dashboard_table()
        self._update_export_buttons()
        self._set_status_ready("Analysis module completed.")

    def _run_fast_slow_analysis(self) -> None:
        if not self.service.is_loaded:
            return
        threshold = float(self.fast_slow_spin.value())
        self._set_status_busy(f"Running Fast vs Slow segmentation (threshold={threshold:g} days)...")
        self._start_worker(
            lambda: self.service.run_fast_slow(threshold_days=threshold),
            self._on_fast_slow_finished,
        )

    def _on_fast_slow_finished(self, comp: FastSlowComparison) -> None:
        self.latest_fast_slow = comp
        self.latest_results[comp.fast_result.code] = comp.fast_result
        self.latest_results[comp.slow_result.code] = comp.slow_result

        fast_pct = comp.fast_result.percentage or 0.0
        slow_pct = comp.slow_result.percentage or 0.0
        self.fs_fast_count_val.setText(f"{comp.fast_result.count:,} ({fast_pct:.2f}%)")
        self.fs_fast_mean_val.setText(
            f"{comp.fast_result.mean_cycle_time_days:.4f} d"
            if comp.fast_result.mean_cycle_time_days is not None
            else "-"
        )
        self.fs_slow_count_val.setText(f"{comp.slow_result.count:,} ({slow_pct:.2f}%)")
        self.fs_slow_mean_val.setText(
            f"{comp.slow_result.mean_cycle_time_days:.4f} d"
            if comp.slow_result.mean_cycle_time_days is not None
            else "-"
        )

        self.fast_slow_table.setRowCount(len(comp.comparison_metrics))
        for r_idx, row in enumerate(comp.comparison_metrics):
            self.fast_slow_table.setItem(r_idx, 0, QTableWidgetItem(str(row["metric"])))
            self.fast_slow_table.setItem(r_idx, 1, QTableWidgetItem(str(row["fast_cases"])))
            self.fast_slow_table.setItem(r_idx, 2, QTableWidgetItem(str(row["slow_cases"])))
        autofit_table_columns(self.fast_slow_table)

        fast_mean_str = (
            f"{comp.fast_result.mean_cycle_time_days:.2f} days"
            if comp.fast_result.mean_cycle_time_days is not None
            else "-"
        )
        slow_mean_str = (
            f"{comp.slow_result.mean_cycle_time_days:.2f} days"
            if comp.slow_result.mean_cycle_time_days is not None
            else "-"
        )
        self.fast_slow_evidence_box.setHtml(
            f"<div style='font-family: Segoe UI, Inter, Arial, sans-serif; font-size: 12.5px;'>"
            f"<div style='margin-bottom:8px; padding:10px; border:1.5px solid #171717; border-radius:6px; background:#B9E5CC;'>"
            f"<b>Fast Throughput Segment (&lt; {comp.threshold_days:g} days):</b> "
            f"{comp.fast_result.count:,} cases ({fast_pct:.2f}%) &nbsp;|&nbsp; Mean Cycle Time: <b>{fast_mean_str}</b>"
            f"</div>"
            f"<div style='padding:10px; border:1.5px solid #171717; border-radius:6px; background:#EF8B79;'>"
            f"<b>Slow Throughput Segment (&ge; {comp.threshold_days:g} days):</b> "
            f"{comp.slow_result.count:,} cases ({slow_pct:.2f}%) &nbsp;|&nbsp; Mean Cycle Time: <b>{slow_mean_str}</b>"
            f"</div>"
            f"<div style='margin-top:8px; color:#525252; font-size:11.5px;'>Use <b>Case Explorer</b> (Cohort Filter) to inspect individual Fast or Slow case traces.</div>"
            f"</div>"
        )
        self._refresh_dashboard_table()
        self._update_export_buttons()
        self._set_status_ready("Fast vs Slow throughput segmentation completed.")

    def _plot_duration_distribution(self) -> None:
        if not self.service.is_loaded:
            return
        durations = self.service.get_cycle_times_df()
        threshold = float(self.fast_slow_spin.value())

        self.dist_figure.clear()
        ax = self.dist_figure.add_subplot(111)
        ax.set_facecolor(COLOR_BG)
        days = durations["cycle_time_days"].dropna()
        if not days.empty:
            total_c = len(days)
            mean_val = float(days.mean())
            median_val = float(days.median())
            p99 = float(days.quantile(0.99)) if len(days) > 20 else float(days.max())
            upper_clip = max(threshold * 1.35, p99, float(days.max()) if len(days) <= 20 else p99)
            clipped = days.clip(upper=upper_clip)

            bins = min(36, max(8, int(len(clipped) ** 0.5)))
            counts, edges, patches = ax.hist(
                clipped,
                bins=bins,
                edgecolor=COLOR_BORDER,
                linewidth=1.1,
                alpha=0.92,
            )
            for patch, left_edge in zip(patches, edges[:-1]):
                if left_edge >= threshold:
                    patch.set_facecolor(COLOR_DANGER)
                else:
                    patch.set_facecolor(COLOR_PRIMARY)

            fast_cnt = int((days < threshold).sum())
            slow_cnt = total_c - fast_cnt
            ax.axvline(
                threshold,
                color=COLOR_BORDER,
                linestyle="--",
                linewidth=2.0,
                label=f"Threshold {threshold:g}d (Fast: {fast_cnt:,} | Slow: {slow_cnt:,})",
            )
            ax.axvline(
                mean_val,
                color=COLOR_ACCENT,
                linestyle="-",
                linewidth=2.2,
                label=f"Mean: {mean_val:.2f}d | Median: {median_val:.2f}d",
            )
            ax.legend(fontsize=8, facecolor="#FFFFFF", edgecolor=COLOR_BORDER, framealpha=0.95)
        ax.set_title("Case Cycle Time Distribution (Fast < Threshold vs Slow >= Threshold)", fontsize=9.5, fontweight="bold")
        ax.set_xlabel("Cycle Time (Days)", fontsize=8.5, fontweight="bold")
        ax.set_ylabel("Number of Cases", fontsize=8.5, fontweight="bold")
        ax.grid(True, linestyle=":", alpha=0.5)
        self.dist_canvas.draw()

    def _plot_selected_case_timeline(self) -> None:
        if not self.service.is_loaded:
            return
        case_id = self.timeline_case_combo.currentText().strip()
        if not case_id:
            return
        events = get_case_events(self.service.data, case_id)
        self.tl_figure.clear()
        ax = self.tl_figure.add_subplot(111)
        ax.set_facecolor(COLOR_BG)
        if not events:
            ax.text(0.5, 0.5, f"Case '{case_id}' not found", ha="center", va="center", fontweight="bold")
            self.tl_canvas.draw()
            return

        import pandas as pd
        total_events = len(events)
        display_events = events[:30]
        t0 = pd.to_datetime(display_events[0]["timestamp"])
        rel_days = [
            (pd.to_datetime(e["timestamp"]) - t0).total_seconds() / 86400.0
            for e in display_events
        ]

        def _short_act(name: str, lc: str | None) -> str:
            base = name if len(name) <= 24 else name[:22] + ".."
            lc_str = (lc or "")[:4]
            return f"{base} [{lc_str}]" if lc_str else base

        labels = [
            f"{i+1:02d}. {_short_act(str(e['activity']), e.get('lifecycle'))}"
            for i, e in enumerate(display_events)
        ]

        colors = []
        for e in display_events:
            act_str = str(e["activity"])
            if act_str.startswith("O_"):
                colors.append(COLOR_SUCCESS)
            elif act_str.startswith("W_"):
                colors.append(COLOR_ACCENT)
            else:
                colors.append(COLOR_PRIMARY)

        y_pos = list(range(len(rel_days)))
        ax.plot(rel_days, y_pos, color=COLOR_BORDER, linewidth=1.4, zorder=2)
        ax.scatter(
            rel_days,
            y_pos,
            c=colors,
            edgecolors=COLOR_BORDER,
            s=52,
            linewidths=1.4,
            zorder=3,
        )
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=7, fontweight="bold")
        ax.invert_yaxis()
        ax.set_xlabel("Elapsed Days since Case Start (t0)", fontsize=8.5, fontweight="bold")
        trunc_suffix = f" (showing first 30 of {total_events})" if total_events > 30 else f" ({total_events} events)"
        ax.set_title(f"Timeline: {case_id}{trunc_suffix}", fontsize=9, fontweight="bold")
        ax.grid(True, linestyle=":", alpha=0.5, zorder=1)
        self.tl_canvas.draw()

    def _run_custom_filter_analysis(self) -> None:
        if not self.service.is_loaded:
            return
        ftype = str(self.cf_type_combo.currentData())
        act_a = self.cf_act_a_combo.currentText().strip()
        act_b = self.cf_act_b_combo.currentText().strip()
        min_occ = int(self.cf_min_spin.value())
        lc = self.cf_lifecycle_combo.currentText().strip()
        ep_pos = str(self.cf_endpoint_combo.currentData())

        self._set_status_busy(f"Evaluating custom filter ({ftype})...")
        self._start_worker(
            lambda: self.service.run_custom_filter(
                filter_type=ftype,
                activity_a=act_a,
                activity_b=act_b,
                min_count=min_occ,
                lifecycle_filter=lc,
                endpoint_position=ep_pos,
            ),
            self._on_custom_filter_finished,
        )

    def _on_custom_filter_finished(self, item: AnalysisResult) -> None:
        self.latest_results[item.code] = item
        self.cf_result_table.setRowCount(1)
        values = [
            item.code,
            item.title,
            f"{item.count:,}",
            "-" if item.denominator is None else f"{item.denominator:,}",
            "-" if item.percentage is None else f"{item.percentage:.2f}%",
            "-" if item.mean_cycle_time_days is None else f"{item.mean_cycle_time_days:.4f}",
        ]
        for col, val in enumerate(values):
            self.cf_result_table.setItem(0, col, QTableWidgetItem(val))
        autofit_table_columns(self.cf_result_table)

        # Populate clean interactive Matching Cases table instead of raw JSON dump
        ev_by_case: dict[str, dict[str, Any]] = {}
        for ev in item.evidence:
            cid = str(ev.get("case_id", ""))
            if cid and cid not in ev_by_case:
                ev_by_case[cid] = ev

        shown_ids = item.case_ids[:MAX_CASE_LIST_PREVIEW]
        self.cf_case_table.setRowCount(len(shown_ids))
        for r_idx, cid in enumerate(shown_ids):
            ev = ev_by_case.get(cid, {})
            summary = self._summarize_custom_evidence(ev, item.rule)
            self.cf_case_table.setItem(r_idx, 0, QTableWidgetItem(cid))
            self.cf_case_table.setItem(r_idx, 1, QTableWidgetItem(summary))
        autofit_table_columns(self.cf_case_table)
        if shown_ids:
            self.cf_case_table.selectRow(0)

        self._refresh_dashboard_table()
        self._update_export_buttons()
        self._set_status_ready(f"Custom filter '{item.title}' finished ({item.count:,} cases).")

    def _summarize_custom_evidence(self, ev: dict[str, Any], fallback_rule: str) -> str:
        if not ev:
            return fallback_rule
        if "first_event" in ev and "subsequent_event" in ev:
            e1 = ev["first_event"]
            e2 = ev["subsequent_event"]
            gap = ev.get("intervening_events", 0)
            return (
                f"{e1.get('activity')} ({self._short_timestamp(str(e1.get('timestamp', '')))}) → "
                f"{e2.get('activity')} ({self._short_timestamp(str(e2.get('timestamp', '')))}) • {gap} intervening"
            )
        if "resource" in ev and "occurrence_count" in ev:
            return f"Resource: {ev.get('resource')} • {ev.get('occurrence_count')} matching occurrences"
        if "endpoint_position" in ev:
            return (
                f"{ev.get('endpoint_position')}: {ev.get('activity')} "
                f"@ {self._short_timestamp(str(ev.get('timestamp', '')))}"
            )
        if "occurrence_count" in ev:
            ct = ev.get("cycle_time_days")
            ct_part = f" • Cycle time: {float(ct):.2f} d" if ct is not None else ""
            return f"{ev.get('activity', 'Target')}: {ev.get('occurrence_count')}x{ct_part}"
        return fallback_rule

    def _on_custom_case_selected(self) -> None:
        selected = self.cf_case_table.selectedItems()
        if not selected or not self.service.is_loaded:
            return
        row = selected[0].row()
        cid_item = self.cf_case_table.item(row, 0)
        sum_item = self.cf_case_table.item(row, 1)
        if cid_item is None:
            return
        case_id = cid_item.text()
        summary = sum_item.text() if sum_item else ""
        try:
            events = get_case_events(self.service.data, case_id)
        except Exception:
            return
        self._update_context_inspector(case_id, events, summary)

    def _run_simple_dfg_analysis(self) -> None:
        if not self.service.is_loaded:
            QMessageBox.warning(
                self, "No Active Event Log", "Please import an XES event log before running DFG."
            )
            return
        top_n = int(self.dfg_top_spin.value())
        include_loops = bool(self.dfg_self_loop_chk.isChecked())
        self.dfg_run_btn.setText("Running DFG...")
        self.dfg_stats_label.setText(f"Computing top-{top_n} directly-follows transitions...")
        self._set_status_busy(f"Computing top-{top_n} Directly-Follows transitions...")
        self._start_worker(
            lambda: self.service.run_simple_dfg(top_n=top_n, include_self_loops=include_loops),
            self._on_simple_dfg_finished,
        )

    def _on_simple_dfg_finished(self, edges: list[dict[str, Any]]) -> None:
        self.dfg_run_btn.setText("▶ Run DFG")
        self.latest_dfg_edges = edges
        self._render_dfg_visual(edges)
        total_trans = sum(int(e.get("frequency", 0)) for e in edges)
        self._set_status_ready(
            f"Directly-Follows Graph rendered: {len(edges)} transitions ({total_trans:,} adjacent event pairs)."
        )

    def _toggle_dfg_animation(self, checked: bool) -> None:
        if checked:
            self.dfg_animate_btn.setText("⏸ Pause Flow")
            self.dfg_interactive_view.start_animation()
        else:
            self.dfg_animate_btn.setText("▶ Animate Flow")
            self.dfg_interactive_view.stop_animation()

    def _on_dfg_speed_changed(self) -> None:
        speed = float(self.dfg_speed_combo.currentData() or 1.0)
        self.dfg_interactive_view.set_animation_speed(speed)

    def _render_dfg_visual(self, edges: list[dict[str, Any]]) -> None:
        min_freq = int(self.dfg_min_edge_spin.value()) if hasattr(self, "dfg_min_edge_spin") else 1
        filtered = [e for e in edges if int(e.get("frequency", 0)) >= min_freq]

        self.dfg_table.setRowCount(len(filtered))
        for r_idx, edge in enumerate(filtered):
            freq = int(edge["frequency"])
            cases = int(edge.get("case_count", freq))
            self.dfg_table.setItem(r_idx, 0, QTableWidgetItem(str(edge["source_activity"])))
            self.dfg_table.setItem(r_idx, 1, QTableWidgetItem(str(edge["target_activity"])))
            self.dfg_table.setItem(r_idx, 2, QTableWidgetItem(f"{freq:,} ({cases:,}c)"))
            self.dfg_table.setItem(r_idx, 3, QTableWidgetItem(f"{edge['mean_hours']:.2f}"))
        autofit_table_columns(self.dfg_table)

        metric_mode = str(self.dfg_view_combo.currentData() or "performance")
        dark_canvas = bool(self.dfg_dark_chk.isChecked()) if hasattr(self, "dfg_dark_chk") else False
        summary = self.dfg_interactive_view.render_dfg(
            filtered,
            metric_mode=metric_mode,
            dark_canvas=dark_canvas,
        )
        if hasattr(self, "dfg_stats_label"):
            bn_info = f"  •  Primary Bottleneck: {summary['bottleneck']}" if summary.get("bottleneck") else ""
            self.dfg_stats_label.setText(
                f"Activity Map: {summary['nodes']} Activities  •  {summary['edges']} Transitions{bn_info}"
            )

    def _populate_exercise_case_list(self, key: str, results: list[AnalysisResult]) -> None:
        case_table = self.case_list_tables[key]
        trace_table = self.trace_tables[key]
        trace_table.setRowCount(0)

        rows_data: list[tuple[str, str, str, str]] = []
        for res in results:
            ev_by_case: dict[str, list[dict[str, Any]]] = {}
            for ev in res.evidence:
                cid = str(ev.get("case_id", ""))
                ev_by_case.setdefault(cid, []).append(ev)

            clean_cohort = self._display_name_for_code(res.code, res.title)
            for cid in res.case_ids[:MAX_CASE_LIST_PREVIEW]:
                ev_items = ev_by_case.get(cid, [])
                summary = self._summarize_case_evidence(res.code, ev_items)
                rows_data.append((res.code, clean_cohort, cid, summary))

        case_table.setRowCount(len(rows_data))
        for r_idx, (raw_code, clean_cohort, cid, summary) in enumerate(rows_data):
            c_item = QTableWidgetItem(clean_cohort)
            c_item.setData(Qt.UserRole, raw_code)
            case_table.setItem(r_idx, 0, c_item)
            case_table.setItem(r_idx, 1, QTableWidgetItem(cid))
            case_table.setItem(r_idx, 2, QTableWidgetItem(summary))
        autofit_table_columns(case_table)

        if rows_data:
            case_table.selectRow(0)

    def _summarize_case_evidence(self, code: str, ev_items: list[dict[str, Any]]) -> str:
        if not ev_items:
            return "Case included in cohort result"
        first = ev_items[0]
        if code in ("11.7C", "11.7D"):
            return (
                f"{first.get('activity')}: {first.get('occurrence_count')}x | "
                f"Cycle time: {first.get('cycle_time_days', 0.0):.4f} d"
            )
        if code == "11.7E":
            return (
                f"Final: {first.get('last_activity')} @ {first.get('last_timestamp')} | "
                f"Cycle time: {first.get('cycle_time_days', 0.0):.4f} d"
            )
        if code == "11.15":
            return f"Completed occurrences: {first.get('complete_occurrence_count')}x"
        if code == "11.18":
            parts = [
                f"Resource {item.get('resource')} ({item.get('complete_occurrence_count')}x)"
                for item in ev_items
            ]
            return "; ".join(parts)
        if code == "11.22":
            c_ev = first.get("cancelled_event", {})
            a_ev = first.get("subsequent_accepted_event", {})
            gap = first.get("intervening_events", 0)
            return (
                f"{c_ev.get('activity')} ({c_ev.get('timestamp')}) -> "
                f"{a_ev.get('activity')} ({a_ev.get('timestamp')}), gap: {gap} events"
            )
        return json.dumps(first, ensure_ascii=False, default=str)

    def _on_result_row_selected(self, key: str) -> None:
        table = self.result_tables[key]
        selected = table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        code_item = table.item(row, 0)
        if code_item is None:
            return
        code = code_item.data(Qt.UserRole) or code_item.text()
        result = self.latest_results.get(str(code))
        if result is not None:
            self._populate_exercise_case_list(key, [result])

    def _on_exercise_case_selected(self, key: str) -> None:
        case_table = self.case_list_tables[key]
        trace_table = self.trace_tables[key]
        selected = case_table.selectedItems()
        if not selected or not self.service.is_loaded:
            return
        row = selected[0].row()
        code_item = case_table.item(row, 0)
        case_item = case_table.item(row, 1)
        summary_item = case_table.item(row, 2)
        if case_item is None:
            return
        case_id = case_item.text()
        cohort_text = code_item.text() if code_item else key
        summary_text = summary_item.text() if summary_item else ""

        try:
            events = get_case_events(self.service.data, case_id)
        except Exception as exc:
            QMessageBox.critical(self, "Trace Load Error", str(exc))
            return

        trace_table.setRowCount(len(events))
        for idx, ev in enumerate(events):
            values = [
                str(idx + 1),
                str(ev["timestamp"]),
                str(ev["activity"]),
                str(ev["lifecycle"] or "-"),
                str(ev["resource"] or "-"),
            ]
            for col, val in enumerate(values):
                trace_table.setItem(idx, col, QTableWidgetItem(val))
        autofit_table_columns(trace_table)

        self._update_context_inspector(case_id, events, f"{cohort_text} — {summary_text}")

    @staticmethod
    def _short_timestamp(ts_text: str) -> str:
        """Format ISO timestamp cleanly for compact table display (full precision stays in tooltip)."""
        clean = str(ts_text).replace("T", " ")
        if "." in clean:
            clean = clean.split(".")[0]
        elif "+" in clean:
            clean = clean.split("+")[0]
        return clean.rstrip("Z")

    def _update_context_inspector(
        self,
        case_id: str,
        events: list[dict[str, Any]],
        context_note: str = "",
    ) -> None:
        short_id = case_id if len(case_id) <= 22 else case_id[:19] + "..."
        self.ctx_case_badge.setText(short_id)
        if events:
            t_start = self._short_timestamp(events[0]["timestamp"])
            t_end = self._short_timestamp(events[-1]["timestamp"])
            self.ctx_summary_label.setText(
                f"Case ID: {case_id}  •  Events: {len(events)}\n"
                f"First: {t_start}  |  Last: {t_end}"
                + (f"\nDetails: {context_note}" if context_note else "")
            )
        else:
            self.ctx_summary_label.setText(f"Case '{case_id}' has no events.")

        self.ctx_trace_table.setRowCount(len(events))
        for idx, ev in enumerate(events):
            raw_ts = str(ev["timestamp"])
            values = [
                str(idx + 1),
                self._short_timestamp(raw_ts),
                str(ev["activity"]),
                str(ev["lifecycle"] or "-"),
                str(ev["resource"] or "-"),
            ]
            for col, val in enumerate(values):
                cell = QTableWidgetItem(val)
                cell.setToolTip(raw_ts if col == 1 else val)
                self.ctx_trace_table.setItem(idx, col, cell)
        autofit_table_columns(self.ctx_trace_table)

    def _refresh_dashboard_table(self) -> None:
        preferred = [
            "11.7A", "11.7B", "11.7C", "11.7D", "11.7E",
            "11.15", "11.18", "11.22",
            "11.10-FAST", "11.10-SLOW",
        ]
        ordered = [self.latest_results[c] for c in preferred if c in self.latest_results]
        for code, res in self.latest_results.items():
            if code not in preferred:
                ordered.append(res)

        self.dashboard_table.setRowCount(len(ordered))
        self.reports_table.setRowCount(len(ordered))
        for r_idx, item in enumerate(ordered):
            clean_name = self._display_name_for_code(item.code, item.title)

            d_first = QTableWidgetItem(clean_name)
            d_first.setData(Qt.UserRole, item.code)
            self.dashboard_table.setItem(r_idx, 0, d_first)
            dash_values = [
                item.title,
                f"{item.count:,}",
                "-" if item.denominator is None else f"{item.denominator:,}",
                "-" if item.percentage is None else f"{item.percentage:.2f}%",
                "-" if item.mean_cycle_time_days is None else f"{item.mean_cycle_time_days:.4f}",
                item.rule,
            ]
            for c_idx, val in enumerate(dash_values, start=1):
                self.dashboard_table.setItem(r_idx, c_idx, QTableWidgetItem(val))

            r_first = QTableWidgetItem(clean_name)
            r_first.setData(Qt.UserRole, item.code)
            self.reports_table.setItem(r_idx, 0, r_first)
            rep_values = [
                item.title,
                f"{item.count:,}",
                "-" if item.denominator is None else f"{item.denominator:,}",
                "-" if item.percentage is None else f"{item.percentage:.2f}%",
                "-" if item.mean_cycle_time_days is None else f"{item.mean_cycle_time_days:.4f}",
                f"{len(item.evidence):,} records",
            ]
            for c_idx, val in enumerate(rep_values, start=1):
                self.reports_table.setItem(r_idx, c_idx, QTableWidgetItem(val))

        autofit_table_columns(self.dashboard_table)
        autofit_table_columns(self.reports_table)

    def _search_case(self) -> None:
        if not self.service.is_loaded:
            return
        query = self.case_input.text().strip()
        filter_code = self.case_filter_combo.currentData()

        try:
            if filter_code and filter_code != "ALL":
                if filter_code not in self.latest_results:
                    self.case_duration_table.setRowCount(0)
                    self.case_table.setRowCount(0)
                    self.case_search_status.setText(
                        "Selected cohort has not been executed yet. Run the corresponding analysis module first."
                    )
                    return
                allowed_ids = set(self.latest_results[filter_code].case_ids)
                all_matching = self.service.search_case_durations(query, limit=100_000)
                cases = [c for c in all_matching if c["case_id"] in allowed_ids][:MAX_CASE_LIST_PREVIEW]
            else:
                cases = self.service.search_case_durations(query, limit=MAX_CASE_LIST_PREVIEW)
        except Exception as exc:
            QMessageBox.critical(self, "Case Search Error", str(exc))
            return

        self.case_duration_table.setRowCount(len(cases))
        for row, case in enumerate(cases):
            values = [
                str(case["case_id"]),
                f"{int(case.get('event_count', 0)):,}",
                str(case["start_time"]),
                str(case["end_time"]),
                f"{case['cycle_time_days']:.4f}",
            ]
            for column, value in enumerate(values):
                self.case_duration_table.setItem(row, column, QTableWidgetItem(value))
        autofit_table_columns(self.case_duration_table)

        self.case_search_status.setText(
            f"Showing {len(cases)} cases (up to {MAX_CASE_LIST_PREVIEW} rows). "
            "Select any row to inspect its chronological event timeline."
        )
        self.case_table.setRowCount(0)

    def _on_case_duration_selected(self) -> None:
        selected = self.case_duration_table.selectedItems()
        if not selected or not self.service.is_loaded:
            return
        row = selected[0].row()
        case_item = self.case_duration_table.item(row, 0)
        cycle_item = self.case_duration_table.item(row, 4)
        if case_item is None:
            return
        case_id = case_item.text()
        cycle_text = cycle_item.text() if cycle_item else "-"
        try:
            events = get_case_events(self.service.data, case_id)
        except Exception as exc:
            QMessageBox.critical(self, "Error Loading Case", str(exc))
            return
        self.case_table.setRowCount(len(events))
        for event_row, event in enumerate(events):
            values = [
                str(event["timestamp"]),
                str(event["activity"]),
                str(event["lifecycle"] or "-"),
                str(event["resource"] or "-"),
                str(event["source_order"]),
            ]
            for column, value in enumerate(values):
                self.case_table.setItem(event_row, column, QTableWidgetItem(value))
        autofit_table_columns(self.case_table)

        self.timeline_case_combo.setCurrentText(case_id)
        self._plot_selected_case_timeline()
        self._update_context_inspector(case_id, events, f"Cycle time: {cycle_text} days")
        self._set_status_ready(f"Case '{case_id}' loaded ({len(events)} events).")

    def _show_about(self) -> None:
        def package_version(name: str) -> str:
            try:
                return version(name)
            except PackageNotFoundError:
                return "not installed"

        information = (
            "Tracely — Process Mining & Event Log Intelligence\n\n"
            f"Python: {sys.version.split()[0]}\n"
            f"PM4Py: {package_version('pm4py')}\n"
            f"Pandas: {package_version('pandas')}\n"
            f"PySide6: {package_version('PySide6')}"
        )
        QMessageBox.information(self, "About Tracely", information)

    def _export_results(self) -> None:
        if not self.latest_results:
            QMessageBox.information(
                self,
                "No Results to Export",
                "Run at least one analytical module before exporting CSV files.",
            )
            return
        directory = QFileDialog.getExistingDirectory(self, "Select Export Directory", str(Path.cwd()))
        if not directory:
            return
        try:
            summary, evidence = self.service.export(directory, list(self.latest_results.values()))
        except Exception as exc:
            QMessageBox.critical(self, "CSV Export Failed", str(exc))
            return
        self._set_status_ready(f"CSV bundle exported to: {directory}")
        QMessageBox.information(
            self,
            "CSV Export Complete",
            f"Files saved:\n{summary}\n{evidence}",
        )

    def _export_pdf_report(self) -> None:
        if not self.latest_results:
            QMessageBox.information(
                self,
                "No Results to Export",
                "Run at least one analytical module before generating a PDF report.",
            )
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Automated PDF Analysis Report",
            str(Path.cwd() / "exports" / "tracely_analysis_report.pdf"),
            "PDF Files (*.pdf)",
        )
        if not file_path:
            return
        try:
            saved = self.service.export_pdf(
                output_path=file_path,
                results=list(self.latest_results.values()),
                fast_slow=self.latest_fast_slow,
            )
        except Exception as exc:
            QMessageBox.critical(self, "PDF Report Failed", str(exc))
            return
        self._set_status_ready(f"PDF report saved to: {saved}")
        QMessageBox.information(
            self,
            "PDF Report Complete",
            f"Automated analysis report saved:\n{saved}",
        )

    def _set_status_busy(self, message: str) -> None:
        self.status_indicator_dot.setText("● RUNNING")
        self.status_indicator_dot.setStyleSheet(
            f"background-color: {COLOR_ACCENT}; border: 1.5px solid {COLOR_BORDER}; "
            "border-radius: 5px; padding: 2px 8px; font-size: 11px; font-weight: 900;"
        )
        self.status_label.setText(message)
        self.sidebar_engine_lbl.setText("PM4Py Worker Busy...")

    def _set_status_ready(self, message: str) -> None:
        self.status_indicator_dot.setText("● READY")
        self.status_indicator_dot.setStyleSheet(
            f"background-color: {COLOR_SUCCESS}; border: 1.5px solid {COLOR_BORDER}; "
            "border-radius: 5px; padding: 2px 8px; font-size: 11px; font-weight: 900;"
        )
        self.status_label.setText(message)

    def _set_status_error(self, message: str) -> None:
        self.status_indicator_dot.setText("● ERROR")
        self.status_indicator_dot.setStyleSheet(
            f"background-color: {COLOR_DANGER}; border: 1.5px solid {COLOR_BORDER}; "
            "border-radius: 5px; padding: 2px 8px; font-size: 11px; font-weight: 900;"
        )
        self.status_label.setText(f"Error: {message}")

    def _start_worker(self, task: Callable[[], Any], on_success: Callable[[Any], None]) -> None:
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, "Task in Progress", "Please wait for the active background task to finish.")
            return
        self._set_analysis_enabled(False)
        self.progress_bar.setVisible(True)
        self.worker = TaskWorker(task, self)
        self.worker.succeeded.connect(on_success)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_failed(self, message: str) -> None:
        self._set_status_error(message)
        QMessageBox.critical(self, "Operation Failed", message)

    def _on_worker_finished(self) -> None:
        self.progress_bar.setVisible(False)
        self.open_button.setEnabled(True)
        self._set_analysis_enabled(self.service.is_loaded)

    def _set_analysis_enabled(self, enabled: bool) -> None:
        for button in self.run_buttons.values():
            button.setEnabled(enabled)
        self.run_all_button.setEnabled(enabled)
        self.dash_run_all_btn.setEnabled(enabled)
        self.case_search_button.setEnabled(enabled)
        self.case_input.setEnabled(enabled)
        self.case_filter_combo.setEnabled(enabled)
        self.fast_slow_btn.setEnabled(enabled)
        self.fast_slow_spin.setEnabled(enabled)
        self.refresh_dist_btn.setEnabled(enabled)
        self.timeline_plot_btn.setEnabled(enabled)
        self.timeline_case_combo.setEnabled(enabled)
        self.cf_run_btn.setEnabled(enabled)
        self.dfg_run_btn.setEnabled(enabled)
