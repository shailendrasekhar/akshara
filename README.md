# AKSHARA 📖🔊

A Linux PDF reader with high-quality neural text-to-speech powered by [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M).

## Features

- 📄 **PDF Viewing** — High-quality rendering with zoom controls
- 🔊 **Neural TTS** — Natural-sounding speech using Kokoro-82M (GPU accelerated)
- 🎯 **Sentence Highlighting** — Follows along as text is read
- 🎮 **Playback Controls** — Play, pause, stop, speed adjustment (0.5x–2.0x)
- 🎨 **Auto Theme** — Light/dark mode based on time of day

## Installation

### Prerequisites

- NVIDIA GPU (recommended for fast TTS)
- Anaconda/Miniconda

### Setup

```bash
git clone https://github.com/yourusername/Talk2me.git
cd Talk2me

# Create conda environment
conda create -n talk2me python=3.11 -y
conda activate talk2me

# Install dependencies
pip install -r requirements.txt

# Install the app
sudo cp akshara-launcher.sh /usr/local/bin/akshara
sudo cp akshara.desktop /usr/share/applications/
```

## Usage

Launch from the applications menu or run:

```bash
akshara
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+O` | Open PDF |
| `←` / `→` | Previous / Next page |
| `Space` | Play / Pause |
| `Escape` | Stop |

## Dependencies

- PyQt6 — GUI framework
- PyMuPDF — PDF rendering
- Kokoro — Neural TTS model
- PyTorch — Deep learning backend
- simpleaudio — Audio playback

## Uninstall

```bash
sudo rm /usr/local/bin/akshara
sudo rm /usr/share/applications/akshara.desktop
```

## License

MIT
