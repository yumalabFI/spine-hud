#!/usr/bin/env bash
set -euo pipefail

rm -rf \
    "$HOME/.local/share/spine-hud-v0.2-test"

rm -f \
    "$HOME/.local/bin/spine-hud-v0.2-test" \
    "$HOME/.local/share/applications/spine-hud-v0.2-test.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database \
        "$HOME/.local/share/applications" \
        >/dev/null 2>&1 || true
fi

echo "Spine HUD v0.2 Test removed."
echo "Logs/settings were left intact."
