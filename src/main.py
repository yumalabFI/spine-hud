import json
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizeGrip,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

PROJECT = Path(__file__).resolve().parent.parent
SPINE_FILE = PROJECT / "spine.json"

COLORS = {
    "done": "#42d66b",
    "active": "#f3a847",
    "blocked": "#ff5f5f",
    "planned": "#8a8f98",
    "idle": "#8a8f98",
}


def run_git(*args):
    result = subprocess.run(
        ["git", "-C", str(PROJECT), *args],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return ""

    return result.stdout.strip()


def git_changed_files():
    output = run_git("status", "--porcelain")
    files = []

    for line in output.splitlines():
        if len(line) < 4:
            continue

        path = line[3:].strip()

        if " -> " in path:
            path = path.split(" -> ", 1)[1]

        files.append(path)

    return files


def path_matches(task_path, changed_file):
    task_path = task_path.rstrip("/")

    return (
        changed_file == task_path
        or changed_file.startswith(task_path + "/")
    )


def node_git_count(node, changed_files):
    matches = set()

    for task_path in node.get("paths", []):
        for changed in changed_files:
            if path_matches(task_path, changed):
                matches.add(changed)

    return len(matches)


def calculated_status(node):
    children = node.get("children", [])

    if not children:
        return node.get("status", "planned")

    statuses = [calculated_status(child) for child in children]

    if "blocked" in statuses:
        return "blocked"

    if "active" in statuses:
        return "active"

    if all(status == "done" for status in statuses):
        return "done"

    if "done" in statuses:
        return "active"

    return "planned"


class SpineHUD(QMainWindow):
    def __init__(self):
        super().__init__()

        self.item_nodes = []
        self.spine_mtime = 0
        self.drag_offset = None

        self.settings = QSettings("YumaLab", "SpineHUD")

        self.setWindowTitle("Spine HUD")

        self.setMinimumSize(170, 300)
        self.resize(250, 800)

        self.setWindowFlags(
            Qt.Window
            | Qt.WindowStaysOnTopHint
        )

        root = QWidget()
        root.setStyleSheet("""
            QWidget {
                background: #15171a;
                color: #e8e9eb;
            }
        """)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(7, 7, 7, 5)
        outer.setSpacing(4)

        # TOP BAR
        self.topbar = QWidget()
        top = QHBoxLayout(self.topbar)
        top.setContentsMargins(0, 0, 0, 0)

        title = QLabel("SPINE HUD")
        title.setStyleSheet("""
            font-size: 12px;
            font-weight: bold;
        """)

        close = QPushButton("×")
        close.setFixedSize(24, 24)
        close.clicked.connect(self.close)

        close.setStyleSheet("""
            QPushButton {
                background: #25282d;
                color: #e8e9eb;
                border: none;
                border-radius: 4px;
                font-size: 16px;
            }

            QPushButton:hover {
                background: #ff5f5f;
            }
        """)

        top.addWidget(title)
        top.addStretch()
        top.addWidget(close)

        outer.addWidget(self.topbar)

        # PROJECT NAME
        self.project_label = QLabel()
        self.project_label.setAlignment(Qt.AlignCenter)
        self.project_label.setStyleSheet("""
            color: #aeb4bd;
            font-size: 11px;
            font-weight: bold;
            padding-bottom: 5px;
        """)

        outer.addWidget(self.project_label)

        # TREE
        self.tree = QTreeWidget()

        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["BUILD", "GIT"])

        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self.tree.setColumnWidth(1, 48)

        self.tree.setIndentation(14)
        self.tree.setAnimated(False)

        # Ei koskaan sivuttaisscrollia.
        self.tree.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.tree.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )

        self.tree.setStyleSheet("""
            QTreeWidget {
                background: #15171a;
                border: none;
                font-size: 11px;
            }

            QHeaderView::section {
                background: #15171a;
                color: #686e77;
                border: none;
                font-size: 9px;
                padding: 3px;
            }

            QTreeWidget::item {
                height: 25px;
            }

            QTreeWidget::item:selected {
                background: #252a31;
            }
        """)

        outer.addWidget(self.tree, 1)

        # RESIZE GRIP
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)

        bottom.addStretch()

        grip = QSizeGrip(self)
        grip.setFixedSize(16, 16)
        grip.setStyleSheet("""
            QSizeGrip {
                background: transparent;
            }
        """)

        bottom.addWidget(grip)

        outer.addLayout(bottom)

        self.setCentralWidget(root)

        self.restore_window_geometry()
        self.reload_tree()
        self.update_columns()

        self.spine_timer = QTimer(self)
        self.spine_timer.timeout.connect(self.check_spine_file)
        self.spine_timer.start(500)

        self.git_timer = QTimer(self)
        self.git_timer.timeout.connect(self.update_git)
        self.git_timer.start(1000)

    def restore_window_geometry(self):
        geometry = self.settings.value("geometry")

        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event):
        self.settings.setValue(
            "geometry",
            self.saveGeometry()
        )
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if event.position().y() <= 40:
                self.drag_offset = (
                    event.globalPosition().toPoint()
                    - self.frameGeometry().topLeft()
                )
                event.accept()

    def mouseMoveEvent(self, event):
        if (
            self.drag_offset is not None
            and event.buttons() & Qt.LeftButton
        ):
            self.move(
                event.globalPosition().toPoint()
                - self.drag_offset
            )
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_offset = None
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_columns()

    def update_columns(self):
        # BUILD venyy automaattisesti, GIT pysyy kiinteänä.
        self.tree.setColumnWidth(1, 48)

    def check_spine_file(self):
        try:
            mtime = SPINE_FILE.stat().st_mtime
        except OSError:
            return

        if mtime != self.spine_mtime:
            self.reload_tree()

    def remember_expanded(self):
        expanded = set()

        def walk(item):
            name = item.data(0, Qt.UserRole)

            if item.isExpanded() and name:
                expanded.add(name)

            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))

        return expanded

    def reload_tree(self):
        if not SPINE_FILE.exists():
            self.project_label.setText("NO spine.json")
            return

        expanded = self.remember_expanded()

        try:
            data = json.loads(
                SPINE_FILE.read_text(encoding="utf-8")
            )
        except Exception:
            self.project_label.setText("INVALID spine.json")
            return

        try:
            self.spine_mtime = SPINE_FILE.stat().st_mtime
        except OSError:
            pass

        self.project_label.setText(
            data.get("project", PROJECT.name).upper()
        )

        self.tree.clear()
        self.item_nodes = []

        for node in data.get("tree", []):
            self.add_node(
                None,
                node,
                expanded
            )

        self.update_columns()
        self.update_git()

    def add_node(self, parent, node, expanded):
        status = calculated_status(node)
        name = node.get("name", "Unnamed")

        if status == "done":
            symbol = "✓"

        elif status == "active":
            symbol = "●"

        elif status == "blocked":
            symbol = "!"

        else:
            symbol = "○"

        item = QTreeWidgetItem([
            f"{symbol}  {name}",
            ""
        ])

        item.setData(
            0,
            Qt.UserRole,
            name
        )

        item.setForeground(
            0,
            QColor(
                COLORS.get(
                    status,
                    COLORS["planned"]
                )
            )
        )

        if parent is None:
            self.tree.addTopLevelItem(item)
        else:
            parent.addChild(item)

        self.item_nodes.append(
            (item, node)
        )

        children = node.get("children", [])

        for child in children:
            self.add_node(
                item,
                child,
                expanded
            )

        if children:
            if name in expanded:
                item.setExpanded(True)
            else:
                item.setExpanded(
                    status in ("active", "blocked")
                )

    def update_git(self):
        changed_files = git_changed_files()

        for item, node in self.item_nodes:
            count = node_git_count(
                node,
                changed_files
            )

            if count:
                item.setText(
                    1,
                    f"M{count}"
                )

                item.setForeground(
                    1,
                    QColor("#f3a847")
                )

            else:
                item.setText(
                    1,
                    "✓"
                )

                item.setForeground(
                    1,
                    QColor("#42d66b")
                )


app = QApplication(sys.argv)

window = SpineHUD()
window.show()

sys.exit(app.exec())
