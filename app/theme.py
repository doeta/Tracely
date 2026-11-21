"""Centralized Design System, Tokens, and Reusable Neubrutalist Widgets for Tracely."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# ======================================================================
# 1. COLOR PALETTE TOKENS
# ======================================================================
COLOR_BG = "#F7F5EF"
COLOR_SURFACE = "#FFFFFF"
COLOR_PRIMARY = "#3155D9"
COLOR_PRIMARY_HOVER = "#2443B5"
COLOR_ACCENT = "#F6D65B"
COLOR_SUCCESS = "#B9E5CC"
COLOR_DANGER = "#EF8B79"
COLOR_TEXT = "#171717"
COLOR_TEXT_SECONDARY = "#666666"
COLOR_TEXT_MUTED = COLOR_TEXT_SECONDARY
COLOR_BORDER = "#171717"
COLOR_SUBTLE_BG = "#EFECE4"

# ======================================================================
# 2. SPACING & SIZING SCALE TOKENS
# ======================================================================
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24
SPACE_2XL = 32

TOPBAR_HEIGHT = 62
STATUSBAR_HEIGHT = 38
SIDEBAR_WIDTH_EXPANDED = 240
SIDEBAR_WIDTH_COLLAPSED = 64

BTN_HEIGHT_STANDARD = 38
BTN_HEIGHT_COMPACT = 34
BTN_ICON_SIZE = 38

TABLE_HEADER_HEIGHT = 38
TABLE_ROW_HEIGHT = 34

NUMERIC_HEADER_KEYWORDS = (
    "count",
    "cases",
    "total",
    "share",
    "percentage",
    "cycle",
    "days",
    "hours",
    "duration",
    "events",
    "records",
    "order",
    "size",
)


def apply_hard_shadow(
    widget: QWidget,
    offset_x: int = 4,
    offset_y: int = 4,
    color: str = COLOR_BORDER,
) -> None:
    """Attach a crisp 0-blur Neubrutalist hard drop shadow to a widget."""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(0)
    shadow.setOffset(offset_x, offset_y)
    shadow.setColor(QColor(color))
    widget.setGraphicsEffect(shadow)


def make_neubrutal_card(
    object_name: str = "NeubrutalCard",
    shadow_offset: int = 4,
) -> QFrame:
    """Create a white surface card with 2px solid black border and controlled hard shadow."""
    card = QFrame()
    card.setObjectName(object_name)
    if shadow_offset > 0:
        apply_hard_shadow(card, shadow_offset, shadow_offset)
    return card


def make_button(
    text: str,
    variant: str = "primary",
    compact: bool = False,
    fixed_width: int | None = None,
    tooltip: str = "",
) -> QPushButton:
    """Create a standardized button with locked height and variant styling."""
    btn = QPushButton(text)
    variant_map = {
        "primary": "",
        "accent": "AccentButton",
        "secondary": "SecondaryButton",
        "outline": "SecondaryButton",
        "success": "SuccessButton",
        "danger": "DangerButton",
        "icon": "IconButton",
    }
    obj_name = variant_map.get(variant.lower(), "")
    if obj_name:
        btn.setObjectName(obj_name)

    h = BTN_HEIGHT_COMPACT if compact else BTN_HEIGHT_STANDARD
    btn.setFixedHeight(h)
    if variant.lower() == "icon":
        btn.setFixedSize(BTN_ICON_SIZE, BTN_ICON_SIZE)
    elif fixed_width is not None:
        btn.setFixedWidth(fixed_width)

    if tooltip:
        btn.setToolTip(tooltip)
    return btn


def make_kpi_card(
    label_text: str,
    initial_value: str = "—",
    badge_text: str = "",
    badge_bg: str = COLOR_ACCENT,
) -> tuple[QFrame, QLabel, QLabel]:
    """Create a proportional Neubrutalist KPI metric card that never clips long text."""
    card = make_neubrutal_card("KpiCard", shadow_offset=3)
    card.setMinimumHeight(114)
    card.setMinimumWidth(165)
    card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(SPACE_LG, SPACE_MD, SPACE_LG, SPACE_MD)
    layout.setSpacing(SPACE_XS)

    top_row = QHBoxLayout()
    top_row.setContentsMargins(0, 0, 0, 0)
    top_row.setSpacing(SPACE_SM)
    title_lbl = QLabel(label_text)
    title_lbl.setObjectName("KpiTitle")
    title_lbl.setWordWrap(True)
    top_row.addWidget(title_lbl, 1)

    badge_lbl = QLabel(badge_text)
    badge_lbl.setObjectName("RefBadge")
    badge_lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    badge_lbl.setStyleSheet(
        f"background-color: {badge_bg}; color: {COLOR_TEXT}; "
        f"border: 1.5px solid {COLOR_BORDER}; border-radius: 5px; "
        "padding: 2px 7px; font-size: 11px; font-weight: 800;"
    )
    badge_lbl.setVisible(bool(badge_text))
    top_row.addWidget(badge_lbl, 0, Qt.AlignRight | Qt.AlignTop)
    layout.addLayout(top_row)

    is_long_text = len(initial_value) > 14 and not initial_value.replace(",", "").isdigit()
    value_lbl = QLabel(initial_value)
    value_lbl.setObjectName("KpiValueCompact" if is_long_text else "KpiValue")
    value_lbl.setWordWrap(True)
    value_lbl.setToolTip(initial_value)
    value_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
    layout.addWidget(value_lbl, 1)

    sub_lbl = QLabel("Awaiting active event log")
    sub_lbl.setObjectName("KpiSub")
    sub_lbl.setWordWrap(True)
    layout.addWidget(sub_lbl)

    return card, value_lbl, sub_lbl


def set_kpi_value(label: QLabel, text: str) -> None:
    """Update a KPI card value label, adapting font class if text is a long activity name."""
    is_long = len(text) > 15
    target_name = "KpiValueCompact" if is_long else "KpiValue"
    if label.objectName() != target_name:
        label.setObjectName(target_name)
        label.style().unpolish(label)
        label.style().polish(label)
    label.setText(text)
    label.setToolTip(text)


def make_ref_badge(text: str, bg_color: str = COLOR_ACCENT) -> QLabel:
    """Create a compact status or academic reference pill badge."""
    badge = QLabel(text)
    badge.setObjectName("RefBadge")
    badge.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    badge.setFixedHeight(28)
    badge.setStyleSheet(
        f"background-color: {bg_color}; color: {COLOR_TEXT}; "
        f"border: 2px solid {COLOR_BORDER}; border-radius: 6px; "
        "padding: 2px 10px; font-size: 11px; font-weight: 800;"
    )
    return badge


def _is_numeric_column(header_text: str) -> bool:
    lower = header_text.strip().lower()
    if "id" in lower or "name" in lower or "title" in lower or "activity" in lower or "rule" in lower or "path" in lower:
        return False
    return any(k in lower for k in NUMERIC_HEADER_KEYWORDS)


class AutoFitHeaderView(QHeaderView):
    """Custom centered QHeaderView that auto-scales / wraps header text so no character is ever clipped."""

    def __init__(self, orientation: Qt.Orientation, parent=None) -> None:
        super().__init__(orientation, parent)
        self.setDefaultAlignment(Qt.AlignCenter)

    def paintSection(self, painter: QPainter, rect: QRect, logicalIndex: int) -> None:
        if not rect.isValid():
            return
        painter.save()

        # Draw Neubrutalist header background & borders
        painter.fillRect(rect, QColor(COLOR_SUBTLE_BG))
        painter.setPen(QPen(QColor(COLOR_BORDER), 2))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        painter.setPen(QPen(QColor(COLOR_BORDER), 1))
        painter.drawLine(rect.topRight(), rect.bottomRight())

        text = str(self.model().headerData(logicalIndex, self.orientation(), Qt.DisplayRole) or "")
        inner = rect.adjusted(4, 2, -4, -3)

        # Dynamically find the largest readable font size (12px down to 8px) that fits without clipping
        chosen_font = QFont(self.font())
        chosen_font.setBold(True)
        flags = Qt.AlignCenter | Qt.TextWordWrap

        for pt_size in (10, 9, 8, 7):
            chosen_font.setPointSize(pt_size)
            fm = QFontMetrics(chosen_font)
            single_w = fm.horizontalAdvance(text)
            if single_w <= inner.width():
                flags = Qt.AlignCenter
                break
            bound = fm.boundingRect(inner, Qt.AlignCenter | Qt.TextWordWrap, text)
            if bound.width() <= inner.width() + 2 and bound.height() <= inner.height() + 2:
                flags = Qt.AlignCenter | Qt.TextWordWrap
                break

        painter.setFont(chosen_font)
        painter.setPen(QColor(COLOR_TEXT))
        painter.drawText(inner, flags, text)
        painter.restore()


def make_table(headers: list[str]) -> QTableWidget:
    """Create a standardized high-contrast analytical table with clean cell clipping (no text bleeding)."""
    table = QTableWidget(0, len(headers))
    custom_header = AutoFitHeaderView(Qt.Horizontal, table)
    table.setHorizontalHeader(custom_header)
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setAlternatingRowColors(True)
    table.setWordWrap(False)
    table.setTextElideMode(Qt.ElideRight)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(TABLE_ROW_HEIGHT)

    header = table.horizontalHeader()
    header.setFixedHeight(TABLE_HEADER_HEIGHT + 4)
    header.setMinimumSectionSize(38)
    header.setDefaultAlignment(Qt.AlignCenter)
    header.setStretchLastSection(True)

    for idx, col_text in enumerate(headers):
        clean = col_text.strip().lower()
        h_item = table.horizontalHeaderItem(idx)
        if h_item is not None:
            h_item.setToolTip(col_text)
            h_item.setTextAlignment(Qt.AlignCenter)

        if clean == "#":
            header.setSectionResizeMode(idx, QHeaderView.Fixed)
            table.setColumnWidth(idx, 38)
        else:
            header.setSectionResizeMode(idx, QHeaderView.Stretch)

    return table


def set_table_cell(
    table: QTableWidget,
    row: int,
    col: int,
    text: str,
    user_data: object = None,
) -> QTableWidgetItem:
    """Create a table cell with automatic full-value tooltip and consistent alignment."""
    item = QTableWidgetItem(text)
    item.setToolTip(text)
    if user_data is not None:
        item.setData(Qt.UserRole, user_data)

    h_item = table.horizontalHeaderItem(col)
    h_text = h_item.text().strip() if h_item is not None else ""
    if h_text == "#":
        item.setTextAlignment(Qt.AlignCenter)
    elif _is_numeric_column(h_text):
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    else:
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    table.setItem(row, col, item)
    return item


def autofit_table_columns(table: QTableWidget, max_col_width: int = 340) -> None:
    """Keep all columns stretched inside the table viewport (zero horizontal sliding) and align/tooltip cells."""
    header = table.horizontalHeader()
    col_count = table.columnCount()
    row_count = table.rowCount()
    if col_count == 0:
        return

    for col in range(col_count):
        h_item = table.horizontalHeaderItem(col)
        h_text = h_item.text().strip() if h_item is not None else ""

        for r in range(row_count):
            cell = table.item(r, col)
            if cell is not None:
                if not cell.toolTip():
                    cell.setToolTip(cell.text())
                if h_text == "#":
                    cell.setTextAlignment(Qt.AlignCenter)
                elif _is_numeric_column(h_text):
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    cell.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        if h_text == "#":
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            table.setColumnWidth(col, 38)
        elif _is_numeric_column(h_text) and col_count >= 5:
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        else:
            header.setSectionResizeMode(col, QHeaderView.Stretch)


def build_global_stylesheet() -> str:
    """Return the complete Tracely Professional Neubrutalism stylesheet."""
    return f"""
    QMainWindow, QWidget {{
        background-color: {COLOR_BG};
        color: {COLOR_TEXT};
        font-family: "Inter", "Manrope", "Segoe UI", Arial, sans-serif;
        font-size: 13px;
    }}
    QFrame#TopNavBar {{
        background-color: {COLOR_SURFACE};
        border-bottom: 2px solid {COLOR_BORDER};
    }}
    QFrame#SidebarFrame {{
        background-color: {COLOR_SURFACE};
        border-right: 2px solid {COLOR_BORDER};
    }}
    QFrame#ContextPanel {{
        background-color: {COLOR_SURFACE};
        border-left: 2px solid {COLOR_BORDER};
    }}
    QFrame#StatusBarFrame {{
        background-color: {COLOR_SURFACE};
        border-top: 2px solid {COLOR_BORDER};
    }}
    QFrame#NeubrutalCard, QFrame#KpiCard {{
        background-color: {COLOR_SURFACE};
        border: 2px solid {COLOR_BORDER};
        border-radius: 8px;
    }}
    QFrame#EmptyStateBanner {{
        background-color: {COLOR_ACCENT};
        border: 2px solid {COLOR_BORDER};
        border-radius: 8px;
    }}
    QFrame#SuccessBanner {{
        background-color: {COLOR_SUCCESS};
        border: 2px solid {COLOR_BORDER};
        border-radius: 8px;
    }}
    QFrame#DangerBanner {{
        background-color: {COLOR_DANGER};
        border: 2px solid {COLOR_BORDER};
        border-radius: 8px;
    }}
    QLabel {{
        background-color: transparent;
        color: {COLOR_TEXT};
        font-size: 13px;
    }}
    QLabel#BrandLogo {{
        background-color: {COLOR_PRIMARY};
        color: #FFFFFF;
        border: 2px solid {COLOR_BORDER};
        border-radius: 6px;
        font-size: 16px;
        font-weight: 900;
        padding: 4px 10px;
    }}
    QLabel#BrandTitle {{
        font-size: 19px;
        font-weight: 900;
        color: {COLOR_TEXT};
        letter-spacing: 0.5px;
    }}
    QLabel#SidebarSectionHeader {{
        color: {COLOR_TEXT_SECONDARY};
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 1.0px;
        padding: 10px 10px 4px 10px;
    }}
    /* Typography Scale: Page title 24px, Section title 18px, Card title 14px */
    QLabel#PageTitle {{
        font-size: 24px;
        font-weight: 900;
        color: {COLOR_TEXT};
    }}
    QLabel#PageSubtitle {{
        font-size: 13px;
        font-weight: 500;
        color: {COLOR_TEXT_SECONDARY};
    }}
    QLabel#SectionHeading {{
        font-size: 16px;
        font-weight: 800;
        color: {COLOR_TEXT};
    }}
    QLabel#CardTitle, QLabel#KpiTitle {{
        font-size: 13px;
        font-weight: 800;
        color: {COLOR_TEXT_SECONDARY};
        letter-spacing: 0.3px;
    }}
    QLabel#KpiValue {{
        font-size: 22px;
        font-weight: 900;
        color: {COLOR_TEXT};
    }}
    QLabel#KpiValueCompact {{
        font-size: 15px;
        font-weight: 800;
        color: {COLOR_TEXT};
    }}
    QLabel#KpiSub {{
        font-size: 11.5px;
        font-weight: 600;
        color: {COLOR_TEXT_SECONDARY};
    }}
    /* Standardized Buttons (13px font, 2px border, zero layout shift on state change) */
    QPushButton {{
        background-color: {COLOR_PRIMARY};
        color: #FFFFFF;
        border: 2px solid {COLOR_BORDER};
        border-radius: 7px;
        padding: 6px 14px;
        min-height: 22px;
        font-weight: 800;
        font-size: 13px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_PRIMARY_HOVER};
        border: 2px solid {COLOR_BORDER};
    }}
    QPushButton:pressed {{
        background-color: #1A3399;
        border: 2px solid {COLOR_BORDER};
    }}
    QPushButton:disabled {{
        background-color: #E2DFD7;
        color: #78756E;
        border: 2px solid #8A8780;
    }}
    QPushButton#AccentButton {{
        background-color: {COLOR_ACCENT};
        color: {COLOR_TEXT};
    }}
    QPushButton#AccentButton:hover {{
        background-color: #EACA4A;
    }}
    QPushButton#SecondaryButton, QPushButton#IconButton {{
        background-color: {COLOR_SURFACE};
        color: {COLOR_TEXT};
    }}
    QPushButton#IconButton {{
        padding: 2px;
        font-size: 16px;
        font-weight: 900;
    }}
    QPushButton#SecondaryButton:hover, QPushButton#IconButton:hover {{
        background-color: {COLOR_SUBTLE_BG};
    }}
    QPushButton#SuccessButton {{
        background-color: {COLOR_SUCCESS};
        color: {COLOR_TEXT};
    }}
    QPushButton#DangerButton {{
        background-color: {COLOR_DANGER};
        color: {COLOR_TEXT};
    }}
    QPushButton#NavButton {{
        background-color: transparent;
        color: {COLOR_TEXT};
        border: 2px solid transparent;
        border-radius: 7px;
        padding: 7px 12px;
        min-height: 22px;
        text-align: left;
        font-weight: 700;
        font-size: 13px;
    }}
    QPushButton#NavButton:hover {{
        background-color: {COLOR_SUBTLE_BG};
        border: 2px solid {COLOR_BORDER};
    }}
    QPushButton#NavButton[active="true"] {{
        background-color: {COLOR_ACCENT};
        color: {COLOR_TEXT};
        border: 2px solid {COLOR_BORDER};
        font-weight: 900;
    }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {{
        background-color: {COLOR_SURFACE};
        color: {COLOR_TEXT};
        border: 2px solid {COLOR_BORDER};
        border-radius: 7px;
        padding: 5px 10px;
        min-height: 24px;
        font-size: 13px;
        font-weight: 600;
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {{
        border: 2px solid {COLOR_PRIMARY};
        background-color: #FFFFFF;
    }}
    QTableWidget {{
        background-color: {COLOR_SURFACE};
        alternate-background-color: {COLOR_BG};
        color: {COLOR_TEXT};
        border: 2px solid {COLOR_BORDER};
        border-radius: 8px;
        gridline-color: #D6D3CD;
        selection-background-color: {COLOR_ACCENT};
        selection-color: {COLOR_TEXT};
        font-size: 13px;
        font-weight: 600;
    }}
    QTableWidget::item {{
        padding: 5px 10px;
    }}
    QHeaderView::section {{
        background-color: {COLOR_SUBTLE_BG};
        color: {COLOR_TEXT};
        font-weight: 800;
        font-size: 12.5px;
        padding: 7px 10px;
        border: none;
        border-bottom: 2px solid {COLOR_BORDER};
        border-right: 1px solid {COLOR_BORDER};
    }}
    QProgressBar {{
        border: 2px solid {COLOR_BORDER};
        border-radius: 6px;
        background-color: {COLOR_SURFACE};
        max-height: 16px;
        text-align: center;
        font-weight: 800;
        font-size: 11px;
        color: {COLOR_TEXT};
    }}
    QProgressBar::chunk {{
        background-color: {COLOR_PRIMARY};
        border-radius: 4px;
    }}
    QTabWidget::pane {{
        border: 2px solid {COLOR_BORDER};
        border-radius: 8px;
        background-color: {COLOR_SURFACE};
    }}
    QTabBar::tab {{
        background-color: {COLOR_SUBTLE_BG};
        color: {COLOR_TEXT};
        border: 2px solid {COLOR_BORDER};
        border-bottom: none;
        border-top-left-radius: 7px;
        border-top-right-radius: 7px;
        padding: 8px 16px;
        margin-right: 4px;
        font-size: 13px;
        font-weight: 800;
    }}
    QTabBar::tab:selected {{
        background-color: {COLOR_ACCENT};
        color: {COLOR_TEXT};
    }}
    QScrollBar:vertical {{
        background: {COLOR_BG};
        width: 12px;
        margin: 0px;
        border-left: 1px solid {COLOR_BORDER};
    }}
    QScrollBar::handle:vertical {{
        background: #B8B4AA;
        min-height: 24px;
        border-radius: 4px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {COLOR_TEXT_SECONDARY};
    }}
    QScrollBar:horizontal {{
        background: {COLOR_BG};
        height: 12px;
        margin: 0px;
        border-top: 1px solid {COLOR_BORDER};
    }}
    QScrollBar::handle:horizontal {{
        background: #B8B4AA;
        min-width: 24px;
        border-radius: 4px;
        margin: 2px;
    }}
    """
