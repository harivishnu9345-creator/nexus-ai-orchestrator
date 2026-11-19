import os
import math
import time
from typing import Dict, List, Callable, Tuple, Optional
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, pyqtSignal, QEvent
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QPolygonF, QNativeGestureEvent
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QRadioButton,
    QButtonGroup, QComboBox, QFrame, QGraphicsView, QGraphicsScene,
    QGraphicsObject, QGraphicsPathItem, QGraphicsItem, QMenu, QMessageBox,
    QPinchGesture, QProgressBar, QFileDialog
)

TEMPLATE_DUMMY_FILENAMES = {
    "filename.ext", "raw_filename.ext", "filename1.ext", "filename2.ext",
    "exact_filename1", "exact_filename2", "name.ext"
}


class ZoomableGraphView(QGraphicsView):
    """QGraphicsView with smooth click-and-drag panning on empty space and pinch zoom."""

    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.TextAntialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.grabGesture(Qt.GestureType.PinchGesture)
        self.viewport().grabGesture(Qt.GestureType.PinchGesture)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            if item is None:
                # Clicked on empty space: engage smooth grab-and-pan
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        super().mousePressEvent(event)

    def _apply_zoom(self, factor: float):
        factor = max(0.86, min(1.16, factor))
        curr = self.transform().m11()
        if (curr <= 0.25 and factor < 1.0) or (curr >= 3.2 and factor > 1.0):
            return
        self.scale(factor, factor)

    def wheelEvent(self, event):
        angle = event.angleDelta().y()
        if angle == 0:
            angle = event.pixelDelta().y()
        if angle != 0:
            factor = 1.12 if angle > 0 else (1.0 / 1.12)
            self._apply_zoom(factor)
            event.accept()
            return
        super().wheelEvent(event)

    def viewportEvent(self, evt):
        etype = evt.type()
        if etype == QEvent.Type.NativeGesture and isinstance(evt, QNativeGestureEvent):
            if evt.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                self._apply_zoom(1.0 + evt.value())
                evt.accept()
                return True
        elif etype == QEvent.Type.Gesture:
            pinch = evt.gesture(Qt.GestureType.PinchGesture)
            if isinstance(pinch, QPinchGesture):
                last_sf = pinch.lastScaleFactor()
                curr_sf = pinch.scaleFactor()
                step = (curr_sf / last_sf) if (last_sf and last_sf > 0.001) else curr_sf
                if 0.5 < step < 2.0 and abs(step - 1.0) > 1e-3:
                    self._apply_zoom(step)
                evt.accept()
                return True
        return super().viewportEvent(evt)


class PrimaryTreeEdgeItem(QGraphicsPathItem):
    """
    THICK Primary Line (3.5px) connecting nodes and intermediate gate boxes:
    - Bright Green (#10b981): Completed / Relayed
    - Bright Orange (#f97316): Currently Running / Awaiting Approval
    - Bright Red (#ef4444): Waiting / Sleeping
    """

    def __init__(self, source_node: QGraphicsObject, target_node: QGraphicsObject):
        super().__init__()
        self.source_node = source_node
        self.target_node = target_node
        self.is_active_flow = False
        self.is_completed = False
        self.pulse_t = 0.0
        self.setPen(QPen(Qt.GlobalColor.transparent, 12.0))
        self.setZValue(1)
        self.update_position()

    def boundingRect(self) -> QRectF:
        return super().boundingRect().adjusted(-14.0, -14.0, 14.0, 14.0)

    def update_position(self):
        if not self.source_node or not self.target_node:
            return
        self.prepareGeometryChange()
        s_rect = self.source_node.sceneBoundingRect()
        t_rect = self.target_node.sceneBoundingRect()

        if abs(t_rect.center().y() - s_rect.center().y()) > 65 and abs(t_rect.center().x() - s_rect.center().x()) < 260:
            start = QPointF(s_rect.center().x(), s_rect.bottom())
            end = QPointF(t_rect.center().x(), t_rect.top())
            dy = max(35.0, abs(end.y() - start.y()) * 0.5)
            c1 = QPointF(start.x(), start.y() + dy)
            c2 = QPointF(end.x(), end.y() - dy)
        else:
            start = QPointF(s_rect.right(), s_rect.center().y())
            end = QPointF(t_rect.left(), t_rect.center().y())
            dx = max(35.0, abs(end.x() - start.x()) * 0.5)
            c1 = QPointF(start.x() + dx, start.y())
            c2 = QPointF(end.x() - dx, end.y())

        path = QPainterPath(start)
        path.cubicTo(c1, c2, end)
        self.setPath(path)

    def paint(self, painter: QPainter, option, widget=None):
        path = self.path()
        if path.isEmpty():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        s_stat = getattr(self.source_node, "status", "WAITING").upper()
        t_stat = getattr(self.target_node, "status", "WAITING").upper()
        s_is_master = getattr(self.source_node, "is_master", False)

        if s_is_master:
            # Master Architect -> L1 Branch lines show Blueprint Delegation state:
            # Green once Master is COMPLETED and branch has started/completed; Orange only while Master is actively generating
            if s_stat in ("RUNNING", "GENERATING", "ACTIVE"):
                line_col = QColor("#f97316")
            elif t_stat in ("COMPLETED", "CACHED", "VERIFIED", "DONE", "RUNNING", "GENERATING", "ACTIVE"):
                line_col = QColor("#10b981")
            else:
                line_col = QColor("#52525b")
        else:
            if t_stat in ("TOKEN_EXHAUSTED", "EXHAUSTED") or s_stat in ("TOKEN_EXHAUSTED", "EXHAUSTED"):
                line_col = QColor("#a855f7")  # Bright Purple (Token Exhausted)
            elif t_stat in ("COMPLETED", "CACHED", "VERIFIED", "DONE", "RELAYED"):
                line_col = QColor("#10b981")  # Bright Green
            elif t_stat in ("RUNNING", "GENERATING", "VERIFYING", "ACTIVE", "AWAITING_APPROVAL"):
                line_col = QColor("#f97316")  # Bright Orange
            else:
                line_col = QColor("#ef4444")  # Bright Red

        glow_pen = QPen(QColor(line_col.red(), line_col.green(), line_col.blue(), 55), 7.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(glow_pen)
        painter.drawPath(path)

        primary_pen = QPen(line_col, 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(primary_pen)
        painter.drawPath(path)

        if path.length() > 20:
            end_pt = path.pointAtPercent(1.0)
            prev_pt = path.pointAtPercent(max(0.0, 1.0 - (14.0 / path.length())))
            angle = math.atan2(end_pt.y() - prev_pt.y(), end_pt.x() - prev_pt.x())
            arrow_size = 9.0
            p_a = QPointF(
                end_pt.x() - arrow_size * math.cos(angle - math.pi / 6),
                end_pt.y() - arrow_size * math.sin(angle - math.pi / 6)
            )
            p_b = QPointF(
                end_pt.x() - arrow_size * math.cos(angle + math.pi / 6),
                end_pt.y() - arrow_size * math.sin(angle + math.pi / 6)
            )
            painter.setBrush(QBrush(line_col))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(QPolygonF([end_pt, p_a, p_b]))

        if self.is_active_flow:
            pt = path.pointAtPercent(self.pulse_t)
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.setPen(QPen(QColor("#f97316"), 2.0))
            painter.drawEllipse(pt, 5.5, 5.5)


class PerimeterRequestEdgeItem(QGraphicsObject):
    """
    Non-Intersecting Outer-Corridor Line for Explicit File Requests:
    - Routes strictly around the top/bottom outer perimeter so it NEVER touches node cards!
    - Bright Red (#ef4444) when REQUESTED.
    - Bright Green (#10b981) when COMPLETED / RELAYED.
    """
    request_clicked = pyqtSignal(object)

    def __init__(
        self,
        source_node: "TreeGraphNodeItem",
        target_node: "TreeGraphNodeItem",
        file_name: str,
        file_path: str = "",
        status: str = "REQUESTED",
        corridor_index: int = 0
    ):
        super().__init__()
        self.source_node = source_node
        self.target_node = target_node
        self.file_name = file_name
        self.file_path = file_path
        self.status = status.upper()
        self.corridor_index = corridor_index
        self.pulse_t = 0.0
        self._path = QPainterPath()
        self._pill_rect = QRectF()
        self.setZValue(5)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_position()

    def boundingRect(self) -> QRectF:
        return self._path.boundingRect().united(self._pill_rect).adjusted(-20, -20, 20, 20)

    def shape(self) -> QPainterPath:
        p = QPainterPath()
        p.addRoundedRect(self._pill_rect, 8.0, 8.0)
        return p

    def update_position(self):
        if not self.source_node or not self.target_node:
            return
        self.prepareGeometryChange()
        s_rect = self.source_node.sceneBoundingRect()
        t_rect = self.target_node.sceneBoundingRect()

        # Route via an outer bottom corridor below both cards so it never intersects any box
        corridor_y = max(s_rect.bottom(), t_rect.bottom()) + 48.0 + (self.corridor_index * 28.0)
        start = QPointF(s_rect.center().x(), s_rect.bottom())
        end = QPointF(t_rect.center().x(), t_rect.bottom())

        path = QPainterPath(start)
        path.lineTo(QPointF(start.x(), corridor_y))
        path.lineTo(QPointF(end.x(), corridor_y))
        path.lineTo(end)
        self._path = path

        mid_x = (start.x() + end.x()) / 2.0
        pill_w = 210.0
        pill_h = 22.0
        self._pill_rect = QRectF(mid_x - pill_w / 2.0, corridor_y - pill_h / 2.0, pill_w, pill_h)

    def paint(self, painter: QPainter, option, widget=None):
        if self._path.isEmpty():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        is_done = self.status in ("RELAYED", "COMPLETED")
        col = QColor("#10b981" if is_done else "#ef4444")
        pen_style = Qt.PenStyle.SolidLine if is_done else Qt.PenStyle.DashLine

        painter.setPen(QPen(col, 2.2, pen_style, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._path)

        painter.setBrush(QBrush(QColor("#052e16" if is_done else "#2a0808")))
        painter.setPen(QPen(col, 1.5))
        painter.drawRoundedRect(self._pill_rect, 8.0, 8.0)

        label = f"\U0001f7e2 COMPLETED: {self.file_name[:18]}" if is_done else f"\U0001f534 REQUESTED: {self.file_name[:18]}"
        painter.setPen(QPen(QColor("#ffffff")))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(self._pill_rect, Qt.AlignmentFlag.AlignCenter, label)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._pill_rect.contains(event.pos()):
            self.request_clicked.emit(self)
            event.accept()
            return
        super().mousePressEvent(event)


class InlineGateCardItem(QGraphicsObject):
    """
    Intermediate Gate Box placed directly IN BETWEEN two accounts on the canvas!
    - Replaces the detached right-side panel completely.
    - Color-coded border:
        * Bright Red (#ef4444): LOCKED / WAITING (upstream stage still working)
        * Bright Orange (#f97316): AWAITING_APPROVAL (ready for user to review checkboxes & click Approve)
        * Bright Green (#10b981): RELAYED / COMPLETED
    - Contains interactive clickable checkboxes right inside the card:
        * Upstream ===SUMMARY=== checkboxes (★ Recommended auto-checked, others unchecked)
        * Harvested/Vault File checkboxes (★ Recommended auto-checked, others unchecked)
        * [+ Attach File] and [🚀 Approve & Push] buttons
    """
    gate_moved = pyqtSignal()
    approve_clicked = pyqtSignal(int)
    attach_file_clicked = pyqtSignal(int)

    WIDTH = 235.0

    def __init__(
        self,
        gate_index: int,
        from_stage_num: int,
        to_stage_num: int,
        to_account_name: str,
        status: str = "LOCKED"
    ):
        super().__init__()
        self.gate_index = gate_index
        self.from_stage_num = from_stage_num
        self.to_stage_num = to_stage_num
        self.to_account_name = to_account_name
        self.status = status.upper()  # "LOCKED", "AWAITING_APPROVAL", "RELAYED"

        # List of dicts: {"id": producer_id, "label": "Stage 1 Summary", "checked": True, "recommended": True, "rect": QRectF()}
        self.summary_items: List[dict] = []
        # List of dicts: {"path": fpath, "filename": fname, "checked": True, "recommended": True, "requested": False, "rect": QRectF()}
        self.file_items: List[dict] = []

        self._btn_attach_rect = QRectF()
        self._btn_approve_rect = QRectF()

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setZValue(4)

    def current_height(self) -> float:
        sum_rows = max(1, min(3, len(self.summary_items)))
        file_rows = max(1, min(6, len(self.file_items)))
        return 46.0 + 18.0 + (sum_rows * 16.0) + 18.0 + (file_rows * 16.0) + 32.0

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.WIDTH, self.current_height())

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.gate_moved.emit()
        return super().itemChange(change, value)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.current_height()
        rect = QRectF(0, 0, self.WIDTH, h)

        st = self.status.upper()
        if st in ("RELAYED", "COMPLETED"):
            border_col = QColor("#10b981")  # Bright Green
            header_bg = QColor("#052e16")
            status_lbl = "\u2713 RELAYED TO STAGE " + str(self.to_stage_num)
        elif st in ("AWAITING_APPROVAL", "READY", "RUNNING"):
            border_col = QColor("#f97316")  # Bright Orange (Current Approval Step!)
            header_bg = QColor("#431407")
            status_lbl = "\u23f8 AWAITING APPROVAL (READY)"
        else:
            border_col = QColor("#ef4444")  # Bright Red (Locked / Waiting)
            header_bg = QColor("#2a0808")
            status_lbl = "\U0001f512 WAITING FOR STAGE " + str(self.from_stage_num)

        painter.setBrush(QBrush(QColor("#141417")))
        painter.setPen(QPen(border_col, 2.4))
        painter.drawRoundedRect(rect, 7.0, 7.0)

        # 1. Top Gate Banner
        hdr_rect = QRectF(0, 0, self.WIDTH, 22.0)
        painter.setBrush(QBrush(header_bg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(hdr_rect, 7.0, 7.0)

        painter.setPen(QPen(border_col))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(
            hdr_rect.adjusted(8, 0, -8, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            f"GATE {self.from_stage_num}\u2192{self.to_stage_num}: -> {self.to_account_name[:14]}"
        )

        # 2. Status Subtitle
        painter.setPen(QPen(border_col))
        painter.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
        painter.drawText(QRectF(8, 23, self.WIDTH - 16, 15), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, status_lbl)

        y_cursor = 41.0

        # 3. Upstream Summaries Section
        painter.setPen(QPen(QColor("#38bdf8")))
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.drawText(QRectF(8, y_cursor, self.WIDTH - 16, 14), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "UPSTREAM ===SUMMARY=== TO INJECT:")
        y_cursor += 15.0

        painter.setFont(QFont("Consolas", 7))
        if not self.summary_items:
            painter.setPen(QPen(QColor("#71717a")))
            painter.drawText(QRectF(10, y_cursor, self.WIDTH - 20, 15), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "[ ] (Awaiting Stage Summary...)")
            y_cursor += 16.0
        else:
            for s_item in self.summary_items[:3]:
                row_r = QRectF(8, y_cursor, self.WIDTH - 16, 15.0)
                s_item["rect"] = row_r
                box_sym = "[\u2713]" if s_item.get("checked") else "[ ]"
                star = "\u2605 " if s_item.get("recommended") else ""
                painter.setPen(QPen(QColor("#38bdf8") if s_item.get("checked") else QColor("#a1a1aa")))
                painter.drawText(row_r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"{box_sym} {star}{s_item['label'][:25]}")
                y_cursor += 16.0

        y_cursor += 2.0

        # 4. Harvested & Vault Files Checklist Section
        painter.setPen(QPen(QColor("#10b981")))
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.drawText(QRectF(8, y_cursor, self.WIDTH - 16, 14), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "FILES (\u2605=RECOMMENDED, UNCHECKED=OTHER):")
        y_cursor += 15.0

        painter.setFont(QFont("Consolas", 7))
        if not self.file_items:
            painter.setPen(QPen(QColor("#71717a")))
            painter.drawText(QRectF(10, y_cursor, self.WIDTH - 20, 15), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "[ ] (Awaiting Stage Files...)")
            y_cursor += 16.0
        else:
            for f_item in self.file_items[:6]:
                row_r = QRectF(8, y_cursor, self.WIDTH - 16, 15.0)
                f_item["rect"] = row_r
                box_sym = "[\u2713]" if f_item.get("checked") else "[ ]"
                if f_item.get("recommended"):
                    tag = "\u2605Rec: "
                    col = QColor("#10b981") if f_item.get("checked") else QColor("#a1a1aa")
                elif f_item.get("requested"):
                    tag = "\u26a1Req: "
                    col = QColor("#f97316")
                else:
                    tag = ""
                    col = QColor("#e4e4e7") if f_item.get("checked") else QColor("#71717a")
                painter.setPen(QPen(col))
                painter.drawText(row_r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"{box_sym} {tag}{f_item['filename'][:21]}")
                y_cursor += 16.0

        # 5. Bottom Action Buttons inside the Inline Gate Box: [+ Attach] & [🚀 Approve & Push]
        btn_y = h - 25.0
        self._btn_attach_rect = QRectF(8, btn_y, 68, 20.0)
        self._btn_approve_rect = QRectF(80, btn_y, self.WIDTH - 88, 20.0)

        painter.setBrush(QBrush(QColor("#1f1f23")))
        painter.setPen(QPen(QColor("#52525b"), 1.0))
        painter.drawRoundedRect(self._btn_attach_rect, 3.0, 3.0)
        painter.setPen(QPen(QColor("#e4e4e7")))
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.drawText(self._btn_attach_rect, Qt.AlignmentFlag.AlignCenter, "+ Attach File")

        btn_bg = QColor("#ea580c") if st == "AWAITING_APPROVAL" else (QColor("#059669") if st == "RELAYED" else QColor("#27272a"))
        painter.setBrush(QBrush(btn_bg))
        painter.setPen(QPen(border_col, 1.0))
        painter.drawRoundedRect(self._btn_approve_rect, 3.0, 3.0)
        painter.setPen(QPen(QColor("#ffffff")))
        btn_txt = "\U0001f680 Approve & Push ->" if st != "RELAYED" else "\u2713 Pushed (Re-Send)"
        painter.drawText(self._btn_approve_rect, Qt.AlignmentFlag.AlignCenter, btn_txt)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            for s_item in self.summary_items[:3]:
                if s_item.get("rect") and s_item["rect"].contains(pos):
                    s_item["checked"] = not s_item.get("checked", False)
                    self.update()
                    event.accept()
                    return
            for f_item in self.file_items[:6]:
                if f_item.get("rect") and f_item["rect"].contains(pos):
                    f_item["checked"] = not f_item.get("checked", False)
                    self.update()
                    event.accept()
                    return
            if self._btn_attach_rect.contains(pos):
                self.attach_file_clicked.emit(self.gate_index)
                event.accept()
                return
            if self._btn_approve_rect.contains(pos):
                self.approve_clicked.emit(self.gate_index)
                event.accept()
                return
        super().mousePressEvent(event)


class FailoverBranchEdgeItem(QGraphicsPathItem):
    """Purple failover branch line connecting a TOKEN_EXHAUSTED node to its newly added replacement node."""

    def __init__(self, source_node: QGraphicsObject, target_node: QGraphicsObject, remaining_files: List[str]):
        super().__init__()
        self.source_node = source_node
        self.target_node = target_node
        self.remaining_files = list(remaining_files or [])
        self._pill_rect = QRectF()
        self.setZValue(6)
        self.update_position()

    def boundingRect(self) -> QRectF:
        return super().boundingRect().united(self._pill_rect).adjusted(-18.0, -18.0, 18.0, 18.0)

    def update_position(self):
        if not self.source_node or not self.target_node:
            return
        self.prepareGeometryChange()
        s_rect = self.source_node.sceneBoundingRect()
        t_rect = self.target_node.sceneBoundingRect()
        start = QPointF(s_rect.right(), s_rect.center().y())
        end = QPointF(t_rect.left(), t_rect.center().y())
        dx = max(45.0, abs(end.x() - start.x()) * 0.45)
        c1 = QPointF(start.x() + dx, start.y() - 35.0)
        c2 = QPointF(end.x() - dx, end.y() - 35.0)
        path = QPainterPath(start)
        path.cubicTo(c1, c2, end)
        self.setPath(path)

        mid = path.pointAtPercent(0.5)
        self._pill_rect = QRectF(mid.x() - 105.0, mid.y() - 11.0, 210.0, 22.0)

    def paint(self, painter: QPainter, option, widget=None):
        path = self.path()
        if path.isEmpty():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        purple = QColor("#a855f7")

        painter.setPen(QPen(QColor(168, 85, 247, 70), 6.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        painter.setPen(QPen(purple, 2.6, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(path)

        painter.setBrush(QBrush(QColor("#3b0764")))
        painter.setPen(QPen(purple, 1.5))
        painter.drawRoundedRect(self._pill_rect, 7.0, 7.0)

        files_preview = ", ".join(self.remaining_files[:2]) if self.remaining_files else "Remaining Tasks"
        if len(self.remaining_files) > 2:
            files_preview += f" +{len(self.remaining_files) - 2}"
        painter.setPen(QPen(QColor("#f3e8ff")))
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.drawText(self._pill_rect, Qt.AlignmentFlag.AlignCenter, f"⚡ FAILOVER: {files_preview[:24]}")


class TreeGraphNodeItem(QGraphicsObject):
    """
    Rich Node Card:
    - Bright Green (#10b981) for COMPLETED / Harvested.
    - Bright Orange (#f97316) for RUNNING / Generating.
    - Bright Red (#ef4444) for WAITING / Sleeping.
    """
    node_moved = pyqtSignal()
    node_selected_for_relay = pyqtSignal(object)
    swap_account_requested = pyqtSignal(object)
    move_worker_offset = pyqtSignal(object, int)
    force_complete_requested = pyqtSignal(str)

    WIDTH = 250.0

    def __init__(
        self,
        node_index: int,
        account_id: str,
        account_name: str,
        platform: str,
        tree_role: str = "L2: LEAF WORKER",
        status: str = "WAITING",
        is_master: bool = False
    ):
        super().__init__()
        self.node_index = node_index
        self.account_id = account_id
        self.account_name = account_name
        self.platform = (platform or "claude").lower()
        self.tree_role = tree_role
        self.status = status.upper()
        self.is_master = is_master
        self.can_move_left = False
        self.can_move_right = False

        self.assigned_files: List[str] = []
        self.cached_files: Dict[str, str] = {}
        self._saw_streaming: bool = False
        self._busy_since: float = 0.0

        self._btn_left_rect = QRectF()
        self._btn_right_rect = QRectF()
        self._btn_force_rect = QRectF()

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setZValue(3)

    def _compute_file_rows(self) -> List[Tuple[str, bool]]:
        rows: List[Tuple[str, bool]] = []
        seen = set()
        for fn in self.assigned_files:
            clean_fn = os.path.basename(fn.strip())
            if clean_fn and clean_fn.lower() not in TEMPLATE_DUMMY_FILENAMES and clean_fn not in seen:
                seen.add(clean_fn)
                rows.append((clean_fn, clean_fn in self.cached_files))
        for fn in self.cached_files.keys():
            clean_fn = os.path.basename(fn.strip())
            if clean_fn and clean_fn.lower() not in TEMPLATE_DUMMY_FILENAMES and clean_fn not in seen:
                seen.add(clean_fn)
                rows.append((clean_fn, True))
        return rows

    def current_height(self) -> float:
        if self.is_master:
            return 118.0
        rows = self._compute_file_rows()
        visible_count = max(2, min(5, len(rows)))
        return 92.0 + (visible_count * 16.0)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.WIDTH, self.current_height())

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.node_moved.emit()
        return super().itemChange(change, value)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.current_height()
        rect = QRectF(0, 0, self.WIDTH, h)

        st = self.status.upper()
        if st in ("TOKEN_EXHAUSTED", "EXHAUSTED"):
            border_col = QColor("#a855f7")  # Bright Purple (Token Exhausted)
            hdr_bg = QColor("#3b0764")
        elif st in ("COMPLETED", "CACHED", "VERIFIED", "DONE"):
            border_col = QColor("#10b981")  # Bright Green
            hdr_bg = QColor("#052e16")
        elif st in ("RUNNING", "GENERATING", "VERIFYING", "ACTIVE"):
            border_col = QColor("#f97316")  # Bright Orange
            hdr_bg = QColor("#431407")
        else:
            border_col = QColor("#ef4444")  # Bright Red (Waiting / Sleeping)
            hdr_bg = QColor("#2a0808")

        painter.setBrush(QBrush(QColor("#141417")))
        painter.setPen(QPen(border_col, 2.5 if self.isSelected() else 1.9))
        painter.drawRoundedRect(rect, 7.0, 7.0)

        header_rect = QRectF(0, 0, self.WIDTH, 24.0)
        painter.setBrush(QBrush(hdr_bg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(header_rect, 7.0, 7.0)

        painter.setPen(QPen(border_col))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(
            header_rect.adjusted(8, 0, -54 if not self.is_master else -8, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.tree_role
        )

        if not self.is_master:
            is_idle = st in ("WAITING", "IDLE", "PENDING", "READY")
            self._btn_left_rect = QRectF(self.WIDTH - 46, 3, 20, 18)
            self._btn_right_rect = QRectF(self.WIDTH - 23, 3, 20, 18)

            for b_rect, enabled, sym in (
                (self._btn_left_rect, is_idle and self.can_move_left, "\u25c0"),
                (self._btn_right_rect, is_idle and self.can_move_right, "\u25b6")
            ):
                painter.setBrush(QBrush(QColor("#27272a") if enabled else QColor("#141417")))
                painter.setPen(QPen(QColor("#52525b") if enabled else QColor("#27272a"), 1.0))
                painter.drawRoundedRect(b_rect, 3.0, 3.0)
                painter.setPen(QPen(QColor("#f4f4f5") if enabled else QColor("#3f3f46")))
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.drawText(b_rect, Qt.AlignmentFlag.AlignCenter, sym)
        else:
            self._btn_left_rect = QRectF()
            self._btn_right_rect = QRectF()

        painter.setPen(QPen(QColor("#f4f4f5")))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title_str = f"{self.account_name} [{self.platform.capitalize()}]"
        painter.drawText(QRectF(8, 26, self.WIDTH - 16, 18), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title_str)

        painter.setPen(QPen(border_col))
        painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(8, 44, self.WIDTH - 85, 16), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"STATUS: {st}")

        if not self.is_master and st not in ("COMPLETED", "DONE"):
            self._btn_force_rect = QRectF(self.WIDTH - 78, 43, 70, 17)
            painter.setBrush(QBrush(QColor("#065f46")))
            painter.setPen(QPen(QColor("#10b981"), 1.0))
            painter.drawRoundedRect(self._btn_force_rect, 3.0, 3.0)
            painter.setPen(QPen(QColor("#a7f3d0")))
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.drawText(self._btn_force_rect, Qt.AlignmentFlag.AlignCenter, "\u2713 Harvest/Next")
        else:
            self._btn_force_rect = QRectF()

        if self.is_master:
            files_box = QRectF(8, 62, self.WIDTH - 16, 48)
            painter.setBrush(QBrush(QColor("#09090b")))
            painter.setPen(QPen(QColor("#27272a"), 1.0))
            painter.drawRoundedRect(files_box, 4.0, 4.0)
            painter.setPen(QPen(QColor("#c084fc")))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(files_box.adjusted(6, 4, -6, -4), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, "Role: Architect & Dependency Manager")
            painter.setPen(QPen(QColor("#a1a1aa")))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(files_box.adjusted(6, 20, -6, -4), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, "• Project Blueprint [MAP]\n• Interface Contracts")
            return

        rows = self._compute_file_rows()
        vis_rows = rows[:5]
        box_h = max(2, len(vis_rows)) * 16.0 + 18.0
        files_box = QRectF(8, 62, self.WIDTH - 16, box_h)
        painter.setBrush(QBrush(QColor("#09090b")))
        painter.setPen(QPen(QColor("#27272a"), 1.0))
        painter.drawRoundedRect(files_box, 4.0, 4.0)

        painter.setPen(QPen(QColor("#a1a1aa")))
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.drawText(QRectF(14, 64, self.WIDTH - 28, 14), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "TARGET OUTPUTS & HARVESTED FILES:")

        painter.setFont(QFont("Consolas", 8))
        if not vis_rows:
            painter.setPen(QPen(QColor("#71717a")))
            painter.drawText(QRectF(14, 80, self.WIDTH - 28, 16), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "• (Awaiting Master Blueprint)")
        else:
            for r_idx, (fname, is_harv) in enumerate(vis_rows):
                ry = 79.0 + r_idx * 15.5
                if is_harv:
                    painter.setPen(QPen(QColor("#10b981")))
                    prefix = "\u2713 Harvested: "
                else:
                    painter.setPen(QPen(QColor("#f4f4f5")))
                    prefix = "\u25cb Target: "
                disp = (prefix + fname)[:31]
                painter.drawText(QRectF(14, ry, self.WIDTH - 28, 15), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, disp)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            is_idle = self.status in ("WAITING", "IDLE", "PENDING", "READY")
            if not self.is_master and is_idle and self.can_move_left and self._btn_left_rect.contains(pos):
                self.move_worker_offset.emit(self, -1)
                event.accept()
                return
            if not self.is_master and is_idle and self.can_move_right and self._btn_right_rect.contains(pos):
                self.move_worker_offset.emit(self, 1)
                event.accept()
                return
            if not self.is_master and self._btn_force_rect.contains(pos):
                self.force_complete_requested.emit(self.account_id)
                event.accept()
                return
            self.node_selected_for_relay.emit(self)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.swap_account_requested.emit(self)
        event.accept()


class BinaryTreeRelayGraphWidget(QWidget):
    """
    100% Full-Width Canvas Graph with Inline Intermediate Gate Cards between Accounts!
    - Zero detached side panel.
    - Every Stage transition has its own InlineGateCardItem right between Account N and Account N+1.
    - Strict 3-color coding: Bright Green (Completed), Bright Orange (Running / Awaiting Approval), Bright Red (Waiting / Requested).
    """
    relay_gate_approved = pyqtSignal(int, dict)
    execution_mode_changed = pyqtSignal(str)
    strategy_topology_changed = pyqtSignal(str)
    force_stage_complete = pyqtSignal(str)
    session_selected = pyqtSignal(int)
    token_exhaust_requested = pyqtSignal()

    def __init__(
        self,
        injector,
        get_panes_fn: Callable,
        get_project_fn: Callable,
        get_vault_tab_fn: Callable,
        parent=None
    ):
        super().__init__(parent)
        self.injector = injector
        self.get_panes = get_panes_fn
        self.get_project = get_project_fn
        self.get_vault_tab = get_vault_tab_fn

        self.master_account: Optional[dict] = None
        self.worker_accounts: List[dict] = []
        self.assigned_files_map: Dict[str, List[str]] = {}
        self.stage_statuses_map: Dict[str, str] = {}
        self.gate_states_list: List[dict] = []

        self.node_items: Dict[str, TreeGraphNodeItem] = {}
        self.inline_gate_items: Dict[int, InlineGateCardItem] = {}
        self.ordered_node_ids: List[str] = []
        self.primary_edges: List[PrimaryTreeEdgeItem] = []
        self.request_edges: List[PerimeterRequestEdgeItem] = []
        self.failover_links: List[Tuple[str, str, List[str]]] = []
        self.failover_edges: List[FailoverBranchEdgeItem] = []
        self.harvest_cache: Dict[str, Dict[str, str]] = {}

        self._active_inspector_gate_idx: int = 0
        self._active_gate_entries_by_idx: Dict[int, List[dict]] = {}
        self._last_confirmed_topology: str = "binary_tree"

        self._setup_ui()

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._tick_animation)
        self.anim_timer.start(60)

        self.state_sync_timer = QTimer(self)
        self.state_sync_timer.timeout.connect(self.sync_live_pane_states)
        self.state_sync_timer.start(2200)

    def _setup_ui(self):
        self.setStyleSheet("""
            QWidget { background-color: #09090b; color: #f4f4f5; }
            QLabel { color: #f4f4f5; font-size: 11px; font-weight: bold; }
            QRadioButton { color: #f4f4f5; font-size: 11px; font-weight: bold; spacing: 5px; }
            QComboBox {
                background-color: #141417; color: #f4f4f5; border: 1px solid #3f3f46;
                border-radius: 3px; padding: 3px 8px; font-size: 11px; font-weight: bold;
            }
            QPushButton {
                background-color: #1f1f23; color: #f4f4f5; border: 1px solid #3f3f46;
                border-radius: 3px; padding: 4px 10px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background-color: #27272a; color: #ffffff; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Top Bar: Session, Strategy, Gate Mode, Approve Active Gate button, Fit Graph
        strat_bar = QFrame()
        strat_bar.setStyleSheet("background-color: #141417; border: 1px solid #27272a; border-radius: 4px;")
        sl = QHBoxLayout(strat_bar)
        sl.setContentsMargins(8, 4, 8, 4)
        sl.setSpacing(8)

        sl.addWidget(QLabel("Session:"))
        self.combo_sessions = QComboBox()
        self.combo_sessions.setFixedWidth(185)
        self.combo_sessions.currentIndexChanged.connect(self._on_session_combo_changed)
        sl.addWidget(self.combo_sessions)

        sl.addWidget(QLabel("| Strategy:"))
        self.grp_strategy = QButtonGroup(self)
        self.rb_binary_tree = QRadioButton("Binary Tree (Auto/Master)")
        self.rb_seq_dag = QRadioButton("Sequential DAG")
        self.rb_parallel = QRadioButton("Instant Parallel")
        self.rb_binary_tree.setChecked(True)

        for rb in (self.rb_binary_tree, self.rb_seq_dag, self.rb_parallel):
            self.grp_strategy.addButton(rb)
            sl.addWidget(rb)
            rb.clicked.connect(lambda checked, r=rb: self._confirm_and_apply_strategy_switch(r))

        sl.addWidget(QLabel("| Gate:"))
        self.grp_gate = QButtonGroup(self)
        self.rb_pause_approval = QRadioButton("Pause for Approval")
        self.rb_auto_relay = QRadioButton("Auto-Relay")
        self.rb_pause_approval.setChecked(True)

        for rb in (self.rb_pause_approval, self.rb_auto_relay):
            self.grp_gate.addButton(rb)
            sl.addWidget(rb)
            rb.toggled.connect(self._on_gate_mode_changed)

        sl.addStretch()

        self.lbl_progress = QLabel("System Ready")
        self.lbl_progress.setStyleSheet("color: #f97316; font-size: 11px; border: none;")
        sl.addWidget(self.lbl_progress)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(95)
        self.progress_bar.setFixedHeight(14)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background-color: #09090b; border: 1px solid #3f3f46; border-radius: 3px; text-align: center; font-size: 9px; color: #ffffff; }
            QProgressBar::chunk { background-color: #10b981; }
        """)
        sl.addWidget(self.progress_bar)

        btn_fire_top = QPushButton("\U0001f680 Approve Active Gate")
        btn_fire_top.setStyleSheet("background-color: #ea580c; color: #ffffff; border: 1px solid #f97316;")
        btn_fire_top.clicked.connect(self.fire_all_pending_gates)
        sl.addWidget(btn_fire_top)

        self.btn_token_exhaust_graph = QPushButton("\u26a1 If Token Exhaust")
        self.btn_token_exhaust_graph.setStyleSheet("background-color: #7e22ce; color: #ffffff; border: 1px solid #a855f7;")
        self.btn_token_exhaust_graph.clicked.connect(self.token_exhaust_requested.emit)
        sl.addWidget(self.btn_token_exhaust_graph)

        btn_rebalance = QPushButton("\U0001f332 Fit Graph")
        btn_rebalance.clicked.connect(self.center_and_fit_readable)
        sl.addWidget(btn_rebalance)

        layout.addWidget(strat_bar)

        # Full-Width Interactive Graph Canvas (No detached right-side panel!)
        self.scene = QGraphicsScene(self)
        self.scene.setBackgroundBrush(QBrush(QColor("#09090b")))

        self.view = ZoomableGraphView(self.scene, self)
        self.view.setStyleSheet("border: 1px solid #27272a; border-radius: 4px; background-color: #09090b;")
        layout.addWidget(self.view, stretch=1)

    # ==========================================================================
    # Signal Handlers & 3-Option Strategy Switch Guard
    # ==========================================================================
    def _on_gate_mode_changed(self, checked: bool):
        if not checked:
            return
        if self.rb_auto_relay.isChecked():
            self.fire_all_pending_gates()

    def _confirm_and_apply_strategy_switch(self, clicked_radio: QRadioButton):
        new_topo = self.get_strategy_topology()
        if new_topo == self._last_confirmed_topology:
            return

        has_active_work = any(
            n.status in ("RUNNING", "GENERATING", "COMPLETED", "CACHED", "VERIFIED")
            for n in self.node_items.values() if not n.is_master
        )

        if not has_active_work:
            self._last_confirmed_topology = new_topo
            self._apply_strategy_change()
            return

        msg = QMessageBox(self)
        msg.setWindowTitle("Switch Swarm Strategy Mid-Project?")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText("You are switching architecture methods while stages have already been charted or executed.")
        msg.setInformativeText(
            "Choose how to proceed:\n\n"
            "1. Wipe Sub-Claudes to /new & Re-Chart Master (Recommended): Resets worker chats to fresh links so you can click '1. Send Master Directive' for this exact method.\n"
            "2. Keep Harvested Files & Migrate From Current Stage: Keeps generated files & summaries in the inline gate boxes and switches the remaining stages.\n"
            "3. Switch On-the-Spot (Efficiency Warning): Switches layout immediately without re-prompting Master (may be less efficient)."
        )
        btn_opt1 = msg.addButton("1. Wipe Workers & Re-Chart (Recommended)", QMessageBox.ButtonRole.AcceptRole)
        btn_opt2 = msg.addButton("2. Keep Files & Migrate", QMessageBox.ButtonRole.ActionRole)
        btn_opt3 = msg.addButton("3. Force Switch On-the-Spot", QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == btn_opt1:
            self._last_confirmed_topology = new_topo
            panes = self.get_panes() or {}
            master_id = self.master_account.get("id") if isinstance(self.master_account, dict) else None
            for aid, pane in panes.items():
                if aid != master_id:
                    pane.navigate_to_url("https://claude.ai/new" if pane.platform == "claude" else "https://gemini.google.com/app")
            for aid, node in self.node_items.items():
                if not node.is_master:
                    node.status = "WAITING"
                    node.cached_files.clear()
            self._apply_strategy_change()
        elif clicked in (btn_opt2, btn_opt3):
            self._last_confirmed_topology = new_topo
            self._apply_strategy_change()
        else:
            # Revert radio button selection
            self.rb_binary_tree.blockSignals(True)
            self.rb_seq_dag.blockSignals(True)
            self.rb_parallel.blockSignals(True)
            self.rb_binary_tree.setChecked(self._last_confirmed_topology == "binary_tree")
            self.rb_seq_dag.setChecked(self._last_confirmed_topology == "dag")
            self.rb_parallel.setChecked(self._last_confirmed_topology == "parallel")
            self.rb_binary_tree.blockSignals(False)
            self.rb_seq_dag.blockSignals(False)
            self.rb_parallel.blockSignals(False)

    def recompute_true_progress(self, prefix_msg: str = ""):
        handed_off_ids = {src_id for src_id, _dst, _files in getattr(self, "failover_links", [])}
        active_workers = [
            w for w in self.worker_accounts
            if not (w.get("id") in handed_off_ids and self.stage_statuses_map.get(w.get("id"), "").upper() in ("TOKEN_EXHAUSTED", "EXHAUSTED"))
        ]
        total_w = max(1, len(active_workers))
        done_w = 0
        for w in active_workers:
            wid = w.get("id")
            if wid in self.node_items and self.node_items[wid].status in ("COMPLETED", "CACHED", "VERIFIED", "DONE"):
                done_w += 1
        pct = int((done_w / total_w) * 100)
        msg = prefix_msg or f"Pipeline Progress: {done_w}/{total_w} Active Stage(s) Completed ({pct}%)"
        self.set_progress(pct, msg)


    def _apply_strategy_change(self):
        topo = self.get_strategy_topology()
        self.rebuild_and_layout_graph()
        self.execution_mode_changed.emit(self.get_execution_mode())
        self.strategy_topology_changed.emit(topo)
        self.recompute_true_progress(f'Active Strategy: {topo.upper()}')

    # ==========================================================================
    # SwarmTrainChartWidget Compatibility API
    # ==========================================================================
    def set_session_list(self, session_titles: List[str], active_idx: int = -1):
        self.combo_sessions.blockSignals(True)
        self.combo_sessions.clear()
        for title in session_titles:
            clean_t = title.replace("\u00e2\u20ac\u201d", "-").replace("\u2014", "-")
            self.combo_sessions.addItem(clean_t)
        if 0 <= active_idx < len(session_titles):
            self.combo_sessions.setCurrentIndex(active_idx)
        self.combo_sessions.blockSignals(False)

    def _on_session_combo_changed(self, idx: int):
        if idx >= 0:
            self.session_selected.emit(idx)

    def get_execution_mode(self) -> str:
        return "parallel" if self.rb_parallel.isChecked() else "pipeline"

    def get_strategy_topology(self) -> str:
        if self.rb_seq_dag.isChecked():
            return "dag"
        if self.rb_parallel.isChecked():
            return "parallel"
        return "binary_tree"

    def is_pause_for_approval(self) -> bool:
        return self.rb_pause_approval.isChecked()

    def set_progress(self, value: int, message: str = ""):
        self.progress_bar.setValue(max(0, min(100, int(value))))
        if message:
            self.lbl_progress.setText(message)

    def set_stage_status(self, account_id: str, status: str):
        norm = status.upper()
        self.stage_statuses_map[account_id] = norm
        if account_id in self.node_items:
            node = self.node_items[account_id]
            node.status = norm
            node.update()
            self._update_primary_edge_flow_states()
            self.scene.update()

    # ==========================================================================
    # Inline Gate Card Population & Activation
    # ==========================================================================
    def _populate_inline_gate_card(self, gate_index: int, gate_card: InlineGateCardItem):
        """Populates an InlineGateCardItem with Master-Recommended vs Unchecked files and upstream summaries."""
        if gate_index + 1 >= len(self.worker_accounts):
            return
        down_id = self.worker_accounts[gate_index + 1].get("id")
        proj = self.get_project() or {}
        vault_files = proj.get("file_vault", {}).get("files", [])
        gate_entries = self._active_gate_entries_by_idx.get(gate_index, [])

        # Preserve any manual checkbox toggles the user already made on this gate card
        prev_sum_checked = {s["id"]: s["checked"] for s in gate_card.summary_items}
        prev_file_checked = {f["path"]: f["checked"] for f in gate_card.file_items}

        # 1. Populate Upstream Summary Checkboxes (All stages 0 .. gate_index)
        new_sums = []
        parent_sums = getattr(self.parent(), "harvested_stage_summaries", {})
        parent_deps = getattr(self.parent(), "worker_dependencies", {}).get(down_id, {})
        req_sum_ids = set(parent_deps.get("required_summaries", []))

        for s_idx in range(gate_index + 1):
            if s_idx >= len(self.worker_accounts):
                break
            w_acc = self.worker_accounts[s_idx]
            w_id = w_acc.get("id")
            w_name = w_acc.get("account_name", w_id)
            has_sum = bool(parent_sums.get(w_id)) or (w_id in self.node_items and bool(self.node_items[w_id].cached_files))
            is_rec = (w_id in req_sum_ids) or (not req_sum_ids and s_idx == gate_index)
            checked = prev_sum_checked.get(w_id, is_rec and has_sum)
            new_sums.append({
                "id": w_id,
                "label": f"S{s_idx + 1}: {w_name}",
                "checked": checked,
                "recommended": is_rec,
                "rect": QRectF()
            })
        gate_card.summary_items = new_sums

        # 2. Populate File Checkboxes (Master Recommended = Checked, Others = Unchecked!)
        rec_paths = {e.get("path") for e in gate_entries if e.get("recommended") and e.get("path")}
        req_paths = set()
        for vf in vault_files:
            if down_id in (vf.get("requested_by_ids") or []):
                req_paths.add(vf.get("path"))

        seen_paths = set()
        new_files = []

        # Include files from gate_entries first
        for e in gate_entries:
            p = e.get("path", "")
            fname = e.get("filename") or os.path.basename(p)
            if not p or not os.path.exists(p) or fname.lower() in TEMPLATE_DUMMY_FILENAMES or p in seen_paths:
                continue
            seen_paths.add(p)
            is_rec = bool(e.get("recommended"))
            is_req = (p in req_paths)
            checked = prev_file_checked.get(p, is_rec or is_req)
            new_files.append({
                "path": p,
                "filename": fname,
                "checked": checked,
                "recommended": is_rec,
                "requested": is_req,
                "rect": QRectF()
            })

        # Include any other harvested files (Unchecked unless recommended/requested)
        for fname, info in self.harvest_cache.items():
            if fname.lower() in TEMPLATE_DUMMY_FILENAMES:
                continue
            p = info.get("path", "")
            if p and os.path.exists(p) and p not in seen_paths:
                seen_paths.add(p)
                is_rec = (p in rec_paths)
                is_req = (p in req_paths)
                checked = prev_file_checked.get(p, is_rec or is_req)
                new_files.append({
                    "path": p,
                    "filename": fname,
                    "checked": checked,
                    "recommended": is_rec,
                    "requested": is_req,
                    "rect": QRectF()
                })

        # Include Vault files (Unchecked unless requested)
        for vf in vault_files:
            fname = vf.get("name", "")
            p = vf.get("path", "")
            if not fname or fname.lower() in TEMPLATE_DUMMY_FILENAMES or not p or not os.path.exists(p) or p in seen_paths:
                continue
            seen_paths.add(p)
            is_rec = (p in rec_paths)
            is_req = (p in req_paths)
            checked = prev_file_checked.get(p, is_rec or is_req)
            new_files.append({
                "path": p,
                "filename": fname,
                "checked": checked,
                "recommended": is_rec,
                "requested": is_req,
                "rect": QRectF()
            })

        new_files.sort(key=lambda x: (not x["recommended"], not x["requested"], x["filename"]))
        gate_card.file_items = new_files
        gate_card.prepareGeometryChange()
        gate_card.update()

    def activate_gate(self, gate_index: int, cumulative_entries: List[dict]):
        clean_entries = [
            e for e in (cumulative_entries or [])
            if os.path.basename(e.get("path", "")).lower() not in TEMPLATE_DUMMY_FILENAMES
        ]
        self._active_inspector_gate_idx = gate_index
        self._active_gate_entries_by_idx[gate_index] = clean_entries

        if gate_index + 1 < len(self.worker_accounts):
            up_id = self.worker_accounts[gate_index]["id"]
            down_name = self.worker_accounts[gate_index + 1]["account_name"]

            for entry in clean_entries:
                fpath = entry.get("path", "")
                fname = entry.get("filename") or os.path.basename(fpath)
                if fpath and os.path.exists(fpath) and fname.lower() not in TEMPLATE_DUMMY_FILENAMES:
                    self.harvest_cache[fname] = {
                        "path": fpath,
                        "producer_id": up_id,
                        "producer_name": entry.get("account_name", up_id)
                    }
                    if up_id in self.node_items:
                        self.node_items[up_id].cached_files[fname] = fpath
                        self.node_items[up_id].update()

            if gate_index in self.inline_gate_items:
                g_card = self.inline_gate_items[gate_index]
                g_card.status = "AWAITING_APPROVAL"
                self._populate_inline_gate_card(gate_index, g_card)

            self._update_all_edge_positions()
            self._update_primary_edge_flow_states()
            self.set_progress(
                int(((gate_index + 1) / max(1, len(self.worker_accounts))) * 100),
                f"Gate {gate_index + 1}\u2192{gate_index + 2} Ready (Orange) -> Review & Approve for {down_name}"
            )

            if self.rb_auto_relay.isChecked():
                self._on_inline_gate_approve_clicked(gate_index)

    def _on_inline_gate_attach_clicked(self, gate_index: int):
        files, _ = QFileDialog.getOpenFileNames(self, f"Attach Extra File(s) to Gate {gate_index + 1}\u2192{gate_index + 2}", "", "All Files (*.*)")
        if not files:
            return
        proj = self.get_project() or {}
        vault = proj.setdefault("file_vault", {"files": [], "folders": []})
        existing = {f.get("path") for f in vault.get("files", [])}
        down_id = self.worker_accounts[gate_index + 1].get("id") if (gate_index + 1 < len(self.worker_accounts)) else ""

        for fp in files:
            norm = os.path.abspath(fp)
            if os.path.isfile(norm) and norm not in existing:
                vault.setdefault("files", []).append({
                    "name": os.path.basename(norm),
                    "path": norm,
                    "folder": os.path.dirname(norm),
                    "used_history": [],
                    "requested_by_nodes": [],
                    "requested_by_ids": [down_id] if down_id else [],
                    "planned_usage": "Manual Gate Attachment"
                })
                existing.add(norm)

        if gate_index in self.inline_gate_items:
            g_card = self.inline_gate_items[gate_index]
            self._populate_inline_gate_card(gate_index, g_card)
            # Mark newly attached files as checked
            attached_set = {os.path.abspath(p) for p in files}
            for f_item in g_card.file_items:
                if f_item["path"] in attached_set:
                    f_item["checked"] = True
            g_card.update()

    def _on_inline_gate_approve_clicked(self, gate_index: int):
        if gate_index not in self.inline_gate_items:
            return
        g_card = self.inline_gate_items[gate_index]
        checked_files = [
            f["path"] for f in g_card.file_items
            if f.get("checked") and os.path.exists(f.get("path", ""))
        ]

        checked_summaries = []
        parent_sums = getattr(self.parent(), "harvested_stage_summaries", {})
        for s_item in g_card.summary_items:
            if s_item.get("checked"):
                p_id = s_item["id"]
                s_txt = parent_sums.get(p_id, "")
                if s_txt:
                    checked_summaries.append(f"=== SUMMARY FROM {s_item['label']} ===\n{s_txt}")

        combined_summary = "\n\n".join(checked_summaries)
        send_summary = bool(combined_summary) or any(s.get("checked") for s in g_card.summary_items)

        g_card.status = "RELAYED"
        g_card.update()

        if gate_index + 1 < len(self.worker_accounts):
            down_id = self.worker_accounts[gate_index + 1].get("id")
            if down_id in self.node_items:
                self.node_items[down_id].status = "RUNNING"
                self.node_items[down_id].update()

        self._update_primary_edge_flow_states()
        self.scene.update()

        self.relay_gate_approved.emit(gate_index, {
            "send_summary": send_summary,
            "custom_summary_text": combined_summary,
            "files": checked_files
        })

    def fire_all_pending_gates(self):
        fired_any = False
        for g_idx, g_card in sorted(self.inline_gate_items.items()):
            if g_card.status == "AWAITING_APPROVAL":
                self._on_inline_gate_approve_clicked(g_idx)
                fired_any = True
                break
        if not fired_any and self._active_inspector_gate_idx in self.inline_gate_items:
            self._on_inline_gate_approve_clicked(self._active_inspector_gate_idx)

    # ==========================================================================
    # Graph Construction & Layout Engine (With Inline Intermediate Gate Cards!)
    # ==========================================================================
    def set_master_and_workers(
        self,
        master_account: Optional[dict],
        worker_accounts: List[dict],
        assigned_files: Optional[Dict[str, List[str]]] = None,
        stage_statuses: Optional[Dict[str, str]] = None,
        gate_states: Optional[List[dict]] = None
    ):
        self.master_account = master_account
        self.worker_accounts = list(worker_accounts or [])
        if assigned_files is not None:
            self.assigned_files_map = {k: list(v) for k, v in assigned_files.items()}
        if stage_statuses is not None:
            self.stage_statuses_map = {k: str(v).upper() for k, v in stage_statuses.items()}
        if gate_states is not None:
            self.gate_states_list = list(gate_states)
        self.rebuild_and_layout_graph()

    def build_train_pipeline(
        self,
        worker_accounts: List[dict],
        assigned_files: Optional[Dict[str, List[str]]] = None,
        stage_statuses: Optional[Dict[str, str]] = None,
        gate_states: Optional[List[dict]] = None
    ):
        proj = self.get_project() or {}
        panes = self.get_panes() or {}
        master_id = proj.get("master_node_id")

        master_acc = self.master_account
        if master_id and master_id in panes:
            p = panes[master_id]
            master_acc = {"id": master_id, "account_name": p.account_name, "platform": p.platform}
        elif not master_acc and panes:
            first_id = next(iter(panes.keys()))
            p = panes[first_id]
            master_acc = {"id": first_id, "account_name": p.account_name, "platform": p.platform}

        self.set_master_and_workers(
            master_account=master_acc,
            worker_accounts=worker_accounts,
            assigned_files=assigned_files,
            stage_statuses=stage_statuses,
            gate_states=gate_states
        )

    def _compute_tree_role_label(self, idx: int, total: int) -> str:
        if idx == 0:
            return "L0: ROOT ARCHITECT (MASTER)"
        if self.rb_seq_dag.isChecked():
            return f"STAGE {idx} (DAG)"
        if self.rb_parallel.isChecked():
            return f"STAGE {idx} (PARALLEL)"
        if idx in (1, 2) and total > 3:
            side = "LEFT" if idx == 1 else "RIGHT"
            return f"L1: {side} BRANCH (STAGE {idx})"
        level = int(math.floor(math.log2(idx + 1)))
        return f"L{level}: LEAF STAGE {idx}"

    def rebuild_and_layout_graph(self):
        panes = self.get_panes() or {}
        proj = self.get_project() or {}

        saved_cached: Dict[str, Dict[str, str]] = {
            aid: dict(n.cached_files) for aid, n in self.node_items.items()
        }
        saved_gate_statuses: Dict[int, str] = {
            g_idx: g_card.status for g_idx, g_card in self.inline_gate_items.items()
        }

        master_id = (
            (self.master_account.get("id") if isinstance(self.master_account, dict) else None)
            or proj.get("master_node_id")
        )
        ordered_ids: List[str] = []
        account_lookup: Dict[str, dict] = {}

        if isinstance(self.master_account, dict) and self.master_account.get("id"):
            mid = self.master_account["id"]
            ordered_ids.append(mid)
            account_lookup[mid] = self.master_account
        elif master_id and master_id in panes:
            ordered_ids.append(master_id)
            account_lookup[master_id] = {
                "id": master_id,
                "account_name": panes[master_id].account_name,
                "platform": panes[master_id].platform
            }

        for w in self.worker_accounts:
            wid = w.get("id")
            if wid and wid not in ordered_ids:
                ordered_ids.append(wid)
                account_lookup[wid] = w

        for aid, pane in panes.items():
            if aid not in ordered_ids:
                ordered_ids.append(aid)
            if aid not in account_lookup:
                account_lookup[aid] = {
                    "id": aid,
                    "account_name": pane.account_name,
                    "platform": pane.platform
                }

        self.ordered_node_ids = ordered_ids
        self.scene.clear()
        self.node_items.clear()
        self.inline_gate_items.clear()
        self.primary_edges.clear()
        self.request_edges.clear()
        self.failover_edges.clear()

        total_nodes = len(ordered_ids)
        worker_count = max(0, total_nodes - 1)

        for idx, aid in enumerate(ordered_ids):
            acc_info = account_lookup.get(aid, {})
            acc_name = acc_info.get("account_name") or (panes[aid].account_name if aid in panes else aid)
            plat = acc_info.get("platform") or (panes[aid].platform if aid in panes else "claude")
            is_master_node = (idx == 0)

            role = self._compute_tree_role_label(idx, total_nodes)
            raw_stat = self.stage_statuses_map.get(aid, "WAITING").upper()
            if raw_stat in ("IDLE", "WAITING"):
                raw_stat = "WAITING"

            node_item = TreeGraphNodeItem(
                node_index=idx,
                account_id=aid,
                account_name=acc_name,
                platform=plat,
                tree_role=role,
                status=raw_stat,
                is_master=is_master_node
            )
            if not is_master_node:
                worker_pos = idx - 1
                node_item.can_move_left = (worker_pos > 0)
                node_item.can_move_right = (worker_pos < worker_count - 1)

            node_item.assigned_files = [
                f for f in self.assigned_files_map.get(aid, [])
                if os.path.basename(f.strip()).lower() not in TEMPLATE_DUMMY_FILENAMES
            ]
            node_item.cached_files = {
                k: v for k, v in saved_cached.get(aid, {}).items()
                if k.lower() not in TEMPLATE_DUMMY_FILENAMES
            }

            node_item.node_moved.connect(self._update_all_edge_positions)
            node_item.node_selected_for_relay.connect(self._on_node_clicked_for_relay)
            node_item.swap_account_requested.connect(self._on_swap_node_dialog)
            node_item.move_worker_offset.connect(self._on_move_worker_by_offset)
            node_item.force_complete_requested.connect(self.force_stage_complete.emit)

            self.scene.addItem(node_item)
            self.node_items[aid] = node_item

        # Create Inline Intermediate Gate Cards between sequential stages (in Binary Tree & Sequential DAG)
        if not self.rb_parallel.isChecked() and len(self.worker_accounts) > 1:
            for g_idx in range(len(self.worker_accounts) - 1):
                to_acc = self.worker_accounts[g_idx + 1]
                g_stat = saved_gate_statuses.get(g_idx, "LOCKED")
                if g_idx < len(self.gate_states_list):
                    st_raw = (self.gate_states_list[g_idx].get("state") or "").lower()
                    if st_raw == "awaiting_approval":
                        g_stat = "AWAITING_APPROVAL"
                    elif st_raw == "relayed":
                        g_stat = "RELAYED"

                gate_card = InlineGateCardItem(
                    gate_index=g_idx,
                    from_stage_num=g_idx + 1,
                    to_stage_num=g_idx + 2,
                    to_account_name=to_acc.get("account_name", f"Stage {g_idx + 2}"),
                    status=g_stat
                )
                gate_card.gate_moved.connect(self._update_all_edge_positions)
                gate_card.approve_clicked.connect(self._on_inline_gate_approve_clicked)
                gate_card.attach_file_clicked.connect(self._on_inline_gate_attach_clicked)
                self._populate_inline_gate_card(g_idx, gate_card)
                self.scene.addItem(gate_card)
                self.inline_gate_items[g_idx] = gate_card

        self._layout_nodes_by_current_strategy()

    def _layout_nodes_by_current_strategy(self):
        for edge in self.primary_edges:
            self.scene.removeItem(edge)
        self.primary_edges.clear()

        n = len(self.ordered_node_ids)
        if n == 0:
            return

        worker_count = max(0, n - 1)
        for idx, aid in enumerate(self.ordered_node_ids):
            node = self.node_items[aid]
            node.node_index = idx
            node.is_master = (idx == 0)
            if idx > 0:
                w_pos = idx - 1
                node.can_move_left = (w_pos > 0)
                node.can_move_right = (w_pos < worker_count - 1)

        if self.rb_seq_dag.isChecked():
            # SEQUENTIAL DAG TRAIN: Master -> Stage 1 -> [Gate 1->2] -> Stage 2 -> [Gate 2->3] -> Stage 3...
            x_cursor = 0.0
            master_node = self.node_items[self.ordered_node_ids[0]]
            master_node.tree_role = "L0: ROOT ARCHITECT (MASTER)"
            master_node.setPos(x_cursor, 25.0)
            master_node.update()
            x_cursor += 300.0

            for w_idx, wid in enumerate(self.ordered_node_ids[1:]):
                w_node = self.node_items[wid]
                w_node.tree_role = f"STAGE {w_idx + 1} (DAG)"
                w_node.setPos(x_cursor, 20.0)
                w_node.update()

                if w_idx == 0:
                    edge = PrimaryTreeEdgeItem(master_node, w_node)
                    self.scene.addItem(edge)
                    self.primary_edges.append(edge)

                x_cursor += 290.0

                if w_idx in self.inline_gate_items and (w_idx + 2) < n:
                    g_card = self.inline_gate_items[w_idx]
                    g_card.setVisible(True)
                    g_card.setPos(x_cursor, 10.0)
                    next_wid = self.ordered_node_ids[w_idx + 2]
                    next_node = self.node_items[next_wid]

                    e1 = PrimaryTreeEdgeItem(w_node, g_card)
                    e2 = PrimaryTreeEdgeItem(g_card, next_node)
                    self.scene.addItem(e1)
                    self.scene.addItem(e2)
                    self.primary_edges.extend([e1, e2])
                    x_cursor += 275.0

        elif self.rb_binary_tree.isChecked():
            # TRUE BINARY TREE TOPOLOGY WITH INLINE GATE BOXES BETWEEN PARENT & CHILD:
            # Row 0 (y=0):    L0 Master Architect
            # Row 1 (y=210):  L1 Left Branch (Stage 1)  --[Gate 1->2]-->  L1 Right Branch (Stage 2)
            # Row 2 (y=430):  Inline Gate Boxes [Gate 1->3], [Gate 2->4], [Gate 2->5]...
            # Row 3 (y=680):  L2 Leaf Workers (Stage 3, Stage 4, Stage 5...)
            master_id = self.ordered_node_ids[0]
            master_node = self.node_items[master_id]
            master_node.tree_role = "L0: ROOT ARCHITECT (MASTER)"
            master_node.setPos(0.0, 0.0)
            master_node.update()

            # Position L1 and L2+ nodes in a balanced symmetric Binary Tree
            for i in range(1, n):
                aid = self.ordered_node_ids[i]
                node = self.node_items[aid]
                node.tree_role = self._compute_tree_role_label(i, n)
                level = int(math.floor(math.log2(i + 1)))
                level_start = (1 << level) - 1
                pos_in_level = i - level_start
                nodes_in_level = min(1 << level, n - level_start)

                if level == 1:
                    # L1 Branch Leads (Stage 1 on Left, Stage 2 on Right, with room for Gate 1->2 in the center)
                    x_span = 680.0
                    total_w = max(0.0, (nodes_in_level - 1) * x_span)
                    x = -total_w / 2.0 + pos_in_level * x_span
                    y = 210.0
                else:
                    # L2+ Leaf Workers positioned below their respective L1 parent branch + intermediate Gate Box
                    x_span = 340.0
                    total_w = max(0.0, (nodes_in_level - 1) * x_span)
                    x = -total_w / 2.0 + pos_in_level * x_span
                    y = 210.0 + (level - 1) * 470.0

                node.setPos(x, y)
                node.update()

                if level == 1:
                    # Connect L0 Master -> L1 Branch Leads
                    e_m = PrimaryTreeEdgeItem(master_node, node)
                    self.scene.addItem(e_m)
                    self.primary_edges.append(e_m)

            # Position each Inline Gate Card directly in the tree hierarchy!
            for g_idx, g_card in self.inline_gate_items.items():
                target_worker_idx = g_idx + 1  # 0-based index in self.worker_accounts (Stage = target_worker_idx + 1)
                target_tree_idx = target_worker_idx + 1  # 1-based index in self.ordered_node_ids
                if target_tree_idx >= n:
                    g_card.setVisible(False)
                    continue

                g_card.setVisible(True)
                dst_node = self.node_items[self.ordered_node_ids[target_tree_idx]]

                if target_tree_idx == 2:
                    # Gate 1->2 sits horizontally between L1 Left (Stage 1) and L1 Right (Stage 2)
                    src_node = self.node_items[self.ordered_node_ids[1]]
                    g_card.from_stage_num = 1
                    g_card.to_stage_num = 2
                    mid_x = (src_node.pos().x() + dst_node.pos().x()) / 2.0
                    mid_y = src_node.pos().y() - 5.0
                    g_card.setPos(mid_x + 8.0, mid_y)
                else:
                    # For L2+ nodes (Stage 3, Stage 4, Stage 5...), connect from their Binary Tree Parent (parent_tree_idx = target_tree_idx // 2)
                    parent_tree_idx = max(1, target_tree_idx // 2)
                    src_node = self.node_items[self.ordered_node_ids[parent_tree_idx]]
                    g_card.from_stage_num = parent_tree_idx
                    g_card.to_stage_num = target_tree_idx
                    # Place the Inline Gate Box vertically between the L1 Parent and the L2 Child!
                    gx = dst_node.pos().x() + 8.0
                    gy = (src_node.pos().y() + dst_node.pos().y()) / 2.0 - 20.0
                    g_card.setPos(gx, gy)

                g_card.update()
                e1 = PrimaryTreeEdgeItem(src_node, g_card)
                e2 = PrimaryTreeEdgeItem(g_card, dst_node)
                self.scene.addItem(e1)
                self.scene.addItem(e2)
                self.primary_edges.extend([e1, e2])
        else:
            # INSTANT PARALLEL STAR
            for g_card in self.inline_gate_items.values():
                g_card.setVisible(False)
            master_id = self.ordered_node_ids[0]
            master_node = self.node_items[master_id]
            master_node.tree_role = "L0: ROOT ARCHITECT (MASTER)"
            master_node.setPos(0.0, 0.0)
            master_node.update()

            workers = self.ordered_node_ids[1:]
            cols = max(1, min(4, len(workers)))
            for idx_w, aid in enumerate(workers):
                node = self.node_items[aid]
                node.tree_role = f"STAGE {idx_w + 1} (PARALLEL)"
                row = idx_w // cols
                col = idx_w % cols
                row_count = min(cols, len(workers) - row * cols)
                total_w = max(0.0, (row_count - 1) * 315.0)
                x = -total_w / 2.0 + col * 315.0
                y = 210.0 + row * 230.0
                node.setPos(x, y)
                node.update()

                edge = PrimaryTreeEdgeItem(master_node, node)
                self.scene.addItem(edge)
                self.primary_edges.append(edge)

        for f_edge in self.failover_edges:
            self.scene.removeItem(f_edge)
        self.failover_edges.clear()
        for src_id, dst_id, rem_files in self.failover_links:
            if src_id in self.node_items and dst_id in self.node_items:
                fe = FailoverBranchEdgeItem(self.node_items[src_id], self.node_items[dst_id], rem_files)
                self.scene.addItem(fe)
                self.failover_edges.append(fe)

        self._update_all_edge_positions()
        self._update_primary_edge_flow_states()
        self.center_and_fit_readable()

    def center_and_fit_readable(self):
        rect = self.scene.itemsBoundingRect().adjusted(-50, -50, 50, 50)
        if rect.isEmpty():
            return
        self.view.setSceneRect(rect)
        self.view.resetTransform()
        vp = self.view.viewport().rect()
        if vp.width() > 60 and vp.height() > 60 and rect.width() > 0 and rect.height() > 0:
            sx = vp.width() / rect.width()
            sy = vp.height() / rect.height()
            scale = max(0.32, min(sx, sy, 1.02))
            self.view.scale(scale, scale)
        self.view.centerOn(rect.center())

    def _update_all_edge_positions(self):
        for edge in self.primary_edges:
            edge.update_position()
        for req in self.request_edges:
            req.update_position()
        for fe in self.failover_edges:
            fe.update_position()
        self.scene.update()

    def _update_primary_edge_flow_states(self):
        for edge in self.primary_edges:
            s_stat = getattr(edge.source_node, "status", "WAITING").upper()
            t_stat = getattr(edge.target_node, "status", "WAITING").upper()
            s_is_master = getattr(edge.source_node, "is_master", False)
            if s_is_master:
                edge.is_active_flow = s_stat in ("GENERATING", "RUNNING", "ACTIVE")
                edge.is_completed = s_stat in ("COMPLETED", "CACHED", "VERIFIED", "DONE") and t_stat != "WAITING"
            else:
                edge.is_active_flow = (
                    t_stat in ("GENERATING", "RUNNING", "VERIFYING", "ACTIVE", "AWAITING_APPROVAL")
                    and s_stat in ("COMPLETED", "CACHED", "VERIFIED", "DONE", "RELAYED", "AWAITING_APPROVAL")
                )
                edge.is_completed = t_stat in ("COMPLETED", "CACHED", "VERIFIED", "DONE", "RELAYED")

    def _on_move_worker_by_offset(self, node_item: TreeGraphNodeItem, offset: int):
        if node_item.account_id not in self.ordered_node_ids:
            return
        idx_a = self.ordered_node_ids.index(node_item.account_id)
        idx_b = idx_a + offset
        if idx_a <= 0 or idx_b <= 0 or idx_b >= len(self.ordered_node_ids):
            return
        other_id = self.ordered_node_ids[idx_b]
        other_node = self.node_items.get(other_id)
        if other_node and other_node.status in ("RUNNING", "GENERATING", "VERIFYING"):
            QMessageBox.warning(self, "Stage Busy", f"Cannot swap with {other_node.account_name} while it is running.")
            return

        self.ordered_node_ids[idx_a], self.ordered_node_ids[idx_b] = self.ordered_node_ids[idx_b], self.ordered_node_ids[idx_a]
        if len(self.worker_accounts) >= max(idx_a, idx_b):
            w_a, w_b = idx_a - 1, idx_b - 1
            if 0 <= w_a < len(self.worker_accounts) and 0 <= w_b < len(self.worker_accounts):
                self.worker_accounts[w_a], self.worker_accounts[w_b] = self.worker_accounts[w_b], self.worker_accounts[w_a]

        self.rebuild_and_layout_graph()

    def _on_swap_node_dialog(self, clicked_node: TreeGraphNodeItem):
        if clicked_node.is_master:
            QMessageBox.information(
                self,
                "Master Architect Node",
                "To change L0: ROOT ARCHITECT (MASTER), select a different account in the top 'Master Architect:' dropdown!"
            )
            return
        if clicked_node.status in ("RUNNING", "GENERATING", "VERIFYING"):
            QMessageBox.warning(self, "Node Busy", f"Cannot swap {clicked_node.account_name} while it is actively working.")
            return

        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #18181b; color: #f4f4f5; border: 1px solid #3f3f46; } QMenu::item:selected { background-color: #ea580c; }")
        swap_actions = {}
        for aid in self.ordered_node_ids[1:]:
            if aid == clicked_node.account_id:
                continue
            other = self.node_items.get(aid)
            if other and other.status not in ("RUNNING", "GENERATING", "VERIFYING"):
                act = menu.addAction(f"Swap Stage Position with: {other.account_name} ({other.tree_role})")
                swap_actions[act] = aid

        if not swap_actions:
            return
        chosen = menu.exec(self.cursor().pos())
        if chosen in swap_actions:
            other_id = swap_actions[chosen]
            idx_a = self.ordered_node_ids.index(clicked_node.account_id)
            idx_b = self.ordered_node_ids.index(other_id)
            self.ordered_node_ids[idx_a], self.ordered_node_ids[idx_b] = self.ordered_node_ids[idx_b], self.ordered_node_ids[idx_a]
            self.rebuild_and_layout_graph()

    def _on_node_clicked_for_relay(self, node_item: TreeGraphNodeItem):
        if node_item.is_master:
            return
        # Center view on the inline gate card feeding into or out of this node
        for g_idx, w in enumerate(self.worker_accounts):
            if w.get("id") == node_item.account_id:
                target_g = max(0, g_idx - 1)
                if target_g in self.inline_gate_items:
                    self._active_inspector_gate_idx = target_g
                break

    def refresh_dropdowns(self, highlight_target_id: Optional[str] = None):
        for g_idx, g_card in self.inline_gate_items.items():
            self._populate_inline_gate_card(g_idx, g_card)

    def sync_live_pane_states(self):
        panes = self.get_panes() or {}
        if not panes or not self.node_items:
            return

        js_state_probe = """
        (function() {
            const btns = Array.from(document.querySelectorAll('button, [role="button"]'));
            const isStreaming = btns.some(b => {
                const r = b.getBoundingClientRect();
                if (r.width === 0 || r.height === 0) return false;
                const aria = (b.getAttribute('aria-label') || b.getAttribute('mattooltip') || b.innerText || "").toLowerCase();
                return aria.includes("stop response") || aria.includes("stop generating") || aria === "stop";
            });
            return { isStreaming: isStreaming };
        })();
        """

        for aid, pane in panes.items():
            if aid not in self.node_items:
                continue

            def _make_cb(acc_id=aid):
                def _on_res(res):
                    if not isinstance(res, dict) or acc_id not in self.node_items:
                        return
                    node = self.node_items[acc_id]
                    is_streaming = bool(res.get("isStreaming"))
                    prev = node.status
                    now = time.time()

                    if is_streaming:
                        node._saw_streaming = True
                        node._busy_since = now
                        if prev != "VERIFYING":
                            node.status = "RUNNING"
                    elif getattr(node, "_saw_streaming", False) and prev in ("GENERATING", "VERIFYING", "RUNNING"):
                        node.status = "COMPLETED"
                        node._saw_streaming = False
                        node._busy_since = 0.0
                        if not node.is_master and node.cached_files:
                            self.force_stage_complete.emit(acc_id)
                    elif prev in ("GENERATING", "VERIFYING", "RUNNING") and getattr(node, "_busy_since", 0.0) > 0.0 and (now - node._busy_since) > 60.0:
                        node.status = "COMPLETED" if node.cached_files else "WAITING"
                        node._saw_streaming = False
                        node._busy_since = 0.0

                    if node.status != prev:
                        node.update()
                        self._update_primary_edge_flow_states()
                        self.scene.update()
                return _on_res

            pane.get_page().runJavaScript(js_state_probe, _make_cb())

    def _tick_animation(self):
        any_active = False
        for edge in self.primary_edges:
            if edge.is_active_flow:
                edge.pulse_t = (edge.pulse_t + 0.035) % 1.0
                any_active = True
        if any_active:
            self.scene.update()

    def on_file_harvested_live(self, producer_id: str, file_name: str, disk_path: str):
        clean_name = os.path.basename(file_name.strip())
        if not clean_name or clean_name.lower() in TEMPLATE_DUMMY_FILENAMES:
            return

        panes = self.get_panes() or {}
        producer_name = panes[producer_id].account_name if producer_id in panes else producer_id
        norm_path = os.path.abspath(disk_path)

        self.harvest_cache[clean_name] = {
            "path": norm_path,
            "producer_id": producer_id,
            "producer_name": producer_name
        }

        if producer_id in self.node_items:
            node = self.node_items[producer_id]
            node.prepareGeometryChange()
            node.cached_files[clean_name] = norm_path
            if node.status not in ("GENERATING", "VERIFYING", "RUNNING"):
                node.status = "COMPLETED"
            node.update()
            self._update_all_edge_positions()
            self._update_primary_edge_flow_states()

        # If any PerimeterRequestEdgeItem was waiting for this file, fulfill it and turn it Bright Green!
        for req_edge in self.request_edges:
            if req_edge.file_name.lower() == clean_name.lower() and req_edge.status != "COMPLETED":
                req_edge.file_path = norm_path
                self._fulfill_request_edge(req_edge)

        vault_tab = self.get_vault_tab()
        if vault_tab is not None and hasattr(vault_tab, "register_harvested_file"):
            vault_tab.register_harvested_file(clean_name, norm_path, producer_id, producer_name)

        self.refresh_dropdowns()

    def on_explicit_file_request(self, requester_id: str, requester_name: str, file_name: str, file_path: str):
        clean_name = os.path.basename(file_name.strip())
        if not clean_name or clean_name.lower() in TEMPLATE_DUMMY_FILENAMES:
            return
        source_id = None
        if clean_name in self.harvest_cache:
            source_id = self.harvest_cache[clean_name].get("producer_id")
            file_path = self.harvest_cache[clean_name].get("path", file_path)

        if not source_id:
            for aid, f_list in self.assigned_files_map.items():
                if any(os.path.basename(f).lower() == clean_name.lower() for f in f_list):
                    source_id = aid
                    break

        if not source_id and len(self.ordered_node_ids) > 1:
            source_id = self.ordered_node_ids[1]

        if source_id and requester_id and source_id != requester_id and requester_id in self.node_items and source_id in self.node_items:
            req_edge = PerimeterRequestEdgeItem(
                source_node=self.node_items[requester_id],
                target_node=self.node_items[source_id],
                file_name=clean_name,
                file_path=file_path,
                status="REQUESTED",
                corridor_index=len(self.request_edges)
            )
            req_edge.request_clicked.connect(self._fulfill_request_edge)
            self.scene.addItem(req_edge)
            self.request_edges.append(req_edge)
            if file_path and os.path.exists(file_path):
                self._fulfill_request_edge(req_edge)

    def _fulfill_request_edge(self, req_edge: PerimeterRequestEdgeItem):
        panes = self.get_panes() or {}
        requester_id = req_edge.source_node.account_id
        if requester_id not in panes or not req_edge.file_path or not os.path.exists(req_edge.file_path):
            return
        req_pane = panes[requester_id]
        prompt = f"[REQUESTED FILE RELAY] Attached is `{req_edge.file_name}` requested by your stage."

        def _on_done(_res):
            req_edge.status = "COMPLETED"
            req_edge.update()
            self.scene.update()

        self.injector.send_multi_files(
            page=req_pane.get_page(),
            platform=req_pane.platform,
            prompt_text=prompt,
            file_paths=[req_edge.file_path],
            view=req_pane.web_view,
            callback=_on_done
        )
    def register_failover_branch(self, exhausted_id: str, new_accounts: List[dict], remaining_files: List[str]):
        self.set_stage_status(exhausted_id, "TOKEN_EXHAUSTED")
        existing_ids = {w.get("id") for w in self.worker_accounts}
        for acc in (new_accounts or []):
            nid = acc.get("id")
            if not nid:
                continue
            if nid not in existing_ids:
                self.worker_accounts.append(acc)
                existing_ids.add(nid)
            self.stage_statuses_map[nid] = "WAITING"
            if remaining_files:
                self.assigned_files_map[nid] = list(remaining_files)
            if not any(s == exhausted_id and d == nid for s, d, _ in self.failover_links):
                self.failover_links.append((exhausted_id, nid, list(remaining_files or [])))
        self.rebuild_and_layout_graph()
        self.recompute_true_progress(f"Failover Branch Active ({len(new_accounts)} new node(s) added)")
