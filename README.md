# AKSHARA

A Linux PDF reader built for focused reading — neural text-to-speech, Pomodoro timer, reading analytics, and a distraction-free interface.

## Features

- **PDF Viewing** — Continuous scroll rendering with lazy page loading, zoom controls, and fit-to-width on open
- **Neural TTS** — Natural-sounding speech via [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M); sentence-level highlighting follows along
- **Pomodoro Timer** — Right-side dock with focus/break cycles, session tracking, and preset durations (15 / 25 / 45 / 50 min)
- **Reading Analytics** — Session history, page dwell times, and per-book progress tracked in a local SQLite database
- **Library** — Left-side dock showing all previously opened documents with progress bars and quick re-open
- **Text Selection & Copy** — Click-drag to select text on the PDF; right-click to copy
- **Auto Theme** — Dark/light mode based on time of day (6 am–6 pm = light); togglable at any time
- **Text Size Toggle** — Cycles S / M / L across the entire UI (toolbar, menus, status bar, panels) with one button
- **Splash Animation** — Logo fades in centred, then travels to the top-left corner as the main window fades in maximized

## Installation

### Prerequisites

- Linux (tested on Ubuntu 22.04+)
- Anaconda or Miniconda
- NVIDIA GPU recommended for fast TTS (CPU fallback works)

### Setup

```bash
git clone https://github.com/yourusername/akshara.git
cd akshara

conda env create -f environment.yml
conda activate akshara

# Optional: install as a system app
sudo cp akshara-launcher.sh /usr/local/bin/akshara
sudo chmod +x /usr/local/bin/akshara
sudo cp akshara.desktop /usr/share/applications/
```

### Manual dependency install (without environment.yml)

```bash
conda create -n akshara python=3.11 -y
conda activate akshara
pip install -r requirements.txt
```

## Usage

```bash
conda activate akshara
python main.py

# Or open a PDF directly
python main.py path/to/book.pdf
```

If installed as a system app: launch from the applications menu or run `akshara`.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+O` | Open PDF |
| `← / →` | Previous / next page |
| `Space` | Play / pause TTS |
| `Escape` | Stop TTS |
| `Ctrl+R` | Read current page |
| `Ctrl+Shift+R` | Read selected text |
| `Ctrl+T` | Toggle dark / light mode |
| `Ctrl+Shift+T` | Cycle text size (S → M → L) |
| `Ctrl+Shift+A` | Open analytics |
| `L` | Show / hide library |

## Project Structure

```text
akshara/
├── main.py                  # Entry point
├── src/
│   ├── main_window.py       # Application window, toolbar, menus
│   ├── pdf_handler.py       # PDF document model (PyMuPDF)
│   ├── pdf_viewer.py        # Continuous-scroll viewer widget
│   ├── tts_engine.py        # Kokoro TTS wrapper
│   ├── splash_screen.py     # Animated splash with logo travel
│   ├── pomodoro.py          # Pomodoro timer panel
│   ├── analytics.py         # Analytics dialog
│   ├── library.py           # Library panel
│   ├── db.py                # SQLite store (sessions, page views, documents)
│   └── ui/
│       └── styles.py        # Stylesheet generator (dark/light, text size)
├── resources/
│   └── icons/               # logo.png
├── environment.yml
└── requirements.txt
```

## Dependencies

| Package     | Purpose                           |
| ----------- | --------------------------------- |
| PyQt6       | GUI framework                     |
| PyMuPDF     | PDF rendering and text extraction |
| kokoro      | Kokoro-82M neural TTS             |
| torch       | PyTorch (TTS backend)             |
| numpy       | Audio array processing            |
| simpleaudio | PCM audio playback                |

## Uninstall

```bash
sudo rm /usr/local/bin/akshara
sudo rm /usr/share/applications/akshara.desktop
conda env remove -n akshara
```

## License

MIT
