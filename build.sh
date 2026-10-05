#!/bin/bash
# Build script for AKSHARA - Creates a standalone Linux application

set -e

echo "🔧 Building AKSHARA standalone application..."

# Ensure we're in the project directory
cd "$(dirname "$0")"

# Clean previous builds
rm -rf build dist

# Build with PyInstaller
uv run --group build pyinstaller \
    --name="akshara" \
    --onefile \
    --windowed \
    --add-data="src/akshara/resources:akshara/resources" \
    src/akshara/__main__.py

echo "✅ Build complete!"
echo "📦 Executable: dist/akshara"
echo ""
echo "To install system-wide, run:"
echo "  sudo ./install.sh"
