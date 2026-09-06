import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

COLORS = {
    "done": "#42d66b",
    "active": "#f3a847",
    "blocked": "#ff5f5f",
    "planned": "#62a8ff",
    "idle": "#8a8f98",
}

SPINE_FILE = "spine.json"


def calculated_status(node):
    children = node.get("children", [])

    if not children:
        return node.get("status", "idle")

    statuses = [calculated_status(child) for child in children]

    if "blocked" in statuses:
        return "blocked"

    if "active" in statuses:
        return "active"

    if all(status == "done" for status in statuses):
        return "done"

    if "done" in statuses:
        return "active"

    if "planned" in statuses:
        return "planned"

    return "idle"


class SpineHUD(QMainWindow):
    def __init__(self):
        super().__init__()

        self.project_path = None
        self.project_data = None

        self.setWindowTitle("Spine HUD")
        self.resize(190, 800)

        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )

        self.build_ui()

    def build_ui(self):
        root = QWidget()

        root.setStyleSheet("""
            QWidget {
                background: #15171a;
                color: #e8e9eb;
            }
        """)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # TOP BAR
        topbar = QHBoxLayout()

        title = QLabel("SPINE HUD")
        title.setStyleSheet("""
            font-size: 12px;
            font-weight: bold;
        """)

        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self.close)

        close_btn.setStyleSheet("""
            QPushButton {
                background: #25282d;
                color: #e8e9eb;
                border: none;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #ff5f5f;
                color: white;
            }
        """)

        topbar.addWidget(title)
        topbar.addStretch()
        topbar.addWidget(close_btn)

        layout.addLayout(topbar)

        # PROJECT NAME
        self.project_label = QLabel("NO PROJECT")
        self.project_label.setAlignment(Qt.AlignCenter)

        self.project_label.setStyleSheet("""
            color: #9da3ad;
            font-size: 11px;
            font-weight: bold;
            padding-bottom: 5px;
        """)

        layout.addWidget(self.project_label)

        # TREE
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(15)
        self.tree.setAnimated(True)
        self.tree.setRootIsDecorated(True)

        self.tree.setStyleSheet("""
            QTreeWidget {
                background: #15171a;
                border: none;
                font-size: 11px;
            }

            QTreeWidget::item {
                height: 24px;
            }

            QTreeWidget::item:selected {
                background: #252a31;
            }
        """)

        layout.addWidget(self.tree)

        # OPEN PROJECT BUTTON
        open_btn = QPushButton("OPEN PROJECT")
        open_btn.clicked.connect(self.choose_project)

        open_btn.setStyleSheet("""
            QPushButton {
                background: #25282d;
                border: 1px solid #34383f;
                border-radius: 4px;
                padding: 5px;
            }

            QPushButton:hover {
                background: #30343a;
            }
        """)

        layout.addWidget(open_btn)

        self.setCentralWidget(root)

    def choose_project(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Choose Spine project",
            str(Path.home())
        )

        if folder:
            self.load_project(Path(folder))

    def load_project(self, path):
        config_path = path / SPINE_FILE

        if not config_path.exists():
            self.project_label.setText("NO spine.json")
            self.tree.clear()
            return

        try:
            data = json.loads(
                config_path.read_text(encoding="utf-8")
            )
        except Exception:
            self.project_label.setText("INVALID spine.json")
            self.tree.clear()
            return

        self.project_path = path
        self.project_data = data

        project_name = data.get("project", path.name)

        self.project_label.setText(project_name.upper())

        self.tree.clear()

        for node in data.get("tree", []):
            self.add_node(None, node)

    def add_node(self, parent, node):
        status = calculated_status(node)

        item = QTreeWidgetItem([
            f"●  {node.get('name', 'Unnamed')}"
        ])

        item.setForeground(
            0,
            QColor(COLORS.get(status, COLORS["idle"]))
        )

        if parent is None:
            self.tree.addTopLevelItem(item)
        else:
            parent.addChild(item)

        children = node.get("children", [])

        for child in children:
            self.add_node(item, child)

        # Only unfinished / problematic branches open by default
        if children:
            item.setExpanded(
                status in ("active", "blocked")
            )


app = QApplication(sys.argv)

window = SpineHUD()
window.show()

sys.exit(app.exec())
