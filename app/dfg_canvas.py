"""Interactive Disco-style Directly-Follows Graph (DFG) canvas with Bottleneck Heatmap & Live Token Animation."""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
)


NODE_WIDTH = 248.0
NODE_HEIGHT = 82.0
H_SPACING = 320.0
V_SPACING = 158.0


def _format_duration_human(hours: float) -> str:
    if hours <= 0.0005:
        return "instant"
    if hours < 1.0:
        mins = hours * 60.0
        if mins < 1.0:
            return f"{mins * 60.0:.0f} secs"
        return f"{mins:.1f} mins"
    if hours < 24.0:
        return f"{hours:.1f} hrs"
    return f"{hours / 24.0:.1f} d"


def _interpolate_color(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    r = int(c1[0] + (c2[0] - c1[0]) * t)
    g = int(c1[1] + (c2[1] - c1[1]) * t)
    b = int(c1[2] + (c2[2] - c1[2]) * t)
    return QColor(r, g, b)


class DfgTerminalNodeItem(QGraphicsEllipseItem):
    """Disco-style circular Start (green ▼) or End (red ■) terminal marker."""

    def __init__(self, is_start: bool, x: float, y: float, dark_canvas: bool = False) -> None:
        self.radius = 18.0
        super().__init__(-self.radius, -self.radius, self.radius * 2, self.radius * 2)
        self.setPos(x, y)
        self.is_start = is_start
        self.dark_canvas = dark_canvas
        self.setZValue(4)
        self.setToolTip("Process Start" if is_start else "Process End")

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing, True)
        r = self.radius
        fill = QColor("#86B882" if self.is_start else "#D97A73")
        border = QColor("#3F623C" if self.is_start else "#8A2B24")
        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(border, 2.0))
        painter.drawEllipse(QRectF(-r, -r, r * 2, r * 2))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#264024" if self.is_start else "#5C1914"))
        if self.is_start:
            tri = QPolygonF([QPointF(-6, -4), QPointF(6, -4), QPointF(0, 7)])
            painter.drawPolygon(tri)
        else:
            painter.drawRect(QRectF(-5.5, -5.5, 11.0, 11.0))


class DfgNodeCardItem(QGraphicsRectItem):
    """Disco-style activity node with bottleneck heatmap shading (warm cream -> amber -> coral)."""

    def __init__(
        self,
        activity: str,
        meta: dict[str, Any],
        heat_ratio: float,
        metric_mode: str,
        subtitle_metric: str,
        x: float,
        y: float,
        dark_canvas: bool = False,
    ) -> None:
        super().__init__(0, 0, NODE_WIDTH, NODE_HEIGHT)
        self.setPos(x, y)
        self.activity = activity
        self.meta = meta
        self.heat_ratio = max(0.0, min(1.0, heat_ratio))
        self.metric_mode = metric_mode
        self.subtitle_metric = subtitle_metric
        self.dark_canvas = dark_canvas
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self._hovered = False
        self.setToolTip(
            f"Activity: {activity}\n"
            f"Cases: {int(meta.get('case_count', 0)):,}\n"
            f"Events: {int(meta.get('event_count', 0)):,}\n"
            f"Start Cases: {int(meta.get('start_count', 0)):,}\n"
            f"End Cases: {int(meta.get('end_count', 0)):,}\n"
            f"Metric: {subtitle_metric}"
        )

    def hoverEnterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect()

        # Subtle crisp shadow
        shadow_rect = rect.translated(3.0, 3.0)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 45 if not self.dark_canvas else 110))
        painter.drawRoundedRect(shadow_rect, 7.0, 7.0)

        # Disco-style heatmap fill (Cream -> Warm Amber -> Orange for high bottleneck/frequency)
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        if self.dark_canvas:
            if self.metric_mode == "performance":
                top_c = _interpolate_color((24, 34, 53), (124, 45, 18), self.heat_ratio)
                bot_c = _interpolate_color((15, 23, 42), (154, 52, 18), self.heat_ratio)
            else:
                top_c = _interpolate_color((24, 34, 53), (30, 64, 175), self.heat_ratio)
                bot_c = _interpolate_color((15, 23, 42), (37, 99, 235), self.heat_ratio)
            text_c = QColor("#F8FAFC")
            sub_c = QColor("#CBD5E1")
            border_c = QColor("#F6D65B" if (self._hovered or self.isSelected()) else "#60A5FA")
        else:
            if self.metric_mode == "performance":
                top_c = _interpolate_color((249, 243, 229), (242, 186, 102), self.heat_ratio)
                bot_c = _interpolate_color((239, 224, 194), (229, 152, 62), self.heat_ratio)
            else:
                top_c = _interpolate_color((241, 245, 255), (147, 197, 253), self.heat_ratio)
                bot_c = _interpolate_color((224, 235, 255), (96, 165, 250), self.heat_ratio)
            text_c = QColor("#171717")
            sub_c = QColor("#3F3F46")
            border_c = QColor("#3155D9" if (self._hovered or self.isSelected()) else "#44403C")

        grad.setColorAt(0.0, top_c)
        grad.setColorAt(1.0, bot_c)

        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(border_c, 2.2 if (self._hovered or self.isSelected()) else 1.6))
        painter.drawRoundedRect(rect, 7.0, 7.0)

        # Activity Title (centered like Disco)
        title_font = QFont("Segoe UI", 9.5, QFont.Bold)
        painter.setFont(title_font)
        painter.setPen(text_c)
        title_rect = QRectF(10.0, 8.0, NODE_WIDTH - 20.0, 38.0)
        painter.drawText(title_rect, Qt.AlignCenter | Qt.TextWordWrap, self.activity)

        # Primary Metric Line (e.g., "18.4 hrs avg wait" or "31,509 cases • 42,995 events")
        metric_font = QFont("Segoe UI", 8.5, QFont.Bold)
        painter.setFont(metric_font)
        painter.setPen(sub_c)
        metric_rect = QRectF(10.0, 48.0, NODE_WIDTH - 20.0, 22.0)
        painter.drawText(metric_rect, Qt.AlignCenter, self.subtitle_metric)

        # Bottleneck indicator pill if high heat
        if self.heat_ratio >= 0.65:
            tag_rect = QRectF(NODE_WIDTH - 86.0, -10.0, 80.0, 18.0)
            painter.setPen(QPen(QColor("#171717"), 1.2))
            painter.setBrush(QColor("#DC2626" if self.metric_mode == "performance" else "#3155D9"))
            painter.drawRoundedRect(tag_rect, 4.0, 4.0)
            painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(
                tag_rect,
                Qt.AlignCenter,
                "BOTTLENECK" if self.metric_mode == "performance" else "HOTSPOT",
            )


class DfgEdgeCurveItem(QGraphicsPathItem):
    """Disco-style weighted Bezier arrow: thick red for slow bottlenecks, crisp blue/gray for normal flow."""

    def __init__(
        self,
        start_pt: QPointF,
        end_pt: QPointF,
        label_text: str,
        weight_ratio: float,
        bottleneck_ratio: float,
        metric_mode: str = "performance",
        is_back_edge: bool = False,
        is_terminal_edge: bool = False,
        is_start_edge: bool = False,
        has_reverse: bool = False,
        layer_span: int = 1,
        label_t: float = 0.5,
        side_offset: float = 0.0,
        dark_canvas: bool = False,
        tooltip: str = "",
        mean_hours: float = 0.0,
        frequency: int = 1,
    ) -> None:
        super().__init__()
        self.start_pt = start_pt
        self.end_pt = end_pt
        self.label_text = label_text
        self.weight_ratio = max(0.0, min(1.0, weight_ratio))
        self.bottleneck_ratio = max(0.0, min(1.0, bottleneck_ratio))
        self.metric_mode = metric_mode
        self.is_back_edge = is_back_edge
        self.is_terminal_edge = is_terminal_edge
        self.is_start_edge = is_start_edge
        self.has_reverse = has_reverse
        self.layer_span = layer_span
        self.label_t = label_t
        self.side_offset = side_offset
        self.dark_canvas = dark_canvas
        self.mean_hours = mean_hours
        self.frequency = max(1, frequency)
        self.setZValue(2 if not is_back_edge else 1)
        if tooltip:
            self.setToolTip(tooltip)
        self._label_center = QPointF()
        self._arrow_poly = QPolygonF()
        self._build_curve()

    def _build_curve(self) -> None:
        path = QPainterPath(self.start_pt)
        dx = self.end_pt.x() - self.start_pt.x()
        dy = self.end_pt.y() - self.start_pt.y()

        if self.is_back_edge:
            side = (125.0 + abs(self.side_offset)) if dx >= 0 else -(125.0 + abs(self.side_offset))
            c1 = QPointF(self.start_pt.x() + side, self.start_pt.y() + 36.0)
            c2 = QPointF(self.end_pt.x() + side, self.end_pt.y() - 36.0)
        elif self.layer_span >= 2:
            bend = (115.0 + self.side_offset) if dx >= 0 else -(115.0 + self.side_offset)
            c1 = QPointF(self.start_pt.x() + bend, self.start_pt.y() + abs(dy) * 0.30)
            c2 = QPointF(self.end_pt.x() + bend, self.end_pt.y() - abs(dy) * 0.30)
        elif abs(dy) < 22.0:
            arch = -48.0 if not self.has_reverse else (-58.0 if dx > 0 else 58.0)
            c1 = QPointF(self.start_pt.x() + dx * 0.30, self.start_pt.y() + arch)
            c2 = QPointF(self.start_pt.x() + dx * 0.70, self.end_pt.y() + arch)
        else:
            v_pull = max(44.0, abs(dy) * 0.45)
            c1 = QPointF(self.start_pt.x() + self.side_offset, self.start_pt.y() + v_pull)
            c2 = QPointF(self.end_pt.x() + self.side_offset, self.end_pt.y() - v_pull)

        path.cubicTo(c1, c2, self.end_pt)
        self.setPath(path)
        self._label_center = path.pointAtPercent(self.label_t)

        p_prev = path.pointAtPercent(0.91)
        angle = math.atan2(self.end_pt.y() - p_prev.y(), self.end_pt.x() - p_prev.x())
        arrow_len = 11.0 + 4.0 * (self.bottleneck_ratio if self.metric_mode == "performance" else self.weight_ratio)
        arrow_angle = 0.44
        p1 = QPointF(
            self.end_pt.x() - arrow_len * math.cos(angle - arrow_angle),
            self.end_pt.y() - arrow_len * math.sin(angle - arrow_angle),
        )
        p2 = QPointF(
            self.end_pt.x() - arrow_len * math.cos(angle + arrow_angle),
            self.end_pt.y() - arrow_len * math.sin(angle + arrow_angle),
        )
        self._arrow_poly = QPolygonF([self.end_pt, p1, p2])

    def boundingRect(self) -> QRectF:
        return super().boundingRect().adjusted(-85.0, -35.0, 85.0, 35.0)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing, True)

        if self.is_terminal_edge:
            line_color = QColor("#65A30D" if self.is_start_edge else "#DC2626")
            lw = 1.8
            pen_style = Qt.DashLine
        elif self.metric_mode == "performance":
            # Disco Bottleneck Color Scale: Neutral Gray -> Brick Red -> Bold Crimson
            lw = 1.6 + 5.2 * self.bottleneck_ratio
            if self.bottleneck_ratio >= 0.45:
                line_color = _interpolate_color((185, 90, 90), (195, 24, 24), (self.bottleneck_ratio - 0.45) / 0.55)
            else:
                line_color = QColor("#94A3B8" if self.dark_canvas else "#78716C")
            pen_style = Qt.DashLine if self.is_back_edge else Qt.SolidLine
        else:
            # Frequency Mode: Slate -> Vivid Blue
            lw = 1.6 + 4.8 * self.weight_ratio
            if self.weight_ratio >= 0.35:
                line_color = QColor("#38BDF8" if self.dark_canvas else "#2563EB")
            else:
                line_color = QColor("#94A3B8" if self.dark_canvas else "#78716C")
            pen_style = Qt.DashLine if self.is_back_edge else Qt.SolidLine

        pen = QPen(line_color, lw, pen_style, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())

        painter.setPen(Qt.NoPen)
        painter.setBrush(line_color)
        painter.drawPolygon(self._arrow_poly)

        if self.label_text:
            is_hot = (self.metric_mode == "performance" and self.bottleneck_ratio >= 0.45)
            font = QFont("Segoe UI", 8.5 if is_hot else 8, QFont.Bold)
            painter.setFont(font)
            fm = painter.fontMetrics()
            pw = max(56.0, fm.horizontalAdvance(self.label_text) + 14.0)
            ph = 20.0
            pill_rect = QRectF(
                self._label_center.x() - pw / 2.0,
                self._label_center.y() - ph / 2.0,
                pw,
                ph,
            )
            bg_pill = QColor("#FEF2F2" if (is_hot and not self.dark_canvas) else ("#1E293B" if self.dark_canvas else "#FFFFFF"))
            border_pill = QColor("#B91C1C" if is_hot else ("#475569" if self.dark_canvas else "#A8A29E"))
            text_pill = QColor("#FCA5A5" if (is_hot and self.dark_canvas) else ("#991B1B" if is_hot else ("#F8FAFC" if self.dark_canvas else "#334155")))

            painter.setPen(QPen(border_pill, 1.4 if is_hot else 1.0))
            painter.setBrush(bg_pill)
            painter.drawRoundedRect(pill_rect, 4.0, 4.0)
            painter.setPen(text_pill)
            painter.drawText(pill_rect, Qt.AlignCenter, self.label_text)


class DfgTokenDotItem(QGraphicsEllipseItem):
    """Animated case token dot moving along a DFG transition path (Disco-style process animation)."""

    def __init__(self, edge: DfgEdgeCurveItem, phase: float, speed_step: float, color: QColor) -> None:
        self.r = 5.5
        super().__init__(-self.r, -self.r, self.r * 2, self.r * 2)
        self.edge = edge
        self.phase = phase % 1.0
        self.speed_step = speed_step
        self.setBrush(QBrush(color))
        self.setPen(QPen(QColor("#171717"), 1.3))
        self.setZValue(6)
        self.advance_token(0.0)

    def advance_token(self, speed_multiplier: float) -> None:
        self.phase = (self.phase + self.speed_step * speed_multiplier) % 1.0
        pt = self.edge.path().pointAtPercent(self.phase)
        self.setPos(pt)


class DfgInteractiveCanvas(QGraphicsView):
    """Disco-style Process Map with Bottleneck Heatmap and Live Token Flow Animation."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(
            QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.dark_canvas = False
        self._zoom = 1.0
        self._auto_fit_enabled = True

        # Live Animation Engine (Disco-style moving case tokens)
        self._edge_items: list[DfgEdgeCurveItem] = []
        self._tokens: list[DfgTokenDotItem] = []
        self._anim_speed: float = 1.0
        self._anim_running: bool = False
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(33)  # ~30 FPS
        self._anim_timer.timeout.connect(self._step_animation)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        bg = QColor("#0B1120" if self.dark_canvas else "#FAF8F5")
        painter.fillRect(rect, bg)

        grid_step = 26
        dot_color = QColor("#1E293B" if self.dark_canvas else "#E5E2DA")
        painter.setPen(QPen(dot_color, 1.5))

        left = int(math.floor(rect.left() / grid_step) * grid_step)
        top = int(math.floor(rect.top() / grid_step) * grid_step)
        right = int(rect.right())
        bottom = int(rect.bottom())
        if (right - left) / grid_step > 200 or (bottom - top) / grid_step > 200:
            return
        for x in range(left, right, grid_step):
            for y in range(top, bottom, grid_step):
                painter.drawPoint(x, y)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._auto_fit_enabled and not self._scene.itemsBoundingRect().isEmpty():
            self.reset_fit()

    def wheelEvent(self, event: QWheelEvent) -> None:
        self._auto_fit_enabled = False
        factor = 1.15 if event.angleDelta().y() > 0 else (1.0 / 1.15)
        new_zoom = self._zoom * factor
        if 0.20 <= new_zoom <= 2.8:
            self._zoom = new_zoom
            self.scale(factor, factor)

    def zoom_in(self) -> None:
        self._auto_fit_enabled = False
        if self._zoom * 1.2 <= 2.8:
            self._zoom *= 1.2
            self.scale(1.2, 1.2)

    def zoom_out(self) -> None:
        self._auto_fit_enabled = False
        if self._zoom / 1.2 >= 0.20:
            self._zoom /= 1.2
            self.scale(1.0 / 1.2, 1.0 / 1.2)

    def reset_fit(self) -> None:
        self._auto_fit_enabled = True
        self.resetTransform()
        self._zoom = 1.0
        bounds = self._scene.itemsBoundingRect()
        if not bounds.isEmpty():
            padded = bounds.adjusted(-45.0, -45.0, 45.0, 45.0)
            self._scene.setSceneRect(padded)
            if self.viewport().width() > 40 and self.viewport().height() > 40:
                self.fitInView(padded, Qt.KeepAspectRatio)

    # ------------------------------------------------------------------
    # Disco-style Token Flow Animation Controls
    # ------------------------------------------------------------------
    def set_animation_speed(self, multiplier: float) -> None:
        self._anim_speed = max(0.25, min(5.0, multiplier))

    def start_animation(self) -> None:
        if not self._edge_items:
            return
        if not self._tokens:
            self._spawn_tokens()
        self._anim_running = True
        self._anim_timer.start()

    def stop_animation(self) -> None:
        self._anim_running = False
        self._anim_timer.stop()

    def clear_tokens(self) -> None:
        self.stop_animation()
        for tok in self._tokens:
            if tok.scene() is self._scene:
                self._scene.removeItem(tok)
        self._tokens.clear()

    def _spawn_tokens(self) -> None:
        self.clear_tokens()
        if not self._edge_items:
            return
        max_freq = max((e.frequency for e in self._edge_items), default=1) or 1
        for edge in self._edge_items:
            # More tokens on higher-frequency paths; slower movement on bottleneck paths (visual congestion!)
            n_dots = max(1, min(4, int(round(1 + 3 * (edge.frequency / float(max_freq))))))
            if edge.bottleneck_ratio >= 0.45:
                step = 0.0045  # Slow down noticeably on red bottleneck edges so congestion is obvious
                dot_color = QColor("#EF4444")
            elif edge.is_terminal_edge:
                step = 0.015
                dot_color = QColor("#22C55E" if edge.is_start_edge else "#F97316")
            else:
                step = 0.012 + 0.008 * (1.0 - edge.bottleneck_ratio)
                dot_color = QColor("#F6D65B")

            for i in range(n_dots):
                tok = DfgTokenDotItem(edge, phase=i / float(n_dots), speed_step=step, color=dot_color)
                self._scene.addItem(tok)
                self._tokens.append(tok)

    def _step_animation(self) -> None:
        for tok in self._tokens:
            tok.advance_token(self._anim_speed)

    # ------------------------------------------------------------------
    # Render Process Map
    # ------------------------------------------------------------------
    def render_dfg(
        self,
        edges: list[dict[str, Any]],
        metric_mode: str = "performance",
        dark_canvas: bool = False,
    ) -> dict[str, Any]:
        """Render Disco-style Top-to-Bottom Process Map with Bottleneck Heatmap & Start/End markers."""
        was_animating = self._anim_running
        self.clear_tokens()
        self._edge_items.clear()
        self.dark_canvas = dark_canvas
        self._scene.clear()
        self.resetTransform()
        self._zoom = 1.0

        if not edges:
            msg = self._scene.addText(
                "Import an XES event log and click '▶ Run DFG' to render the Disco-style Process Map.",
                QFont("Segoe UI", 11, QFont.Bold),
            )
            msg.setDefaultTextColor(QColor("#94A3B8" if dark_canvas else "#525252"))
            self._scene.setSceneRect(msg.boundingRect().adjusted(-80, -80, 80, 80))
            self.reset_fit()
            return {"nodes": 0, "edges": 0, "bottleneck": None}

        # 1. Collect node metadata and incoming wait times (for node bottleneck heatmap)
        nodes_meta: dict[str, dict[str, Any]] = {}
        node_in_hours: dict[str, list[float]] = {}
        for e in edges:
            src = str(e["source_activity"])
            dst = str(e["target_activity"])
            node_in_hours.setdefault(dst, []).append(float(e.get("mean_hours", 0.0)))
            for act, raw_m in ((src, e.get("source_meta") or {}), (dst, e.get("target_meta") or {})):
                if act not in nodes_meta:
                    nodes_meta[act] = {
                        "activity": act,
                        "event_count": int(raw_m.get("event_count", e.get("frequency", 1))),
                        "case_count": int(raw_m.get("case_count", e.get("case_count", e.get("frequency", 1)))),
                        "start_count": int(raw_m.get("start_count", 0)),
                        "end_count": int(raw_m.get("end_count", 0)),
                        "avg_rank": float(raw_m.get("avg_rank", 0.0)),
                    }

        # 2. Sort nodes Top-to-Bottom by average trace rank
        sorted_nodes = sorted(
            nodes_meta.values(),
            key=lambda m: (
                0 if m["start_count"] > m["end_count"] and m["avg_rank"] < 1.5 else 1,
                m["avg_rank"],
                -m["event_count"],
            ),
        )

        max_cols_per_row = 3 if len(sorted_nodes) >= 6 else 2
        layers: list[list[str]] = []
        current_layer: list[str] = []
        last_rank: float | None = None
        for item in sorted_nodes:
            act_name = item["activity"]
            r = item["avg_rank"]
            if not current_layer:
                current_layer.append(act_name)
                last_rank = r
            elif len(current_layer) < max_cols_per_row and (last_rank is not None and abs(r - last_rank) <= 2.2):
                current_layer.append(act_name)
            else:
                layers.append(current_layer)
                current_layer = [act_name]
                last_rank = r
        if current_layer:
            layers.append(current_layer)

        # 3. Compute bottleneck ratios
        max_ev = max((m["event_count"] for m in nodes_meta.values()), default=1) or 1
        max_edge_hours = max((float(e.get("mean_hours", 0.0)) for e in edges), default=0.0)
        max_node_wait = max(
            (sum(v) / len(v) for v in node_in_hours.values() if v),
            default=0.0,
        )

        # Add Disco Green START Marker at top
        start_marker = DfgTerminalNodeItem(is_start=True, x=0.0, y=-86.0, dark_canvas=dark_canvas)
        self._scene.addItem(start_marker)

        node_positions: dict[str, tuple[float, float]] = {}
        node_layer_idx: dict[str, int] = {}

        for row_idx, row_nodes in enumerate(layers):
            row_width = (len(row_nodes) - 1) * H_SPACING
            start_x = -row_width / 2.0 - NODE_WIDTH / 2.0
            y = row_idx * V_SPACING
            for col_idx, act_name in enumerate(row_nodes):
                x = start_x + col_idx * H_SPACING
                node_positions[act_name] = (x, y)
                node_layer_idx[act_name] = row_idx
                meta = nodes_meta[act_name]
                in_hrs = node_in_hours.get(act_name, [])
                avg_wait = (sum(in_hrs) / len(in_hrs)) if in_hrs else 0.0

                if metric_mode == "performance":
                    heat = (avg_wait / max_node_wait) if max_node_wait > 0 else 0.0
                    subtitle = f"Avg wait: {_format_duration_human(avg_wait)}  •  {meta['case_count']:,}c"
                else:
                    heat = meta["event_count"] / float(max_ev)
                    subtitle = f"{meta['case_count']:,} cases  •  {meta['event_count']:,} events"

                card = DfgNodeCardItem(
                    activity=act_name,
                    meta=meta,
                    heat_ratio=heat,
                    metric_mode=metric_mode,
                    subtitle_metric=subtitle,
                    x=x,
                    y=y,
                    dark_canvas=dark_canvas,
                )
                card.setZValue(3)
                self._scene.addItem(card)

        # Add Disco Red END Marker at bottom
        bottom_y = len(layers) * V_SPACING + 22.0
        end_marker = DfgTerminalNodeItem(is_start=False, x=0.0, y=bottom_y, dark_canvas=dark_canvas)
        self._scene.addItem(end_marker)

        # Connect START marker to top-layer / start activities
        start_targets = [a for a in layers[0]] if layers else []
        for act_name in start_targets[:2]:
            tx, ty = node_positions[act_name]
            s_edge = DfgEdgeCurveItem(
                start_pt=QPointF(0.0, -68.0),
                end_pt=QPointF(tx + NODE_WIDTH / 2.0, ty),
                label_text="",
                weight_ratio=0.5,
                bottleneck_ratio=0.0,
                metric_mode=metric_mode,
                is_terminal_edge=True,
                is_start_edge=True,
                dark_canvas=dark_canvas,
                frequency=nodes_meta[act_name]["case_count"],
            )
            self._scene.addItem(s_edge)
            self._edge_items.append(s_edge)

        # Connect bottom-layer / end activities to END marker
        end_sources = [a for a in layers[-1]] if layers else []
        for act_name in end_sources[:2]:
            sx, sy = node_positions[act_name]
            e_edge = DfgEdgeCurveItem(
                start_pt=QPointF(sx + NODE_WIDTH / 2.0, sy + NODE_HEIGHT),
                end_pt=QPointF(0.0, bottom_y - 18.0),
                label_text="",
                weight_ratio=0.5,
                bottleneck_ratio=0.0,
                metric_mode=metric_mode,
                is_terminal_edge=True,
                is_start_edge=False,
                dark_canvas=dark_canvas,
                frequency=nodes_meta[act_name]["case_count"],
            )
            self._scene.addItem(e_edge)
            self._edge_items.append(e_edge)

        # 4. Build inter-activity edges with distributed ports and Bottleneck Highlighting
        max_freq = max((int(e["frequency"]) for e in edges), default=1) or 1
        pair_set = {(str(e["source_activity"]), str(e["target_activity"])) for e in edges}
        out_edges_by_src: dict[str, list[int]] = {}
        in_edges_by_dst: dict[str, list[int]] = {}
        for idx_e, e in enumerate(edges):
            s_a, t_a = str(e["source_activity"]), str(e["target_activity"])
            if s_a in node_positions and t_a in node_positions:
                out_edges_by_src.setdefault(s_a, []).append(idx_e)
                in_edges_by_dst.setdefault(t_a, []).append(idx_e)

        def _port_x(base_x: float, slot_idx: int, total_slots: int) -> float:
            if total_slots <= 1:
                return base_x + NODE_WIDTH / 2.0
            usable = NODE_WIDTH - 56.0
            step = usable / float(total_slots - 1)
            return base_x + 28.0 + slot_idx * step

        slowest_edge: dict[str, Any] | None = None
        for idx_e, e in enumerate(edges):
            src = str(e["source_activity"])
            dst = str(e["target_activity"])
            if src not in node_positions or dst not in node_positions:
                continue
            freq = int(e["frequency"])
            cases = int(e.get("case_count", freq))
            hours = float(e.get("mean_hours", 0.0))
            if slowest_edge is None or hours > float(slowest_edge.get("mean_hours", 0.0)):
                slowest_edge = e

            b_ratio = (hours / max_edge_hours) if max_edge_hours > 0 else 0.0
            if metric_mode == "performance":
                label_text = _format_duration_human(hours)
            else:
                label_text = f"{freq:,} ({cases:,}c)"

            sx, sy = node_positions[src]
            tx, ty = node_positions[dst]
            s_layer = node_layer_idx[src]
            t_layer = node_layer_idx[dst]
            has_rev = (dst, src) in pair_set and src != dst
            layer_span = abs(t_layer - s_layer)

            out_list = out_edges_by_src.get(src, [idx_e])
            in_list = in_edges_by_dst.get(dst, [idx_e])
            out_slot = out_list.index(idx_e)
            in_slot = in_list.index(idx_e)

            side_offset = 0.0
            label_t = 0.5
            if src == dst:
                start_pt = QPointF(sx + NODE_WIDTH, sy + NODE_HEIGHT * 0.28)
                end_pt = QPointF(sx + NODE_WIDTH, sy + NODE_HEIGHT * 0.72)
                is_back = True
            elif t_layer > s_layer:
                start_pt = QPointF(_port_x(sx, out_slot, len(out_list)), sy + NODE_HEIGHT)
                end_pt = QPointF(_port_x(tx, in_slot, len(in_list)), ty)
                is_back = False
                if has_rev:
                    label_t = 0.36
                    side_offset = 22.0
                elif layer_span >= 2:
                    side_offset = 28.0 * (out_slot + 1)
                    label_t = 0.45
            elif t_layer < s_layer:
                start_pt = QPointF(sx + NODE_WIDTH, sy + NODE_HEIGHT * 0.5)
                end_pt = QPointF(tx + NODE_WIDTH, ty + NODE_HEIGHT * 0.5)
                is_back = True
                label_t = 0.64 if has_rev else 0.5
                side_offset = 22.0 * (out_slot + 1)
            else:
                if tx > sx:
                    start_pt = QPointF(sx + NODE_WIDTH, sy + NODE_HEIGHT * 0.40)
                    end_pt = QPointF(tx, ty + NODE_HEIGHT * 0.40)
                    label_t = 0.40 if has_rev else 0.5
                else:
                    start_pt = QPointF(sx, sy + NODE_HEIGHT * 0.64)
                    end_pt = QPointF(tx + NODE_WIDTH, ty + NODE_HEIGHT * 0.64)
                    label_t = 0.60 if has_rev else 0.5
                is_back = False

            edge_tooltip = (
                f"{src}  →  {dst}\n"
                f"Avg Waiting/Transition Time: {_format_duration_human(hours)} ({hours:.2f} hrs)\n"
                f"Frequency: {freq:,} transitions ({cases:,} unique cases)"
            )
            edge_item = DfgEdgeCurveItem(
                start_pt=start_pt,
                end_pt=end_pt,
                label_text=label_text,
                weight_ratio=freq / float(max_freq),
                bottleneck_ratio=b_ratio,
                metric_mode=metric_mode,
                is_back_edge=is_back,
                has_reverse=has_rev,
                layer_span=layer_span,
                label_t=label_t,
                side_offset=side_offset,
                dark_canvas=dark_canvas,
                tooltip=edge_tooltip,
                mean_hours=hours,
                frequency=freq,
            )
            self._scene.addItem(edge_item)
            self._edge_items.append(edge_item)

        bounds = self._scene.itemsBoundingRect().adjusted(-55.0, -45.0, 55.0, 45.0)
        self._scene.setSceneRect(bounds)
        self.reset_fit()
        self.viewport().update()

        if was_animating:
            self.start_animation()

        bn_summary = None
        if slowest_edge is not None:
            bn_summary = (
                f"{slowest_edge['source_activity']} → {slowest_edge['target_activity']} "
                f"({_format_duration_human(float(slowest_edge.get('mean_hours', 0.0)))})"
            )
        return {"nodes": len(nodes_meta), "edges": len(edges), "bottleneck": bn_summary}
