#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")/.." &&
    pwd
)"

APP_DIR="$HOME/.local/share/spine-hud-v0.2-test"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
STATE_DIR="$HOME/.local/state/spine-hud-v0.2-test"

LAUNCHER="$BIN_DIR/spine-hud-v0.2-test"
DESKTOP_FILE="$DESKTOP_DIR/spine-hud-v0.2-test.desktop"

echo "Installing Spine HUD v0.2 Test..."

mkdir -p \
    "$APP_DIR" \
    "$BIN_DIR" \
    "$DESKTOP_DIR" \
    "$STATE_DIR"

# Päivitä sovellustiedostot, mutta älä kopioi Gitiä tai DEV-venviä.
rm -rf "$APP_DIR/src" "$APP_DIR/docs" "$APP_DIR/packaging"

mkdir -p "$APP_DIR"

tar \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    -cf - \
    -C "$SOURCE_DIR" . \
| tar -xf - -C "$APP_DIR"

python3 -m venv "$APP_DIR/.venv"

"$APP_DIR/.venv/bin/python" -m pip install \
    --disable-pip-version-check \
    -r "$APP_DIR/requirements.txt"

cat > "$LAUNCHER" <<'LAUNCHER'
#!/usr/bin/env bash

APP_DIR="$HOME/.local/share/spine-hud-v0.2-test"
STATE_DIR="$HOME/.local/state/spine-hud-v0.2-test"
LOG_FILE="$STATE_DIR/spine.log"

mkdir -p "$STATE_DIR"

export SPINE_ENV=dev
export PYTHONPATH="$APP_DIR/src"

# Fedora/Wayland-testissä xcb/XWayland on ollut vakaa polku.
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"

exec \
    "$APP_DIR/.venv/bin/python" \
    "$APP_DIR/src/main.py" \
    >>"$LOG_FILE" 2>&1
LAUNCHER

chmod +x "$LAUNCHER"

cat > "$DESKTOP_FILE" <<EOF_DESKTOP
[Desktop Entry]
Type=Application
Name=Spine HUD v0.2 Test
Comment=Spine HUD v0.2 test release
Exec=$LAUNCHER
Terminal=false
Categories=Development;
StartupNotify=false
EOF_DESKTOP

chmod 644 "$DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

echo
echo "Installed:"
echo "  $APP_DIR"
echo
echo "Launcher:"
echo "  $LAUNCHER"
echo
echo "Desktop entry:"
echo "  $DESKTOP_FILE"
echo
echo "Log:"
echo "  $STATE_DIR/spine.log"
echo
echo "v0.1 PRODUCT settings are untouched."
