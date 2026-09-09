from PySide6.QtCore import Qt


OPACITY_KEY = "window_opacity"
OPACITY_MIN = 40
OPACITY_MAX = 100
OPACITY_DEFAULT = 100

COMPACT_KEY = "compact_mode"
COMPACT_DEFAULT = False

HUD_NORMAL_MIN_WIDTH = 170
HUD_NORMAL_MIN_HEIGHT = 300
HUD_COMPACT_MIN_WIDTH = 170
HUD_COMPACT_MIN_HEIGHT = 100

HUD_NORMAL_ROW_HEIGHT = 25
HUD_COMPACT_ROW_HEIGHT = 21

HUD_NORMAL_MARGIN = 7
HUD_COMPACT_MARGIN = 0

HUD_NORMAL_SPACING = 4
HUD_COMPACT_SPACING = 0


def clamp_opacity(value) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = OPACITY_DEFAULT

    return max(
        OPACITY_MIN,
        min(OPACITY_MAX, value)
    )


def read_opacity(settings) -> int:
    return clamp_opacity(
        settings.value(
            OPACITY_KEY,
            OPACITY_DEFAULT
        )
    )


def save_opacity(settings, value) -> int:
    value = clamp_opacity(value)

    settings.setValue(
        OPACITY_KEY,
        value
    )
    settings.sync()

    return value


def apply_opacity(window, value) -> None:
    value = clamp_opacity(value)

    window.setWindowOpacity(
        value / 100.0
    )


def read_compact_mode(settings) -> bool:
    return settings.value(
        COMPACT_KEY,
        COMPACT_DEFAULT,
        type=bool,
    )


def save_compact_mode(settings, enabled) -> bool:
    enabled = bool(enabled)

    settings.setValue(
        COMPACT_KEY,
        enabled,
    )
    settings.sync()

    return enabled


def apply_hud_compact_mode(window, enabled) -> None:
    enabled = bool(enabled)

    if enabled:
        window.setMinimumSize(
            HUD_COMPACT_MIN_WIDTH,
            HUD_COMPACT_MIN_HEIGHT,
        )
    else:
        window.setMinimumSize(
            HUD_NORMAL_MIN_WIDTH,
            HUD_NORMAL_MIN_HEIGHT,
        )

    outer = getattr(window, "outer_layout", None)

    if outer is not None:
        if enabled:
            outer.setContentsMargins(
                0,
                0,
                0,
                0,
            )
            outer.setSpacing(0)
        else:
            outer.setContentsMargins(
                HUD_NORMAL_MARGIN,
                HUD_NORMAL_MARGIN,
                HUD_NORMAL_MARGIN,
                max(3, HUD_NORMAL_MARGIN - 2),
            )
            outer.setSpacing(
                HUD_NORMAL_SPACING
            )

    topbar = getattr(window, "topbar", None)

    if topbar is not None:
        topbar.setVisible(not enabled)

    project_label = getattr(
        window,
        "project_label",
        None,
    )

    if project_label is not None:
        project_label.setVisible(not enabled)

    bottom = getattr(window, "bottom_layout", None)

    if bottom is not None:
        bottom_widget = getattr(
            window,
            "bottom_widget",
            None,
        )

        if bottom_widget is not None:
            bottom_widget.setVisible(not enabled)

    tree = getattr(window, "tree", None)

    if tree is not None:
        tree.setHeaderHidden(enabled)

        if enabled:
            tree.setIndentation(0)
            tree.setRootIsDecorated(False)
            tree.setStyleSheet(f"""
                QTreeWidget {{
                    background: #000000;
                    color: #e8e9eb;
                    border: none;
                    outline: none;
                    padding: 0px;
                    margin: 0px;
                    font-size: 11px;
                }}

                QTreeWidget::item {{
                    height: {HUD_COMPACT_ROW_HEIGHT}px;
                    border: none;
                    padding: 0px;
                    margin: 0px;
                }}

                QTreeWidget::item:selected {{
                    background: #000000;
                    border: none;
                    outline: none;
                }}

                QTreeWidget::branch {{
                    background: #000000;
                    border: none;
                }}

                QScrollBar:vertical {{
                    width: 0px;
                    border: none;
                    background: #000000;
                }}
            """)
        else:
            tree.setIndentation(14)
            tree.setRootIsDecorated(True)
            tree.setStyleSheet("""
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

    if enabled:
        window.setStyleSheet("""
            QMainWindow {
                background: #000000;
                border: none;
            }

            QWidget {
                background: #000000;
                border: none;
            }
        """)
    else:
        window.setStyleSheet("")


def apply_window_behavior(window, settings=None) -> None:
    # Vakaa nykyinen Spine-käytös.
    # Stay on top -toggle on roadmapissa BLOCKED,
    # joten tässä pidetään aina päällä oleva peruskäytös.
    window.setWindowFlags(
        Qt.Window
        | Qt.WindowStaysOnTopHint
    )

    if settings is not None:
        apply_opacity(
            window,
            read_opacity(settings)
        )
