# AKSHARA 📖🔊

A modern Linux desktop PDF reader with text-to-speech functionality.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![PyQt6](https://img.shields.io/badge/PyQt6-6.6+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

- 📄 **PDF Viewing** - High-quality PDF rendering with zoom controls
- 🔊 **Text-to-Speech** - Have your PDFs read aloud with adjustable speed
- 🎮 **Playback Controls** - Play, pause, stop, and speed adjustment (0.5x - 2.0x)
- 📑 **Page Navigation** - Easy navigation with keyboard shortcuts
- 🎨 **Auto Theme** - Automatically switches between light/dark mode based on time of day
- ✨ **Animated Splash** - Beautiful blur-reveal animation on startup
- 📦 **Portable** - Can be packaged as a standalone executable

## Installation

### Prerequisites

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y libxcb-cursor0 espeak-ng

# Install Anaconda/Miniconda if not already installed
# https://docs.conda.io/en/latest/miniconda.html
```

### Option 1: Quick Install (Standalone Executable)

```bash
# Clone the repository
git clone https://github.com/yourusername/Talk2me.git
cd Talk2me

# Create and activate conda environment
conda create -n talk2me python=3.11 -y
conda activate talk2me

# Install Python dependencies
pip install -r requirements.txt

# Build the standalone executable
./build.sh

# Install system-wide
sudo ./install.sh
```

After installation, you can:
- Launch **AKSHARA** from your application menu
- Run `akshara` from any terminal
- Right-click any PDF → Open With → AKSHARA

### Option 2: Run from Source (Development)

```bash
# Clone the repository
git clone https://github.com/shailendrasekhar/akshara.git
cd akshara

# Create and activate conda environment
conda create -n akshara python=3.11 -y
conda activate akshara

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Uninstall

```bash
sudo rm /usr/local/bin/akshara
sudo rm /usr/share/applications/akshara.desktop
sudo rm /usr/share/icons/hicolor/256x256/apps/akshara.png
```

## Usage

### Opening a PDF

- Click **📂 Open** button or use `Ctrl+O`
- Drag and drop a PDF file onto the window
- Pass a PDF file as command line argument: `akshara document.pdf`
- Right-click a PDF file → Open With → AKSHARA

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+O` | Open PDF file |
| `←` / `→` | Previous / Next page |
| `Space` | Play / Pause reading |
| `Escape` | Stop reading |
| `Ctrl++` / `Ctrl+-` | Zoom in / out |
| `Ctrl+T` | Toggle light/dark theme |

### Text-to-Speech Controls

- **▶ Read Page** - Start reading the entire current page
- **📖 Read Selection** - Read only selected text
- **⏸ Pause** - Pause/resume reading
- **⏹ Stop** - Stop reading completely
- **Speed Slider** - Adjust reading speed from 0.5x to 2.0x

### Theme

The app automatically selects the theme based on local time:
- ☀️ **Light mode**: 6:00 AM – 5:59 PM
- 🌙 **Dark mode**: 6:00 PM – 5:59 AM

You can manually toggle the theme with the ☀️/🌙 button or `Ctrl+T`.

## Project Structure

```
akshara/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── environment.yml         # Conda environment spec
├── build.sh               # Build script for executable
├── install.sh             # System installation script
├── akshara.desktop        # Linux desktop entry
├── src/
│   ├── __init__.py
│   ├── main_window.py     # Main application window
│   ├── pdf_handler.py     # PDF loading & text extraction
│   ├── pdf_viewer.py      # PDF display with text selection
│   ├── tts_engine.py      # Text-to-speech engine
│   ├── splash_screen.py   # Animated splash screen
│   └── ui/
│       ├── __init__.py
│       └── styles.py      # Light/dark theme styles
└── resources/
    └── icons/             # Application icons
```

## Tech Stack

- **[PyQt6](https://www.riverbankcomputing.com/software/pyqt/)** - Modern GUI framework
- **[PyMuPDF](https://pymupdf.readthedocs.io/)** - PDF processing and rendering
- **[espeak-ng](https://github.com/espeak-ng/espeak-ng)** - Offline text-to-speech
- **[PyInstaller](https://pyinstaller.org/)** - Standalone executable packaging

## Troubleshooting

### No sound / TTS not working
```bash
# Ensure espeak-ng is installed
sudo apt-get install espeak-ng

# Test it works
espeak-ng "Hello world"
```

### App won't launch after install
```bash
# Check if the executable exists
which akshara

# Try running directly with verbose output
/usr/local/bin/akshara
```

### Missing Qt libraries
```bash
sudo apt-get install libxcb-cursor0 libxcb-xinerama0
```

## License

MIT License - feel free to use and modify!

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
