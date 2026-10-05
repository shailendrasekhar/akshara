#!/usr/bin/env bash
# Build a portable AppImage of Akshara.
#
#   packaging/appimage/build.sh             # lightweight: system speech only (~120 MB)
#   packaging/appimage/build.sh --with-tts  # bundles Kokoro neural TTS + CPU PyTorch (large)
#
# Requires: uv, network access. Output lands in dist/.
# The Kokoro voice model itself is not bundled; it downloads (~330 MB) from
# Hugging Face the first time you press Read, then works offline.
set -euo pipefail

PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
with_tts=0
[[ "${1:-}" == "--with-tts" ]] && with_tts=1

root="$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)"
cd "$root"
version="$(uv version --short 2>/dev/null || grep -m1 '^version' pyproject.toml | cut -d'"' -f2)"
app_id=io.github.shailendrasekhar.Akshara
recipe="build/appimage/akshara"

rm -rf build/appimage
mkdir -p "$recipe" dist

echo "==> Building wheel"
uv build --wheel --out-dir build/appimage/wheel >/dev/null
wheel="$(ls "$root"/build/appimage/wheel/akshara-*.whl)"

echo "==> Writing recipe"
if (( with_tts )); then
    {
        echo "--extra-index-url https://download.pytorch.org/whl/cpu"
        echo "akshara[tts] @ file://$wheel"
    } > "$recipe/requirements.txt"
    suffix=""
else
    echo "akshara @ file://$wheel" > "$recipe/requirements.txt"
    suffix="-lite"
fi

cat > "$recipe/entrypoint.sh" <<'SH'
{{ python-executable }} -s -m akshara "$@"
SH

sed -e "s/^Icon=.*/Icon=akshara/" -e "s/^Exec=.*/Exec=akshara %f/" \
    "packaging/linux/$app_id.desktop" > "$recipe/akshara.desktop"
cp "packaging/linux/icons/hicolor/256x256/apps/$app_id.png" "$recipe/akshara.png"
sed -e "s#<launchable type=\"desktop-id\">$app_id.desktop</launchable>#<launchable type=\"desktop-id\">akshara.desktop</launchable>#" \
    -e "s#<id>$app_id</id>#<id>akshara</id>#" \
    "packaging/linux/$app_id.metainfo.xml" > "$recipe/akshara.appdata.xml"

echo "==> Building AppImage (Python $PYTHON_VERSION)"
(cd build/appimage && uvx python-appimage build app -p "$PYTHON_VERSION" akshara)

out="dist/Akshara${suffix}-${version}-$(uname -m).AppImage"
mv build/appimage/akshara-*.AppImage "$out" 2>/dev/null || mv build/appimage/*.AppImage "$out"
chmod +x "$out"
echo "==> $out ($(du -h "$out" | cut -f1))"
