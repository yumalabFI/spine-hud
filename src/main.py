import sys

try:
    from .hud import SpineHUD
except ImportError:
    from hud import SpineHUD

from PySide6.QtWidgets import QApplication


app = QApplication(sys.argv)

window = SpineHUD()
window.show()

sys.exit(app.exec())
