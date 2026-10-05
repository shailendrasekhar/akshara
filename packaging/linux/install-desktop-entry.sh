#!/usr/bin/env bash
# Register Akshara with the desktop (menu entry, icon, "Open with" for PDFs)
# for the current user. Use after `uv tool install` so `akshara` is on PATH.
#
#   packaging/linux/install-desktop-entry.sh            # install
#   packaging/linux/install-desktop-entry.sh --uninstall
set -euo pipefail

APP_ID=io.github.shailendrasekhar.Akshara
here="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
data="${XDG_DATA_HOME:-$HOME/.local/share}"

if [[ "${1:-}" == "--uninstall" ]]; then
    rm -f "$data/applications/$APP_ID.desktop" "$data/metainfo/$APP_ID.metainfo.xml"
    find "$data/icons/hicolor" -name "$APP_ID.png" -delete 2>/dev/null || true
    echo "Removed Akshara desktop integration."
    exit 0
fi

if ! command -v akshara >/dev/null; then
    echo "warning: 'akshara' is not on PATH yet — run: uv tool install '.[tts]'" >&2
fi

install -Dm644 "$here/$APP_ID.desktop" "$data/applications/$APP_ID.desktop"
install -Dm644 "$here/$APP_ID.metainfo.xml" "$data/metainfo/$APP_ID.metainfo.xml"
(cd "$here/icons" && find hicolor -name "$APP_ID.png" -exec install -Dm644 {} "$data/icons/{}" \;)

update-desktop-database "$data/applications" 2>/dev/null || true
gtk-update-icon-cache -q -t "$data/icons/hicolor" 2>/dev/null || true
xdg-mime default "$APP_ID.desktop" application/pdf 2>/dev/null || true
echo "Installed Akshara desktop entry for $USER."
