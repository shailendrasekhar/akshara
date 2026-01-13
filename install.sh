#!/bin/bash
# Installation script for AKSHARA

set -e

echo "📦 Installing AKSHARA..."

# Check if the executable exists
if [ ! -f "dist/akshara" ]; then
    echo "❌ Error: dist/akshara not found. Run ./build.sh first."
    exit 1
fi

# Install the executable
sudo cp dist/akshara /usr/local/bin/
echo "✅ Copied akshara to /usr/local/bin/"

# Install the desktop file
sudo cp akshara.desktop /usr/share/applications/akshara.desktop
echo "✅ Installed desktop entry"

# Install icon (if exists)
if [ -f "resources/icons/logo.png" ]; then
    sudo mkdir -p /usr/share/icons/hicolor/256x256/apps/
    sudo cp resources/icons/logo.png /usr/share/icons/hicolor/256x256/apps/akshara.png
    sudo gtk-update-icon-cache /usr/share/icons/hicolor/ 2>/dev/null || true
    echo "✅ Installed application icon"
fi

echo ""
echo "🎉 Installation complete!"
echo "You can now launch AKSHARA from your application menu or by running 'akshara' in terminal."
