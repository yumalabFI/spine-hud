import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QLockFile, QTimer, QSettings
from PySide6.QtWidgets import QApplication

try:
    from .runtime_env import (
        LOCK_NAME,
        SETTINGS_APP,
    )
except ImportError:
    from runtime_env import (
        LOCK_NAME,
        SETTINGS_APP,
    )

try:
    from . import hud as hud_module
    from .project_selector import select_project
    from .project_registry import set_last_opened
except ImportError:
    import hud as hud_module
    from project_selector import select_project
    from project_registry import set_last_opened


app = None
lock = None
window = None


def open_project(project):
    global window

    project = Path(project).resolve()

    hud_module.PROJECT = project
    hud_module.SPINE_FILE = project / "spine.json"

    set_last_opened(project)

    settings = QSettings(
        "YumaLab",
        SETTINGS_APP
    )

    settings.setValue(
        "last_opened_project",
        str(project)
    )

    settings.sync()

    window = hud_module.SpineHUD()

    window.project_menu_requested.connect(
        show_project_menu_from_hud
    )

    window.show()


def show_project_menu(use_last_project=True):
    global window

    if window is not None:
        window.hide()
        window.deleteLater()
        window = None

    # Vain ohjelman ensimmäinen käynnistys käyttää
    # "Open last project on startup" -asetusta.
    if use_last_project:
        settings = QSettings(
            "YumaLab",
            SETTINGS_APP
        )

        open_last = settings.value(
            "open_last_project",
            False,
            type=bool
        )

        last_opened = settings.value(
            "last_opened_project",
            "",
            type=str
        )

        if open_last and last_opened:
            project = (
                Path(last_opened)
                .expanduser()
                .resolve()
            )

            if (project / "spine.json").exists():
                open_project(project)
                return

    project = select_project()

    if project is None:
        app.quit()
        return

    open_project(project)


def show_project_menu_from_hud():
    # HUDin X tarkoittaa aina takaisin projektivalikkoon.
    # Viimeistä projektia ei avata automaattisesti tässä.
    show_project_menu(
        use_last_project=False
    )


def main():
    global app, lock

    app = QApplication(sys.argv)

    # Projektivalikko saa olla hetken ainoa ikkuna
    # ilman että QApplication lopettaa.
    app.setQuitOnLastWindowClosed(False)

    lock_path = (
        Path(tempfile.gettempdir())
        / LOCK_NAME
    )

    lock = QLockFile(str(lock_path))
    # Recover automatically from stale lock files left by a dead process.
    lock.setStaleLockTime(5000)
    lock.removeStaleLockFile()

    if not lock.tryLock(100):
        return 0

    QTimer.singleShot(
        0,
        lambda: show_project_menu(
            use_last_project=True
        )
    )

    try:
        return app.exec()
    finally:
        lock.unlock()


if __name__ == "__main__":
    raise SystemExit(main())
