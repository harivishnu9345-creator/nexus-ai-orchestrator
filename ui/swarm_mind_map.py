from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QLinearGradient
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsPathItem, QFrame, QComboBox
)


class MindMapNode(QGraphicsItem):
    def __init__(self, node_id: str, title: str, role: str, files: list, is_master: bool = False):
        super().__init__()
        self.node_id = node_id
        self.title = title
        self.role = role
        self.files = files or []
        self.is_master = is_master
        self.status = "idle"

        self.width = 230
        base_height = 76
        file_rows = max(1, len(self.files))
        self.height = base_height + (file_rows * 18)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.edges = []

    def add_edge(self, edge):
        self.edges.append(edge)

    def set_status(self, status: str):
        self.status = status
        self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.edges:
                edge.update_path()
        return super().itemChange(change, value)

    def boundingRect(self) -> QRectF:
        return QRectF(-4, -4, self.width + 8, self.height + 8)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        border_color = QColor("#a1a1aa") if (self.is_master or self.status in ("active", "done")) else QColor("#3f3f46")
        header_bg = QColor("#27272a") if self.is_master else QColor("#18181b")

        body_rect = QRectF(0, 0, self.width, self.height)
        grad = QLinearGradient(0, 0, 0, self.height)
        grad.setColorAt(0.0, QColor("#18181b"))
        grad.setColorAt(1.0, QColor("#121215"))

        painter.setBrush(QBrush(grad))
        pen_width = 2.0 if (self.is_master or self.status == "active") else 1.2
        painter.setPen(QPen(border_color, pen_width))
        painter.drawRoundedRect(body_rect, 6, 6)

        header_rect = QRectF(1, 1, self.width - 2, 30)
        painter.setBrush(QBrush(header_bg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(header_rect, 5, 5)

        painter.setPen(QPen(QColor("#f4f4f5")))
        title_font = QFont("Ubuntu", 9, QFont.Weight.Bold)
        painter.setFont(title_font)
        prefix = "MASTER: " if self.is_master else "WORKER: "
        painter.drawText(QRectF(10, 5, self.width - 20, 22), Qt.AlignmentFlag.AlignVCenter, f"{prefix}{self.title}")

        role_font = QFont("Ubuntu", 8, QFont.Weight.Normal)
        painter.setFont(role_font)
        painter.setPen(QPen(QColor("#a1a1aa")))
        painter.drawText(QRectF(10, 36, self.width - 20, 18), Qt.AlignmentFlag.AlignVCenter, f"Role: {self.role} [{self.status.upper()}]")

        painter.setPen(QPen(QColor("#27272a"), 1))
        painter.drawLine(10, 56, int(self.width - 10), 56)

        file_font = QFont("Consolas", 8)
        painter.setFont(file_font)
        y_offset = 62
        if not self.files:
            painter.setPen(QPen(QColor("#71717a")))
            painter.drawText(QRectF(12, y_offset, self.width - 24, 16), Qt.AlignmentFlag.AlignVCenter, "- (Awaiting Master Blueprint)")
        else:
            for fname in self.files:
                chip_rect = QRectF(10, y_offset, self.width - 20, 16)
                painter.setBrush(QBrush(QColor("#09090b")))
                painter.setPen(QPen(QColor("#27272a"), 1))
                painter.drawRoundedRect(chip_rect, 3, 3)

                painter.setPen(QPen(QColor("#d4d4d8")))
                display_name = fname if len(fname) <= 28 else "..." + fname[-25:]
                painter.drawText(QRectF(16, y_offset, self.width - 28, 16), Qt.AlignmentFlag.AlignVCenter, display_name)
                y_offset += 18


class MindMapEdge(QGraphicsPathItem):
    def __init__(self, source_node: MindMapNode, dest_node: MindMapNode):
        super().__init__()
        self.source = source_node
        self.dest = dest_node
        self.source.add_edge(self)
        self.dest.add_edge(self)
        self.setZValue(-1)
        self.update_path()

    def update_path(self):
        start = self.source.scenePos() + QPointF(self.source.width, self.source.height / 2)
        end = self.dest.scenePos() + QPointF(0, self.dest.height / 2)

        path = QPainterPath(start)
        dx = abs(end.x() - start.x()) * 0.55
        ctrl1 = QPointF(start.x() + dx, start.y())
        ctrl2 = QPointF(end.x() - dx, end.y())
        path.cubicTo(ctrl1, ctrl2, end)

        self.setPath(path)
        pen = QPen(QColor("#52525b"), 2.0, Qt.PenStyle.SolidLine)
        self.setPen(pen)


class SwarmMindMapWidget(QWidget):
    session_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.nodes = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toolbar = QFrame()
        self.toolbar.setFixedHeight(34)
        self.toolbar.setStyleSheet("""
            QFrame {
                background-color: #141417;
                border-bottom: 1px solid #27272a;
            }
            QLabel {
                color: #e4e4e7;
                font-size: 11px;
                font-weight: bold;
                border: none;
            }
            QComboBox {
                background-color: #09090b;
                color: #f4f4f5;
                border: 1px solid #3f3f46;
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 11px;
            }
            QPushButton {
                background-color: #1f1f23;
                color: #d4d4d8;
                border: 1px solid #3f3f46;
                border-radius: 3px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #27272a;
                color: #ffffff;
            }
        """)
        tb_layout = QHBoxLayout(self.toolbar)
        tb_layout.setContentsMargins(10, 2, 10, 2)
        tb_layout.setSpacing(8)

        self.lbl_info = QLabel("Swarm Architecture Mind-Map")
        tb_layout.addWidget(self.lbl_info)

        tb_layout.addWidget(QLabel("|  Session History:"))
        self.combo_sessions = QComboBox()
        self.combo_sessions.setFixedWidth(320)
        self.combo_sessions.currentIndexChanged.connect(self._on_session_combo_changed)
        tb_layout.addWidget(self.combo_sessions)

        tb_layout.addStretch()
        btn_reset = QPushButton("Center & Fit Graph")
        btn_reset.clicked.connect(self.fit_graph)
        tb_layout.addWidget(btn_reset)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setStyleSheet("background-color: #09090b; border: none;")

        layout.addWidget(self.toolbar)
        layout.addWidget(self.view, stretch=1)

    def _on_session_combo_changed(self, idx: int):
        if idx >= 0:
            self.session_selected.emit(idx)

    def set_session_list(self, labels: list, current_index: int):
        self.combo_sessions.blockSignals(True)
        self.combo_sessions.clear()
        for lbl in labels:
            self.combo_sessions.addItem(lbl)
        if 0 <= current_index < len(labels):
            self.combo_sessions.setCurrentIndex(current_index)
        self.combo_sessions.blockSignals(False)

    def build_mind_map(
        self,
        master_account: dict,
        worker_accounts: list,
        file_assignments: dict = None,
        node_statuses: dict = None
    ):
        self.scene.clear()
        self.nodes.clear()
        file_assignments = file_assignments or {}
        node_statuses = node_statuses or {}

        m_id = master_account.get("id", "master")
        m_files = file_assignments.get(m_id, ["Project Blueprint [MAP]", "Interface Contracts"])
        master_node = MindMapNode(
            node_id=m_id,
            title=master_account.get("account_name", "Master Node"),
            role="Architect & Dependency Manager",
            files=m_files,
            is_master=True
        )
        master_node.set_status(node_statuses.get(m_id, "idle"))
        master_node.setPos(40, 90)
        self.scene.addItem(master_node)
        self.nodes[m_id] = master_node

        count = len(worker_accounts)
        spacing_y = 125
        start_y = 90 - ((count - 1) * spacing_y) / 2 if count > 1 else 90

        for idx, acc in enumerate(worker_accounts):
            w_id = acc.get("id", f"worker_{idx}")
            assigned_files = file_assignments.get(w_id, [])
            role_label = f"Subordinate Stage {idx + 1}"
            worker_node = MindMapNode(
                node_id=w_id,
                title=acc.get("account_name", f"Worker {idx + 1}"),
                role=role_label,
                files=assigned_files,
                is_master=False
            )
            worker_node.set_status(node_statuses.get(w_id, "idle"))
            worker_node.setPos(390, start_y + (idx * spacing_y))
            self.scene.addItem(worker_node)
            self.nodes[w_id] = worker_node

            edge = MindMapEdge(master_node, worker_node)
            self.scene.addItem(edge)

        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-40, -40, 40, 40))

    def update_node_status(self, account_id: str, status: str):
        if account_id in self.nodes:
            self.nodes[account_id].set_status(status)

    def fit_graph(self):
        if self.scene.items():
            self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-30, -30, 30, 30), Qt.AspectRatioMode.KeepAspectRatio)
