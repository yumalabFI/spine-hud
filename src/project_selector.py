from pathlib import Path
from datetime import datetime, date, timedelta

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QLabel,
    QCheckBox,
    QListWidget,
    QMenu,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QInputDialog,
    QMessageBox,
)

try:
    from .projects import (
        ProjectRegistryError,
        load_projects,
        add_project,
        rename_project,
        remove_project,
    )
except ImportError:
    from projects import (
        ProjectRegistryError,
        load_projects,
        add_project,
        rename_project,
        remove_project,
    )


def format_changed_time(path):
    try:
        changed = datetime.fromtimestamp(
            path.stat().st_mtime
        )
    except OSError:
        return "Unknown"

    today = date.today()

    if changed.date() == today:
        return f"Today {changed:%H:%M}"

    if changed.date() == today - timedelta(days=1):
        return f"Yesterday {changed:%H:%M}"

    if changed.year == datetime.now().year:
        return changed.strftime("%-d %b %H:%M")

    return changed.strftime("%-d %b %Y")




def project_status(path):
    try:
        import json

        data = json.loads(
            (path / "spine.json").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, json.JSONDecodeError):
        return "planned"

    leaves = []

    def walk(nodes):
        for node in nodes:
            children = node.get("children", [])

            if children:
                walk(children)
            else:
                leaves.append(
                    node.get("status", "planned")
                )

    walk(data.get("tree", []))

    if not leaves:
        return "planned"

    if any(status == "active" for status in leaves):
        return "active"

    if any(status == "blocked" for status in leaves):
        return "blocked"

    if all(status == "done" for status in leaves):
        return "done"

    return "planned"


def project_status_symbol(status):
    return {
        "done": "✓",
        "active": "●",
        "blocked": "!",
        "planned": "○",
    }.get(status, "○")




class ProjectSelector(QDialog):
    def __init__(self):
        super().__init__()

        self.selected_path = None

        self.setWindowTitle("Spine Projects")
        self.setMinimumWidth(320)

        # Projektivalikko käyttää täsmälleen samaa
        # kokoa ja sijaintia kuin Spine HUD.
        self.settings = QSettings(
            "YumaLab",
            "SpineHUD"
        )

        x = self.settings.value("x")
        y = self.settings.value("y")
        width = self.settings.value("width")
        height = self.settings.value("height")

        if None not in (x, y, width, height):
            try:
                self.setGeometry(
                    int(x),
                    int(y),
                    int(width),
                    int(height)
                )
            except (TypeError, ValueError):
                self.resize(360, 420)
        else:
            self.resize(360, 420)

        self.setStyleSheet("""
            QDialog {
                background: #15171a;
                color: #e8e9eb;
            }

            QLabel {
                color: #aeb4bd;
                font-size: 11px;
                font-weight: bold;
                padding: 6px;
            }

            QListWidget {
                background: #15171a;
                color: #e8e9eb;
                border: none;
                font-size: 12px;
                outline: none;
            }

            QListWidget::item {
                padding: 10px 8px;
                min-height: 28px;
            }

            QListWidget::item:selected {
                background: #252a31;
                color: #ffffff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title = QLabel("SELECT PROJECT")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.list = QListWidget()
        self.list.setContextMenuPolicy(
            Qt.CustomContextMenu
        )
        self.list.customContextMenuRequested.connect(
            self.open_context_menu
        )

        layout.addWidget(self.list, 1)

        self.open_button = QPushButton("OPEN")
        self.open_button.setEnabled(False)
        self.open_button.setStyleSheet("""
            QPushButton {
                background: #25282d;
                color: #e8e9eb;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #30343a;
            }

            QPushButton:disabled {
                color: #686e77;
            }
        """)

        layout.addWidget(self.open_button)

        self.add_button = QPushButton("ADD PROJECT")
        self.add_button.setStyleSheet("""
            QPushButton {
                background: #202329;
                color: #aeb4bd;
                border: none;
                border-radius: 4px;
                padding: 7px;
            }

            QPushButton:hover {
                background: #2b3037;
                color: #ffffff;
            }
        """)

        layout.addWidget(self.add_button)

        self.last_project_checkbox = QCheckBox(
            "Open last project on startup"
        )

        self.last_project_checkbox.setChecked(
            self.settings.value(
                "open_last_project",
                False,
                type=bool
            )
        )

        self.last_project_checkbox.setStyleSheet("""
            QCheckBox {
                color: #aeb4bd;
                padding: 6px;
            }

            QCheckBox:hover {
                color: #ffffff;
            }
        """)

        self.last_project_checkbox.stateChanged.connect(
            self.save_last_project_preference
        )

        layout.addWidget(
            self.last_project_checkbox
        )

        self.quit_button = QPushButton(
            "QUIT SPINE"
        )

        self.quit_button.setStyleSheet("""
            QPushButton {
                background: #202329;
                color: #aeb4bd;
                border: none;
                border-radius: 4px;
                padding: 7px;
            }

            QPushButton:hover {
                background: #30343a;
                color: #ffffff;
            }
        """)

        self.quit_button.clicked.connect(
            self.confirm_quit
        )

        layout.addWidget(
            self.quit_button
        )

        self.load_registry()

        self.list.currentItemChanged.connect(
            self.on_selection_changed
        )

        self.list.itemDoubleClicked.connect(
            self.open_item
        )

        self.open_button.clicked.connect(
            self.open_selected
        )

        self.add_button.clicked.connect(
            self.add_project
        )

        if self.list.count():
            if self.list.currentItem() is None:
                self.list.setCurrentRow(0)

            self.list.setFocus()

    def save_last_project_preference(self, state):
        self.settings.setValue(
            "open_last_project",
            bool(state)
        )
        self.settings.sync()

    def load_registry(self):
        data = load_projects()

        last_opened = data.get("last_opened")

        colors = {
            "done": "#6fbd7a",
            "active": "#f3a847",
            "blocked": "#e56b6f",
            "planned": "#8b929c",
        }

        for project in data.get("projects", []):
            path = project.get("path")
            name = project.get("name")

            if not path:
                continue

            project_path = Path(path)
            spine_file = project_path / "spine.json"

            if not spine_file.exists():
                continue

            is_last = (
                str(project_path) == last_opened
            )

            status = project_status(
                project_path
            )

            arrow = "➜" if is_last else " "
            symbol = project_status_symbol(
                status
            )

            changed_text = format_changed_time(
                spine_file
            )

            item = QListWidgetItem(
                f"{arrow} {symbol}  "
                f"{name or project_path.name}\n"
                f"      {changed_text}"
            )

            item.setForeground(
                QColor(
                    colors.get(
                        status,
                        colors["planned"]
                    )
                )
            )

            item.setData(
                Qt.UserRole,
                str(project_path)
            )

            item.setData(
                Qt.UserRole + 1,
                is_last
            )

            self.list.addItem(item)

            if is_last:
                self.list.setCurrentItem(item)

    def add_project(self):
        # Älä anna ProjectSelectoria parentiksi.
        # Muuten Qt voi periä Spine-valikon geometrian
        # Linuxin kansiovalitsimelle.
        dialog = QFileDialog(
            None,
            "Add Spine project"
        )

        dialog.setFileMode(
            QFileDialog.Directory
        )

        dialog.setOption(
            QFileDialog.ShowDirsOnly,
            True
        )

        if dialog.exec() != QFileDialog.Accepted:
            return

        selected = dialog.selectedFiles()

        if not selected:
            return

        directory = selected[0]

        if not directory:
            return

        path = Path(directory).resolve()

        if not (path / "spine.json").exists():
            QMessageBox.warning(
                self,
                "Not a Spine project",
                "The selected folder does not contain "
                "spine.json."
            )
            return

        try:
            project = add_project(path)
        except ProjectRegistryError as exc:
            QMessageBox.warning(
                self,
                "Add project failed",
                str(exc)
            )
            return

        self.load_registry_refresh()

        for row in range(self.list.count()):
            item = self.list.item(row)

            if item.data(Qt.UserRole) == str(path):
                self.list.setCurrentItem(item)
                break

        QMessageBox.information(
            self,
            "Project added",
            f"Added: {project['name']}"
        )

    def open_context_menu(self, position):
        item = self.list.itemAt(position)

        if item is None:
            return

        self.list.setCurrentItem(item)

        menu = QMenu(self)

        rename_action = menu.addAction(
            "Rename"
        )

        remove_action = menu.addAction(
            "Remove from Spine"
        )

        action = menu.exec(
            self.list.viewport().mapToGlobal(position)
        )

        if action is rename_action:
            self.rename_selected()

        elif action is remove_action:
            self.remove_selected()

    def rename_selected(self):
        item = self.list.currentItem()

        if item is None:
            return

        path = Path(
            item.data(Qt.UserRole)
        )

        current_name = path.name

        # Käytä rekisterissä olevaa nimeä.
        data = load_projects()

        for project in data.get("projects", []):
            if project.get("path") == str(path):
                current_name = project.get(
                    "name",
                    current_name
                )
                break

        name, accepted = QInputDialog.getText(
            self,
            "Rename project",
            "Project name:",
            text=current_name
        )

        if not accepted:
            return

        name = name.strip()

        if not name or name == current_name:
            return

        try:
            rename_project(
                path,
                name
            )
        except ProjectRegistryError as exc:
            QMessageBox.warning(
                self,
                "Rename failed",
                str(exc)
            )
            return

        self.load_registry_refresh()

    def remove_selected(self):
        item = self.list.currentItem()

        if item is None:
            return

        path = Path(
            item.data(Qt.UserRole)
        )

        name = item.text().strip()

        answer = QMessageBox.question(
            self,
            "Remove project",
            f"Remove this project from Spine?\n\n"
            f"{name}\n\n"
            "The project files will NOT be deleted.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if answer != QMessageBox.Yes:
            return

        try:
            remove_project(path)
        except ProjectRegistryError as exc:
            QMessageBox.warning(
                self,
                "Remove failed",
                str(exc)
            )
            return

        self.load_registry_refresh()

        if self.list.count() == 0:
            self.selected_path = None
            self.open_button.setEnabled(False)

    def load_registry_refresh(self):
        current_path = None

        current = self.list.currentItem()

        if current is not None:
            current_path = current.data(
                Qt.UserRole
            )

        self.list.clear()
        self.load_registry()

        if current_path:
            for row in range(self.list.count()):
                item = self.list.item(row)

                if item.data(Qt.UserRole) == current_path:
                    self.list.setCurrentItem(item)
                    break

    def confirm_quit(self):
        answer = QMessageBox.question(
            self,
            "Quit Spine",
            "Quit Spine completely?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if answer == QMessageBox.Yes:
            self.accept()
            app = QApplication.instance()
            if app is not None:
                app.quit()

    def closeEvent(self, event):
        # Projektivalikon X ei sammuta Spineä.
        # Käytä erillistä QUIT SPINE -painiketta.
        event.ignore()

    def keyPressEvent(self, event):
        if event.key() in (
            Qt.Key_Return,
            Qt.Key_Enter
        ):
            self.open_selected()
            return

        if event.key() == Qt.Key_Escape:
            # Esc ei sammuta Spineä.
            # Projektivalikko pysyy auki.
            return

        super().keyPressEvent(event)

    def on_selection_changed(self, current, previous):
        self.open_button.setEnabled(
            current is not None
        )

    def open_selected(self):
        item = self.list.currentItem()

        if item is None:
            return

        self.open_item(item)

    def open_item(self, item):
        path = item.data(Qt.UserRole)

        if not path:
            return

        self.selected_path = Path(path)
        self.accept()


def select_project():
    dialog = ProjectSelector()

    if dialog.exec() != QDialog.Accepted:
        return None

    return dialog.selected_path
