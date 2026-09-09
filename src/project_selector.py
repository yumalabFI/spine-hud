from pathlib import Path
from datetime import datetime, date, timedelta

from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QColor

try:
    from .window_behavior import (
        OPACITY_MAX,
        OPACITY_MIN,
        apply_opacity,
        apply_window_behavior,
        read_compact_mode,
        read_opacity,
        save_compact_mode,
        save_opacity,
    )
except ImportError:
    from window_behavior import (
        OPACITY_MAX,
        OPACITY_MIN,
        apply_opacity,
        apply_window_behavior,
        read_compact_mode,
        read_opacity,
        save_compact_mode,
        save_opacity,
    )

try:
    from .runtime_env import (
        IS_DEV,
        SETTINGS_APP,
        WINDOW_SUFFIX,
    )
except ImportError:
    from runtime_env import (
        IS_DEV,
        SETTINGS_APP,
        WINDOW_SUFFIX,
    )
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
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QInputDialog,
    QMessageBox,
    QSizePolicy,
    QSlider,
)

try:
    from .project_registry import ProjectRegistryError
    from .project_service import (
        register_existing_project,
        create_new_project,
        initialize_existing_project,
        load_project_registry,
        scan_projects,
        rename_existing_project,
        remove_existing_project,
    )
except ImportError:
    from project_registry import ProjectRegistryError
    from project_service import (
        register_existing_project,
        create_new_project,
        initialize_existing_project,
        load_project_registry,
        scan_projects,
        rename_existing_project,
        remove_existing_project,
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
        self._quit_confirmed = False

        self.setWindowTitle("Spine Projects" + WINDOW_SUFFIX)
        self.setMinimumWidth(320)

        # Projektivalikko käyttää täsmälleen samaa
        # kokoa ja sijaintia kuin Spine HUD.
        self.settings = QSettings(
            "YumaLab",
            SETTINGS_APP
        )

        apply_window_behavior(
            self,
            self.settings,
        )

        self.geometry_save_timer = QTimer(self)
        self.geometry_save_timer.setSingleShot(True)
        self.geometry_save_timer.timeout.connect(
            self.save_window_geometry
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

        self.setStyleSheet(f"""
            QDialog {{
                background: #15171a;
                color: #e8e9eb;
                border: none;
            }}

            QLabel {{
                color: #aeb4bd;
                font-size: 11px;
                font-weight: bold;
                padding: 6px;
            }}

            QListWidget {{
                background: #15171a;
                color: #e8e9eb;
                border: none;
                font-size: 12px;
                outline: none;
            }}

            QListWidget::item {{
                padding: 10px 72px 10px 8px;
                min-height: 28px;
            }}

            QListWidget::item:selected {{
                background: #252a31;
                color: #ffffff;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.list = QListWidget()
        self.list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        self.list.setContextMenuPolicy(
            Qt.CustomContextMenu
        )
        self.list.customContextMenuRequested.connect(
            self.open_context_menu
        )

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

        self.open_button.setParent(
            self.list.viewport()
        )
        self.open_button.setFixedSize(58, 24)
        self.open_button.hide()

        self.new_button = QPushButton("NEW PROJECT")
        self.new_button.setStyleSheet("""
            QPushButton {
                background: #25282d;
                color: #e8e9eb;
                border: none;
                border-radius: 4px;
                padding: 7px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #30343a;
                color: #ffffff;
            }
        """)

        layout.addWidget(self.new_button)

        self.add_button = QPushButton("ADD EXISTING PROJECT")
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

        self.scan_button = QPushButton("SCAN PROJECTS")
        self.scan_button.setStyleSheet("""
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

        layout.addWidget(self.scan_button)

        projects_label = QLabel("PROJECTS")
        projects_label.setStyleSheet("""
            QLabel {
                color: #686e77;
                font-size: 10px;
                font-weight: bold;
                padding: 8px 4px 3px 4px;
            }
        """)

        layout.addWidget(projects_label)

        layout.addWidget(self.list, 1)

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

        self.compact_checkbox = QCheckBox(
            "Compact mode"
        )

        self.compact_checkbox.setChecked(
            read_compact_mode(
                self.settings
            )
        )

        self.compact_checkbox.setStyleSheet("""
            QCheckBox {
                color: #aeb4bd;
                padding: 6px;
            }

            QCheckBox:hover {
                color: #ffffff;
            }
        """)

        self.compact_checkbox.stateChanged.connect(
            self.save_compact_preference
        )

        layout.addWidget(
            self.compact_checkbox
        )

        self.opacity_label = QLabel()

        self.opacity_slider = QSlider(
            Qt.Horizontal
        )
        self.opacity_slider.setRange(
            OPACITY_MIN,
            OPACITY_MAX
        )
        self.opacity_slider.setSingleStep(5)
        self.opacity_slider.setPageStep(10)

        opacity = read_opacity(
            self.settings
        )

        self.opacity_slider.setValue(
            opacity
        )

        self.update_opacity_label(
            opacity
        )

        self.opacity_slider.valueChanged.connect(
            self.change_opacity
        )

        layout.addWidget(
            self.opacity_label
        )
        layout.addWidget(
            self.opacity_slider
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

        self.list.verticalScrollBar().valueChanged.connect(
            self.position_open_button
        )

        self.list.itemDoubleClicked.connect(
            self.open_item
        )

        self.open_button.clicked.connect(
            self.open_selected
        )

        self.new_button.clicked.connect(
            self.new_project
        )

        self.add_button.clicked.connect(
            self.add_project
        )

        self.scan_button.clicked.connect(
            self.scan_projects
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

    def save_compact_preference(self, state):
        save_compact_mode(
            self.settings,
            bool(state),
        )

    def update_opacity_label(self, value):
        self.opacity_label.setText(
            f"Opacity: {int(value)}%"
        )

    def change_opacity(self, value):
        value = save_opacity(
            self.settings,
            value,
        )

        self.update_opacity_label(
            value
        )

        apply_opacity(
            self,
            value,
        )

    def load_registry(self):
        data = load_project_registry()

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

            item.setData(
                Qt.UserRole + 2,
                "registered"
            )

            self.list.addItem(item)

            if is_last:
                self.list.setCurrentItem(item)

    def new_project(self):
        base_directory = QFileDialog.getExistingDirectory(
            None,
            "Choose location for new Spine project"
        )

        if not base_directory:
            return

        name, accepted = QInputDialog.getText(
            self,
            "New Spine project",
            "Project name:"
        )

        if not accepted:
            return

        name = name.strip()

        if not name:
            return

        invalid_chars = '<>:"/\\|?*'

        if (
            name in (".", "..")
            or any(char in name for char in invalid_chars)
        ):
            QMessageBox.warning(
                self,
                "Invalid project name",
                "Choose a project name without path "
                "separators or reserved characters."
            )
            return

        project_path = (
            Path(base_directory) / name
        ).resolve()

        try:
            project = create_new_project(project_path)
        except (FileExistsError, SystemExit, ProjectRegistryError) as exc:
            QMessageBox.warning(
                self,
                "Project creation failed",
                f"Could not create Spine project:\n"
                f"{project_path}\n\n{exc}"
            )
            return

        self.load_registry_refresh()

        for row in range(self.list.count()):
            item = self.list.item(row)

            if item.data(Qt.UserRole) == str(project_path):
                self.list.setCurrentItem(item)
                break

        QMessageBox.information(
            self,
            "Project created",
            f"Created: {project['name']}"
        )

        self.open_selected()

    def add_project(self):
        directory = QFileDialog.getExistingDirectory(
            None,
            "Choose existing project"
        )

        if not directory:
            return

        path = Path(directory).resolve()

        try:
            if (path / "spine.json").exists():
                project = register_existing_project(path)
            else:
                answer = QMessageBox.question(
                    self,
                    "Make Spine project?",
                    "This project does not contain spine.json.\n\n"
                    "Make this existing project a Spine project?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )

                if answer != QMessageBox.Yes:
                    return

                project = initialize_existing_project(path)

        except (SystemExit, ProjectRegistryError) as exc:
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

    def scan_projects(self):
        roots = [
            Path.home(),
            Path.home() / "VerkkoJako",
        ]

        found = scan_projects(
            roots=roots,
            max_depth=5
        )

        # Poista mahdolliset vanhat FOUND-rivit.
        for row in range(
            self.list.count() - 1,
            -1,
            -1
        ):
            item = self.list.item(row)

            if item.data(Qt.UserRole + 2) in (
                "found",
                "found_header"
            ):
                self.list.takeItem(row)

        if not found:
            QMessageBox.information(
                self,
                "Scan projects",
                "No new projects found."
            )
            return

        header = QListWidgetItem(
            "FOUND PROJECTS"
        )
        header.setData(
            Qt.UserRole + 2,
            "found_header"
        )
        header.setFlags(Qt.NoItemFlags)
        header.setForeground(
            QColor("#686e77")
        )

        self.list.addItem(header)

        for project in found:
            self.add_scan_result(project)

        self.open_button.hide()

    def add_scan_result(self, project):
        item = QListWidgetItem()

        item.setData(
            Qt.UserRole,
            project["path"]
        )
        item.setData(
            Qt.UserRole + 2,
            "found"
        )

        item.setSizeHint(
            self.list.sizeHintForIndex(
                self.list.model().index(
                    max(0, self.list.count() - 1),
                    0
                )
            )
        )

        row = QWidget()

        layout = QHBoxLayout(row)
        layout.setContentsMargins(
            8,
            5,
            8,
            5
        )
        layout.setSpacing(8)

        project_path = Path(project["path"])

        try:
            display_path = "~/" + str(
                project_path.relative_to(
                    Path.home()
                )
            )
        except ValueError:
            display_path = str(project_path)

        if len(display_path) > 38:
            display_path = (
                display_path[:16]
                + "..."
                + display_path[-19:]
            )

        git_status = project.get(
            "git_status",
            "GIT"
        )

        last_commit = project.get(
            "last_commit"
        )

        if last_commit:
            metadata = (
                f"GIT · {git_status} · "
                f"last commit {last_commit}"
            )
        else:
            metadata = (
                f"GIT · {git_status}"
            )

        label = QLabel(
            f"<b>{project['name']}</b><br>"
            f"<span style='color:#aeb4bd;'>"
            f"{metadata}</span><br>"
            f"<span style='color:#686e77;'>"
            f"{display_path}</span>"
        )
        label.setToolTip(
            project["path"]
        )
        label.setMinimumWidth(0)
        label.setSizePolicy(
            QSizePolicy.Ignored,
            QSizePolicy.Preferred
        )
        label.setStyleSheet("""
            QLabel {
                color: #aeb4bd;
                font-size: 10px;
            }
        """)

        button = QPushButton(
            "ADD"
            if project["has_spine"]
            else "MAKE SPINE PROJECT"
        )

        button.setFixedSize(148, 28)

        button.setStyleSheet("""
            QPushButton {
                background: #25282d;
                color: #e8e9eb;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #30343a;
                color: #ffffff;
            }
        """)

        if project["has_spine"]:
            button.clicked.connect(
                lambda checked=False, path=project_path:
                self.add_scanned_project(path)
            )
        else:
            button.clicked.connect(
                lambda checked=False, path=project_path:
                self.initialize_scanned_project(path)
            )

        layout.addWidget(label, 1)
        layout.addWidget(button)

        row.setMinimumHeight(62)

        item.setSizeHint(
            row.sizeHint()
        )

        self.list.addItem(item)
        self.list.setItemWidget(
            item,
            row
        )

    def add_scanned_project(self, path):
        try:
            project = register_existing_project(path)
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

    def initialize_scanned_project(self, path):
        answer = QMessageBox.question(
            self,
            "Make Spine project?",
            f"Make Spine project in this folder?\n\n{path}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if answer != QMessageBox.Yes:
            return

        try:
            project = initialize_existing_project(path)
        except (SystemExit, ProjectRegistryError) as exc:
            QMessageBox.warning(
                self,
                "Make Spine project failed",
                f"Could not make Spine project in:\n"
                f"{path}\n\n{exc}"
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
        data = load_project_registry()

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
            rename_existing_project(
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
            remove_existing_project(path)
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

    def save_window_geometry(self):
        geometry = self.geometry()

        self.settings.setValue(
            "x",
            geometry.x()
        )
        self.settings.setValue(
            "y",
            geometry.y()
        )
        self.settings.setValue(
            "width",
            geometry.width()
        )
        self.settings.setValue(
            "height",
            geometry.height()
        )

        self.settings.sync()

    def confirm_quit(self):
        answer = QMessageBox.question(
            self,
            "Quit Spine?",
            "Are you sure you want to quit Spine?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if answer != QMessageBox.Yes:
            return

        self._quit_confirmed = True

        app = QApplication.instance()

        if app is not None:
            app.quit()

    def schedule_geometry_save(self):
        if hasattr(self, "geometry_save_timer"):
            self.geometry_save_timer.start(200)

    def moveEvent(self, event):
        super().moveEvent(event)
        self.schedule_geometry_save()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.schedule_geometry_save()

    def closeEvent(self, event):
        if self._quit_confirmed:
            self.save_window_geometry()
            event.accept()
            return

        event.ignore()
        self.save_window_geometry()
        self.confirm_quit()

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
        has_selection = current is not None

        self.open_button.setEnabled(
            has_selection
        )

        self.position_open_button()

    def position_open_button(self):
        item = self.list.currentItem()

        if (
            item is None
            or item.data(Qt.UserRole + 2) != "registered"
        ):
            self.open_button.hide()
            return

        rect = self.list.visualItemRect(item)

        if not rect.isValid():
            self.open_button.hide()
            return

        width = self.open_button.width()
        height = self.open_button.height()

        x = rect.right() - width - 8
        y = rect.top() + max(
            0,
            (rect.height() - height) // 2
        )

        self.open_button.move(x, y)
        self.open_button.show()
        self.open_button.raise_()

    def open_selected(self):
        item = self.list.currentItem()

        if item is None:
            return

        self.open_item(item)

    def open_item(self, item):
        if item.data(Qt.UserRole + 2) != "registered":
            return

        path = item.data(Qt.UserRole)

        if not path:
            return

        self.selected_path = Path(path)
        self.save_window_geometry()
        self.accept()


def select_project():
    dialog = ProjectSelector()

    if dialog.exec() != QDialog.Accepted:
        return None

    return dialog.selected_path
