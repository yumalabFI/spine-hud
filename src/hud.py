import json
import math
import subprocess
import uuid
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QSettings, QEvent, QSize, QRectF
from PySide6.QtGui import QColor, QPainter, QBrush
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QMenu,
    QInputDialog,
    QMessageBox,
    QSizeGrip,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from engine import (
    SpineValidationError,
    validate_spine_data,
    validate_task_name,
)

from storage import (
    SpineStorageError,
    load_spine,
    save_spine,
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


try:
    from .engine import (
        get_changed_files,
        path_matches,
        calculated_status,
    )
except ImportError:
    from engine import (
        get_changed_files,
        path_matches,
        calculated_status,
    )


def git_changed_files():
    return get_changed_files(PROJECT)


def node_git_count(node, changed_files):
    count = 0

    for task_path in node.get("paths", []):
        for changed_file in changed_files:
            if path_matches(task_path, changed_file):
                count += 1
                break

    for child in node.get("children", []):
        count += node_git_count(
            child,
            changed_files
        )

    return count


class SpineHUD(QMainWindow):
    def __init__(self):
        super().__init__()

        self.item_nodes = []
        self.spine_mtime = 0
        self.drag_offset = None


        self.active_items = []
        self.arrow_phase = False


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
        self.tree.installEventFilter(self)

        # Hiirellä tapahtuva puun järjestely.
        self.tree.setSortingEnabled(False)
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDefaultDropAction(Qt.MoveAction)
        self.tree.setDragDropMode(
            QAbstractItemView.InternalMove
        )

        self.tree.model().rowsMoved.connect(
            self.on_tree_rows_moved
        )

        self.tree.setContextMenuPolicy(
            Qt.CustomContextMenu
        )
        self.tree.customContextMenuRequested.connect(
            self.open_task_menu
        )

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

        self.arrow_timer = QTimer(self)
        self.arrow_timer.timeout.connect(self.animate_active_arrow)
        self.arrow_timer.start(450)



    def restore_window_geometry(self):
        geometry = self.settings.value("geometry")

        if geometry:
            self.restoreGeometry(geometry)

        # Varmista että HUD jää näkyvälle näytölle.
        window_rect = self.frameGeometry()

        screens = QApplication.screens()

        visible = any(
            screen.availableGeometry().intersects(window_rect)
            for screen in screens
        )

        if not visible:
            screen = QApplication.primaryScreen()

            if screen is not None:
                area = screen.availableGeometry()

                self.move(
                    area.left() + 20,
                    area.top() + 20
                )

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
        self.tree.setColumnWidth(1, 48)

    def eventFilter(self, obj, event):
        if obj is self.tree and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape:
                self.return_to_active_task()
                return True

        return super().eventFilter(obj, event)

    def on_tree_rows_moved(self, *args):
        # Anna Qt:n viimeistellä pudotus ennen tallennusta.
        QTimer.singleShot(
            0,
            self.save_tree_structure
        )

    def save_tree_structure(self):
        try:
            data = load_spine(SPINE_FILE)
        except Exception:
            return

        nodes_by_id = {}

        def index_nodes(nodes):
            for node in nodes:
                node_id = node.get("id")

                if node_id:
                    nodes_by_id[node_id] = node

                index_nodes(
                    node.get("children", [])
                )

        index_nodes(data.get("tree", []))

        def rebuild_item(item):
            node_id = item.data(
                0,
                Qt.UserRole + 1
            )

            node = nodes_by_id.get(node_id)

            if node is None:
                return None

            children = []

            for index in range(
                item.childCount()
            ):
                child_node = rebuild_item(
                    item.child(index)
                )

                if child_node is not None:
                    children.append(child_node)

            # Säilytä package/branch myös tyhjänä.
            if children or "children" in node:
                node["children"] = children
            else:
                node.pop("children", None)

            return node

        new_tree = []

        for index in range(
            self.tree.topLevelItemCount()
        ):
            node = rebuild_item(
                self.tree.topLevelItem(index)
            )

            if node is not None:
                new_tree.append(node)

        def normalize(nodes):
            for index, node in enumerate(
                nodes,
                start=1
            ):
                node["order"] = index * 10
                normalize(
                    node.get("children", [])
                )

        normalize(new_tree)

        data["tree"] = new_tree

        try:
            save_spine(
                SPINE_FILE,
                data
            )
        except SpineStorageError as exc:
            QMessageBox.warning(
                self,
                "Move failed",
                str(exc)
            )

            # Virheellinen pudotus palautetaan levyltä.
            self.reload_tree()
            return

        self.reload_tree()

    def open_task_menu(self, position):
        item = self.tree.itemAt(position)

        if item is None:
            return

        selected_node = None

        for tree_item, node in self.item_nodes:
            if tree_item is item:
                selected_node = node
                break

        if selected_node is None:
            return

        menu = QMenu(self)

        children = selected_node.get("children", [])
        status = selected_node.get("status", "planned")

        # Leaf-tehtävien tilakomennot
        if not children:
            start_action = menu.addAction("Start")
            done_action = menu.addAction("Done")
            block_action = menu.addAction("Blocked")

            menu.addSeparator()

        else:
            start_action = None
            done_action = None
            block_action = None

        add_child_action = menu.addAction("Add child")
        rename_action = menu.addAction("Rename")

        drag_hint_action = menu.addAction("Move by dragging")
        drag_hint_action.setEnabled(False)

        remove_action = menu.addAction("Remove")

        action = menu.exec(
            self.tree.viewport().mapToGlobal(position)
        )

        if action is None:
            return

        name = selected_node.get("name", "")

        if action is start_action:
            self.set_task_status(name, "active")

        elif action is done_action:
            self.set_task_status(name, "done")

        elif action is block_action:
            self.set_task_status(name, "blocked")

        elif action is add_child_action:
            self.add_child_task(selected_node)

        elif action is rename_action:
            self.rename_task(selected_node)

        elif action is remove_action:
            self.remove_task(selected_node)

    def remove_task(self, selected_node):
        node_id = selected_node.get("id")
        node_name = selected_node.get("name", "")

        if not node_id:
            QMessageBox.warning(
                self,
                "Cannot remove",
                "Task has no persistent ID."
            )
            return

        answer = QMessageBox.question(
            self,
            "Remove",
            f'Remove "{node_name}" and everything under it?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if answer != QMessageBox.Yes:
            return

        try:
            data = load_spine(SPINE_FILE)
        except Exception:
            return

        removed = False

        def remove_exact(nodes):
            nonlocal removed

            for index, node in enumerate(nodes):
                if node.get("id") == node_id:
                    del nodes[index]
                    removed = True
                    return

                remove_exact(node.get("children", []))

                if removed:
                    return

        remove_exact(data.get("tree", []))

        if not removed:
            QMessageBox.warning(
                self,
                "Remove failed",
                "The selected task could not be found."
            )
            return

        try:
            validate_spine_data(data)
        except SpineValidationError as exc:
            QMessageBox.warning(
                self,
                "Invalid project tree",
                str(exc)
            )
            return

        save_spine(
            SPINE_FILE,
            data
        )

    def rename_task(self, selected_node):
        node_id = selected_node.get("id")
        old_name = selected_node.get("name", "")

        new_name, ok = QInputDialog.getText(
            self,
            "Rename",
            "Name:",
            text=old_name
        )

        new_name = new_name.strip()

        if not ok or not new_name or new_name == old_name:
            return

        try:
            data = load_spine(SPINE_FILE)
        except Exception:
            return

        target = None

        def find_node(nodes):
            nonlocal target

            for node in nodes:
                if node_id and node.get("id") == node_id:
                    target = node
                    return

                if not node_id and node.get("name") == old_name:
                    target = node
                    return

                find_node(node.get("children", []))

                if target is not None:
                    return

        find_node(data.get("tree", []))

        if target is None:
            return

        target["name"] = new_name

        save_spine(
            SPINE_FILE,
            data
        )

    def add_child_task(self, selected_node):
        parent_id = selected_node.get("id")
        parent_name = selected_node.get("name", "")

        child_name, ok = QInputDialog.getText(
            self,
            "Add child",
            f"Add under {parent_name}:"
        )

        if not ok:
            return

        try:
            child_name = validate_task_name(child_name)
        except SpineValidationError as exc:
            QMessageBox.warning(
                self,
                "Invalid task",
                str(exc)
            )
            return

        try:
            data = load_spine(SPINE_FILE)
        except Exception:
            return

        target = None

        def find_node(nodes):
            nonlocal target

            for node in nodes:
                # ID ensisijainen, nimi fallback vanhemmille nodeille.
                if parent_id and node.get("id") == parent_id:
                    target = node
                    return

                if not parent_id and node.get("name") == parent_name:
                    target = node
                    return

                find_node(node.get("children", []))

                if target is not None:
                    return

        find_node(data.get("tree", []))

        if target is None:
            return

        children = target.setdefault("children", [])

        next_order = (
            max(
                (child.get("order", 0) for child in children),
                default=0
            ) + 10
        )

        children.append({
            "id": f"task-{uuid.uuid4().hex[:12]}",
            "name": child_name,
            "status": "planned",
            "paths": [],
            "order": next_order
        })

        try:
            validate_spine_data(data)
        except SpineValidationError as exc:
            QMessageBox.warning(
                self,
                "Invalid project tree",
                str(exc)
            )
            return

        save_spine(
            SPINE_FILE,
            data
        )

        # Muista että tämä parent halutaan pitää auki reloadin jälkeen.
        for item, node in self.item_nodes:
            if node.get("name") == parent_name:
                item.setExpanded(True)
                break

    def set_task_status(self, task_name, new_status):
        try:
            data = load_spine(SPINE_FILE)
        except Exception:
            return

        selected = None

        def walk(nodes):
            nonlocal selected

            for node in nodes:
                children = node.get("children", [])

                # vain leaf-tehtäville status
                if not children:
                    if new_status == "active" and node.get("status") == "active":
                        node["status"] = "planned"

                    if node.get("name") == task_name:
                        selected = node

                if children:
                    walk(children)

        walk(data.get("tree", []))

        if selected is None:
            return

        if new_status == "active":
            # vain yksi aktiivinen leaf kerrallaan
            def clear_others(nodes):
                for node in nodes:
                    children = node.get("children", [])

                    if not children and node is not selected:
                        if node.get("status") == "active":
                            node["status"] = "planned"

                    if children:
                        clear_others(children)

            clear_others(data.get("tree", []))

        selected["status"] = new_status

        save_spine(
            SPINE_FILE,
            data
        )

    def return_to_active_task(self):
        # ESC on vain navigointia.
        # Se ei koskaan muuta spine.json-tiedostoa.
        for item, node in self.item_nodes:
            if (
                not node.get("children")
                and node.get("status") == "active"
            ):
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)
                return

    def start_selected_task(self):
        item = self.tree.currentItem()

        if item is None:
            return

        # Pääoksia/paketteja ei käynnistetä työnä.
        if item.childCount() > 0:
            return

        task_name = item.data(0, Qt.UserRole)

        if not task_name:
            return

        try:
            data = load_spine(SPINE_FILE)
        except Exception:
            return

        selected = None

        def walk(nodes):
            nonlocal selected

            for node in nodes:
                children = node.get("children", [])

                # Vain leaf-tehtävät voivat olla active.
                if not children:
                    if node.get("status") == "active":
                        node["status"] = "planned"

                    if node.get("name") == task_name:
                        selected = node

                if children:
                    walk(children)

        walk(data.get("tree", []))

        if selected is None:
            return

        # Valmista tehtävää ei vahingossa käynnistetä uudestaan.
        if selected.get("status") == "done":
            return

        selected["status"] = "active"

        save_spine(
            SPINE_FILE,
            data
        )

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
            data = load_spine(SPINE_FILE)
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

        # Säilytä valinta puun reloadin yli.
        selected_name = None
        current = self.tree.currentItem()

        if current is not None:
            selected_name = current.data(0, Qt.UserRole)

        self.tree.clear()
        self.item_nodes = []
        self.active_items = []

        for node in data.get("tree", []):
            self.add_node(
                None,
                node,
                expanded
            )

        self.update_columns()
        self.update_git()

        # Palauta sama valittu tehtävä reloadin jälkeen.
        if selected_name:
            for item, node in self.item_nodes:
                if node.get("name") == selected_name:
                    self.tree.setCurrentItem(item)
                    break


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

        item.setData(
            0,
            Qt.UserRole + 1,
            node.get("id")
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

        # Aktiivinen tehtävä erottuu nuolella + boldilla.
        if not node.get("children") and node.get("status") == "active":
            item.setText(0, f"➜  {name}")

            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)

            item.setForeground(
                0,
                QColor("#f3a847")
            )

            self.active_items.append((item, name))

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
            # Spine näyttää keskeneräisen työn oletuksena auki.
            # Valmis oksa saa jäädä suljetuksi.
            if status != "done":
                item.setExpanded(True)
            elif name in expanded:
                item.setExpanded(True)
            else:
                item.setExpanded(False)

    def animate_active_arrow(self):
        self.arrow_phase = not self.arrow_phase

        for item, name in self.active_items:
            if self.arrow_phase:
                item.setText(0, f" ➜ {name}")
            else:
                item.setText(0, f"➜  {name}")

    def update_git(self):
        changed_files = git_changed_files()

        for item, node in self.item_nodes:
            is_active_leaf = (
                not node.get("children")
                and node.get("status") == "active"
            )

            if is_active_leaf:
                count = node_git_count(
                    node,
                    changed_files
                )
            else:
                count = 0

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
                    "–"
                )

                item.setForeground(
                    1,
                    QColor("#555b63")
                )

