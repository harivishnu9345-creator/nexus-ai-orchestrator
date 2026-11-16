import os
import math
from typing import Dict, List, Optional
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QEvent
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QPolygonF, QNativeGestureEvent
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QGraphicsView, QGraphicsScene,
    QGraphicsObject, QGraphicsPathItem, QGraphicsItem, QPinchGesture, QRadioButton, QButtonGroup
)


class ZoomableMindMapView(QGraphicsView):
    """QGraphicsView with mouse wheel and touchpad pinch zoom for the Task Assignment Mind-Map."""

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

    def _apply_zoom(self, factor: float):
        factor = max(0.85, min(1.18, factor))
        curr = self.transform().m11()
        if (curr <= 0.30 and factor < 1.0) or (curr >= 3.2 and factor > 1.0):
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


class MindMapEdgeItem(QGraphicsPathItem):
    """Thick primary connection curve between parent and child nodes in the Mind-Map."""

    def __init__(self, source_node: "MindMapNodeItem", target_node: "MindMapNodeItem", is_sub_edge: bool = False):
        super().__init__()
        self.source_node = source_node
        self.target_node = target_node
        self.is_sub_edge = is_sub_edge
        self.setPen(QPen(Qt.GlobalColor.transparent, 10.0))
        self.setZValue(1 if not is_sub_edge else 2)
        self.update_position()

    def boundingRect(self) -> QRectF:
        return super().boundingRect().adjusted(-12, -12, 12, 12)

    def update_position(self):
        if not self.source_node or not self.target_node:
            return
        self.prepareGeometryChange()
        s_rect = self.source_node.sceneBoundingRect()
        t_rect = self.target_node.sceneBoundingRect()

        # Left-to-Right tree flow (or Top-to-Bottom if vertically stacked)
        if abs(t_rect.left() - s_rect.right()) >= 35:
            start = QPointF(s_rect.right(), s_rect.center().y())
            end = QPointF(t_rect.left(), t_rect.center().y())
            dx = max(45.0, abs(end.x() - start.x()) * 0.5)
            c1 = QPointF(start.x() + dx, start.y())
            c2 = QPointF(end.x() - dx, end.y())
        else:
            start = QPointF(s_rect.center().x(), s_rect.bottom())
            end = QPointF(t_rect.center().x(), t_rect.top())
            dy = max(40.0, abs(end.y() - start.y()) * 0.5)
            c1 = QPointF(start.x(), start.y() + dy)
            c2 = QPointF(end.x(), end.y() - dy)

        path = QPainterPath(start)
        path.cubicTo(c1, c2, end)
        self.setPath(path)

    def paint(self, painter: QPainter, option, widget=None):
        path = self.path()
        if path.isEmpty():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        t_stat = (self.target_node.status or "idle").lower()
        if t_stat in ("done", "completed", "cached", "verified"):
            col = QColor("#10b981")
        elif t_stat in ("active", "running", "generating"):
            col = QColor("#f97316")
        else:
            col = QColor("#64748b")

        if self.is_sub_edge:
            pen = QPen(QColor("#38bdf8"), 1.6, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawPath(path)
            return

        glow = QPen(QColor(col.red(), col.green(), col.blue(), 45), 6.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(glow)
        painter.drawPath(path)

        main_pen = QPen(col, 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(main_pen)
        painter.drawPath(path)

        if path.length() > 20:
            end_pt = path.pointAtPercent(1.0)
            prev_pt = path.pointAtPercent(max(0.0, 1.0 - (12.0 / path.length())))
            angle = math.atan2(end_pt.y() - prev_pt.y(), end_pt.x() - prev_pt.x())
            arrow_size = 8.0
            p_a = QPointF(
                end_pt.x() - arrow_size * math.cos(angle - math.pi / 6),
                end_pt.y() - arrow_size * math.sin(angle - math.pi / 6)
            )
            p_b = QPointF(
                end_pt.x() - arrow_size * math.cos(angle + math.pi / 6),
                end_pt.y() - arrow_size * math.sin(angle + math.pi / 6)
            )
            painter.setBrush(QBrush(col))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(QPolygonF([end_pt, p_a, p_b]))


class MindMapNodeItem(QGraphicsObject):
    """Draggable Mind-Map Card showing Role, Account Name, Status, and Assigned File pills."""
    node_moved = pyqtSignal()

    WIDTH = 240.0

    def __init__(
        self,
        account_id: str,
        title: str,
        role_subtitle: str,
        files: List[str],
        status: str = "idle",
        is_master: bool = False
    ):
        super().__init__()
        self.account_id = account_id
        self.title = title
        self.role_subtitle = role_subtitle
        self.files = list(files or [])
        self.status = (status or "idle").lower()
        self.is_master = is_master

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setZValue(3)

    def current_height(self) -> float:
        rows = max(2, min(6, len(self.files)))
        return 64.0 + rows * 21.0 + 10.0

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

        st = self.status
        if st in ("done", "completed", "cached", "verified"):
            border_col = QColor("#10b981")
            badge_txt = "DONE"
        elif st in ("active", "running", "generating"):
            border_col = QColor("#f97316")
            badge_txt = "ACTIVE"
        elif self.is_master:
            border_col = QColor("#a855f7")
            badge_txt = "MASTER"
        else:
            border_col = QColor("#52525b")
            badge_txt = "IDLE"

        painter.setBrush(QBrush(QColor("#141417")))
        painter.setPen(QPen(border_col, 2.2 if self.isSelected() else 1.6))
        painter.drawRoundedRect(rect, 7.0, 7.0)

        # Title
        painter.setPen(QPen(QColor("#ffffff")))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(10, 8, self.WIDTH - 20, 18), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.title[:28])

        # Role Subtitle + Status
        painter.setPen(QPen(QColor("#a1a1aa")))
        painter.setFont(QFont("Segoe UI", 8))
        sub_str = f"{self.role_subtitle} [{badge_txt}]"
        painter.drawText(QRectF(10, 27, self.WIDTH - 20, 16), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, sub_str[:34])

        # Assigned File Pills
        display_files = self.files[:6] if self.files else ["(Awaiting Blueprint)"]
        painter.setFont(QFont("Consolas", 8))
        for idx, fname in enumerate(display_files):
            py = 48.0 + idx * 20.0
            pill_r = QRectF(10, py, self.WIDTH - 20, 17.0)
            painter.setBrush(QBrush(QColor("#09090b")))
            painter.setPen(QPen(QColor("#27272a"), 1.0))
            painter.drawRoundedRect(pill_r, 3.0, 3.0)

            txt_col = QColor("#10b981") if st in ("done", "completed") else QColor("#e4e4e7")
            painter.setPen(QPen(txt_col))
            painter.drawText(pill_r.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, fname[:28])


class SwarmMindMapWidget(QWidget):
    """
    Task Assignment Mind-Map supporting Binary Tree (L0 -> L1 -> L2),
    Sequential DAG, and Parallel Star topologies.
    """
    session_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.topology_mode = "binary_tree"  # "binary_tree", "dag", "parallel"
        self.master_acc: dict = {}
        self.worker_accs: List[dict] = []
        self.assigned_files: Dict[str, List[str]] = {}
        self.node_statuses: Dict[str, str] = {}

        self.node_items: Dict[str, MindMapNodeItem] = {}
        self.edges: List[MindMapEdgeItem] = []

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #141417; border: 1px solid #27272a; border-radius: 4px;")
        tl = QHBoxLayout(top_bar)
        tl.setContentsMargins(8, 4, 8, 4)
        tl.setSpacing(8)

        tl.addWidget(QLabel("Swarm Architecture Mind-Map | Session History:"))
        self.combo_sessions = QComboBox()
        self.combo_sessions.setMinimumWidth(240)
        self.combo_sessions.currentIndexChanged.connect(self._on_session_changed)
        tl.addWidget(self.combo_sessions)

        tl.addWidget(QLabel("| Layout:"))
        self.grp_topo = QButtonGroup(self)
        self.rb_btree = QRadioButton("Binary Tree (L0->L1->L2)")
        self.rb_dag = QRadioButton("Sequential DAG")
        self.rb_star = QRadioButton("Parallel Star")
        self.rb_btree.setChecked(True)
        for rb, mode_key in ((self.rb_btree, "binary_tree"), (self.rb_dag, "dag"), (self.rb_star, "parallel")):
            self.grp_topo.addButton(rb)
            tl.addWidget(rb)
            rb.toggled.connect(lambda checked, m=mode_key: self.set_topology_mode(m) if checked else None)

        tl.addStretch()

        btn_z_out = QPushButton("- Zoom Out")
        btn_z_out.setFixedWidth(85)
        btn_z_out.clicked.connect(lambda: self.view._apply_zoom(1.0 / 1.15))
        tl.addWidget(btn_z_out)

        btn_z_100 = QPushButton("100% Reset")
        btn_z_100.setFixedWidth(85)
        btn_z_100.clicked.connect(self.center_and_fit)
        tl.addWidget(btn_z_100)

        btn_z_in = QPushButton("+ Zoom In")
        btn_z_in.setFixedWidth(85)
        btn_z_in.clicked.connect(lambda: self.view._apply_zoom(1.15))
        tl.addWidget(btn_z_in)

        btn_fit = QPushButton("Center / Fit Graph")
        btn_fit.clicked.connect(self.center_and_fit)
        tl.addWidget(btn_fit)

        layout.addWidget(top_bar)

        self.scene = QGraphicsScene(self)
        self.scene.setBackgroundBrush(QBrush(QColor("#09090b")))

        self.view = ZoomableMindMapView(self.scene, self)
        self.view.setStyleSheet("border: 1px solid #27272a; border-radius: 4px; background-color: #09090b;")
        layout.addWidget(self.view, stretch=1)

    def set_topology_mode(self, mode: str):
        norm = (mode or "binary_tree").lower()
        if "dag" in norm or "seq" in norm:
            self.topology_mode = "dag"
            self.rb_dag.blockSignals(True)
            self.rb_dag.setChecked(True)
            self.rb_dag.blockSignals(False)
        elif "parallel" in norm or "star" in norm:
            self.topology_mode = "parallel"
            self.rb_star.blockSignals(True)
            self.rb_star.setChecked(True)
            self.rb_star.blockSignals(False)
        else:
            self.topology_mode = "binary_tree"
            self.rb_btree.blockSignals(True)
            self.rb_btree.setChecked(True)
            self.rb_btree.blockSignals(False)
        self._rebuild_scene()

    def set_session_list(self, labels: List[str], current_idx: int = -1):
        self.combo_sessions.blockSignals(True)
        self.combo_sessions.clear()
        for lbl in labels:
            clean = lbl.replace("\u00e2\u20ac\u201d", "-").replace("\u2014", "-")
            self.combo_sessions.addItem(clean)
        if 0 <= current_idx < len(labels):
            self.combo_sessions.setCurrentIndex(current_idx)
        self.combo_sessions.blockSignals(False)

    def _on_session_changed(self, idx: int):
        if idx >= 0:
            self.session_selected.emit(idx)

    def build_mind_map(
        self,
        master_acc: dict,
        worker_accounts: List[dict],
        assigned_files: Optional[Dict[str, List[str]]] = None,
        node_statuses: Optional[Dict[str, str]] = None
    ):
        self.master_acc = dict(master_acc or {})
        self.worker_accs = list(worker_accounts or [])
        if assigned_files is not None:
            self.assigned_files = {k: list(v) for k, v in assigned_files.items()}
        if node_statuses is not None:
            self.node_statuses = {k: str(v) for k, v in node_statuses.items()}
        self._rebuild_scene()

    def update_node_status(self, account_id: str, status: str):
        self.node_statuses[account_id] = status
        if account_id in self.node_items:
            self.node_items[account_id].status = status.lower()
            self.node_items[account_id].update()
            self.scene.update()

    def _rebuild_scene(self):
        self.scene.clear()
        self.node_items.clear()
        self.edges.clear()

        if not self.master_acc:
            return

        # All nodes ordered with Master at index 0, followed by workers
        all_accs = [self.master_acc] + [w for w in self.worker_accs if w.get("id") != self.master_acc.get("id")]
        total = len(all_accs)

        for idx, acc in enumerate(all_accs):
            aid = acc.get("id", f"node_{idx}")
            name = acc.get("account_name", aid)
            is_m = (idx == 0)

            if is_m:
                title = f"MASTER: {name}"
                role = "L0: Root Architect & Map"
                files = ["Project Blueprint [MAP]", "Interface Contracts"]
            else:
                if self.topology_mode == "binary_tree":
                    level = int(math.floor(math.log2(idx + 1)))
                    if idx in (1, 2) and total > 3:
                        side = "Left" if idx == 1 else "Right"
                        title = f"L1 {side.upper()} BRANCH: {name}"
                        role = f"Role: L1 {side} Lead (Stage {idx})"
                    else:
                        title = f"L{level} LEAF WORKER: {name}"
                        role = f"Role: L{level} Leaf Stage {idx}"
                elif self.topology_mode == "dag":
                    title = f"DAG STAGE {idx}: {name}"
                    role = f"Role: Sequential Stage {idx}"
                else:
                    title = f"WORKER: {name}"
                    role = f"Role: Subordinate Stage {idx}"

                files = self.assigned_files.get(aid) or ["(Awaiting Master Blueprint)"]

            stat = self.node_statuses.get(aid, "idle")
            item = MindMapNodeItem(
                account_id=aid,
                title=title,
                role_subtitle=role,
                files=files,
                status=stat,
                is_master=is_m
            )
            item.node_moved.connect(self._update_edges)
            self.scene.addItem(item)
            self.node_items[aid] = item

        ordered_ids = [a.get("id", f"node_{i}") for i, a in enumerate(all_accs)]

        # Position according to active topology_mode
        if self.topology_mode == "binary_tree":
            # Left-to-Right Multi-Column Binary Tree (L0 Col 0 -> L1 Col 1 -> L2 Col 2)
            col_x_spacing = 320.0
            base_y_spacing = 165.0
            for i, aid in enumerate(ordered_ids):
                node = self.node_items[aid]
                level = int(math.floor(math.log2(i + 1)))
                level_start = (1 << level) - 1
                pos_in_level = i - level_start
                nodes_in_level = min(1 << level, total - level_start)

                # Spread L1 nodes wider vertically so their L2 children align cleanly beside them
                y_gap = base_y_spacing * (1.8 if (level == 1 and total > 3) else 1.0)
                total_h = max(0.0, (nodes_in_level - 1) * y_gap)
                x = level * col_x_spacing
                y = -total_h / 2.0 + pos_in_level * y_gap
                node.setPos(x, y)

                if i > 0:
                    parent_idx = (i - 1) // 2
                    parent_id = ordered_ids[parent_idx]
                    edge = MindMapEdgeItem(self.node_items[parent_id], node)
                    self.scene.addItem(edge)
                    self.edges.append(edge)

        elif self.topology_mode == "dag":
            for i, aid in enumerate(ordered_ids):
                node = self.node_items[aid]
                node.setPos(i * 305.0, 0.0)
                if i > 0:
                    prev_id = ordered_ids[i - 1]
                    edge = MindMapEdgeItem(self.node_items[prev_id], node)
                    self.scene.addItem(edge)
                    self.edges.append(edge)

        else:
            # Parallel Star: Master on Left (0, 0), Workers in 2 balanced columns on Right
            master_node = self.node_items[ordered_ids[0]]
            master_node.setPos(0.0, 0.0)
            workers = ordered_ids[1:]
            per_col = max(1, math.ceil(len(workers) / 2.0))
            for w_idx, aid in enumerate(workers):
                node = self.node_items[aid]
                col = w_idx // per_col
                row = w_idx % per_col
                col_count = min(per_col, len(workers) - col * per_col)
                total_h = max(0.0, (col_count - 1) * 165.0)
                x = 330.0 + col * 310.0
                y = -total_h / 2.0 + row * 165.0
                node.setPos(x, y)
                edge = MindMapEdgeItem(master_node, node)
                self.scene.addItem(edge)
                self.edges.append(edge)

        self._update_edges()
        self.center_and_fit()

    def _update_edges(self):
        for e in self.edges:
            e.update_position()
        self.scene.update()

    def center_and_fit(self):
        rect = self.scene.itemsBoundingRect().adjusted(-40, -40, 40, 40)
        if rect.isEmpty():
            return
        self.view.setSceneRect(rect)
        self.view.resetTransform()
        vp = self.view.viewport().rect()
        if vp.width() > 60 and vp.height() > 60 and rect.width() > 0 and rect.height() > 0:
            sx = vp.width() / rect.width()
            sy = vp.height() / rect.height()
            scale = max(0.50, min(sx, sy, 1.02))
            self.view.scale(scale, scale)
        self.view.centerOn(rect.center())