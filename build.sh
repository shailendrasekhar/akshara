#!/bin/bash
# Build script for AKSHARA - Creates a standalone Linux application

set -e

echo "🔧 Building AKSHARA standalone application..."

# Ensure we're in the project directory
cd "$(dirname "$0")"

# Activate conda environment
source ~/anaconda3/etc/profile.d/conda.sh
conda activate talk2me

# Clean previous builds
rm -rf build dist

# Build with PyInstaller
pyinstaller \
    --name="akshara" \
    --onefile \
    --windowed \
    --add-data="resources:resources" \
    main.py

echo "✅ Build complete!"
echo "📦 Executable: dist/akshara"
echo ""
echo "To install system-wide, run:"
echo "  sudo ./install.sh"
