import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEV_MARKER = PROJECT_ROOT / ".spine-dev"

_env = os.environ.get("SPINE_ENV", "").strip().lower()

if _env:
    IS_DEV = _env == "dev"
else:
    IS_DEV = DEV_MARKER.exists()

SETTINGS_APP = "SpineHUD-DEV" if IS_DEV else "SpineHUD"

CONFIG_DIR = (
    Path.home()
    / ".config"
    / ("spine-dev" if IS_DEV else "spine")
)

LOCK_NAME = (
    "spine-hud-dev.lock"
    if IS_DEV
    else "spine-hud.lock"
)

WINDOW_SUFFIX = " [DEV]" if IS_DEV else ""


# SPINE_V02_RELEASE_RUNTIME
# Installed v0.2 releases must not share DEV settings or the DEV lock.
_RUNTIME_KIND = os.environ.get("SPINE_ENV", "").strip().lower()
IS_RELEASE = _RUNTIME_KIND in {"release", "test"}

if IS_RELEASE:
    IS_DEV = False
    SETTINGS_APP = "SpineHUD-v0.2"
    LOCK_NAME = "spine-hud-v0.2.lock"
