# AKSHARA

A calm Linux PDF reader built for deep reading: natural neural text-to-speech
with sentence highlighting, highlights and notes, a Pomodoro timer, and
private reading analytics. Everything stays on your computer.

![Akshara in dark mode](docs/screenshots/reader-dark.png)

## Features

**Reading**
- Smooth continuous scrolling with HiDPI-sharp rendering and a page cache
- Fit width, fit page, or a remembered per-book zoom; Ctrl+scroll zooms at the cursor
- Dark, light and sepia themes, following the desktop setting, the time of day, or your choice.
  Pages are recoloured to match while photos and figures keep their colours
- Table of contents, clickable links, whole-document search (Ctrl+F)
- Reopens every book at the page you left; password-protected PDFs supported
- Focus mode (Ctrl+Shift+F) hides everything but the page

**Read aloud**
- Neural voices via [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M), with the sentence being
  spoken highlighted and followed on screen
- Keeps reading onto the next page, skipping blank pages; read a selection or "read aloud from here"
- Pause/stop, adjustable speed, 13 voices (US/UK)
- Falls back to the system speech engine (speech-dispatcher) when neural voices aren't installed

**Notes**
- Word-level text selection; highlights with optional notes; bookmarks with notes
- Export a book's highlights and bookmarks as Markdown

**Focus and analytics**
- Pomodoro timer with configurable lengths, optional auto-start breaks and desktop notifications
- Analytics: 28-day heatmap, last-7-days chart, streaks, session lengths, time per book,
  pages read and words heard, CSV export

| Sepia | Analytics |
|---|---|
| ![Sepia theme](docs/screenshots/reader-sepia.png) | ![Analytics](docs/screenshots/analytics.png) |

## Run it

### Requirements

- Linux with a graphical session (X11 or Wayland)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Python 3.11 or newer (uv downloads one if needed)
- For neural voices: `libportaudio2` (audio output), and 1–3 GB of free disk for PyTorch and the model.
  An NVIDIA GPU makes synthesis faster, but the CPU works
- Optional, for the system-voice fallback: `speech-dispatcher`

On Debian/Ubuntu:

```bash
sudo apt install libportaudio2 speech-dispatcher
```

### From a checkout (quickest)

```bash
git clone https://github.com/shailendrasekhar/akshara.git
cd akshara

uv run akshara                      # reader + system voices only (small download)
uv run --extra tts akshara          # with neural voices (downloads PyTorch, ~1–3 GB)
uv run --extra tts akshara path/to/book.pdf --no-splash
```

On Linux, PyPI's PyTorch build includes CUDA libraries, which is why the `tts` extra is large.

### Install as a command

```bash
uv tool install ".[tts]"                     # or just "." for the lightweight reader
akshara --version
packaging/linux/install-desktop-entry.sh     # optional: menu entry, icon, "Open with" for PDFs
```

To undo: `packaging/linux/install-desktop-entry.sh --uninstall` and `uv tool uninstall akshara`.

### Neural voices for a lightweight install

Any build without the `tts` extra can add neural voices later from
**Edit ▸ Preferences ▸ Read aloud ▸ Install neural voices…**. This installs Kokoro and a CPU build
of PyTorch (about 1 GB) into `~/.local/share/akshara/tts-addon/`. It uses `pip`, or `uv` if the
Python has no pip. After it finishes, choose **Neural (Kokoro)** as the engine.

### AppImage and Flatpak

No release has been published yet. The packaging is in `packaging/`, and pushing a `v*` tag runs
the release workflow, which attaches the wheel, two AppImages and a Flatpak bundle to a GitHub
release. To build them yourself, see [Building packages](#building-packages).

## Verify your setup

Work through these after installing. Each step says what you should see.

**1. The app starts**

```bash
uv run akshara --version            # prints: akshara 0.2.0
uv run akshara --no-splash
```

The welcome screen appears. **Help ▸ About** lists each speech engine and says whether it is
available, or why it isn't.

**2. Neural voices (Kokoro)**

First check speech outside the GUI. This downloads the model (~330 MB, from Hugging Face) on the
first run and plays one sentence:

```bash
uv run --extra tts python -c "
import numpy as np, sounddevice as sd
from kokoro import KPipeline
p = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')
audio = np.concatenate([r.audio.numpy() for r in p('Hello from Akshara.', voice='af_heart')])
sd.play(audio, 24000); sd.wait()"
```

GPU check (optional): `uv run --extra tts python -c "import torch; print(torch.cuda.is_available())"`.

Then in the app (`uv run --extra tts akshara`), open a PDF with real text (not a scan) and press
**Space**:
- The status bar shows "Loading voice…" briefly, then "Reading aloud".
- Each sentence is highlighted as it is spoken, and the view follows it.
- **Space** pauses and resumes; **Esc** stops at once.
- With **Speech ▸ Continue onto Next Page** checked, reading carries on to the next page.
- Right-click a word ▸ **Read aloud from here** starts at that word.

Common problems:
- `OSError: PortAudio library not found` from the snippet, or "Audio output error: PortAudio library
  not found" in the app's status bar, means `libportaudio2` is missing.
- "Neural (Kokoro) (unavailable)" in Preferences means the `tts` extra or the add-on isn't
  installed.

**3. System voices (fallback)**

`spd-say "hello"` should speak. Then choose **System (speech-dispatcher)** under
**Preferences ▸ Read aloud** and press Space on a page.

**4. Desktop notifications**

`notify-send test` should show a notification. In the app, press **Begin** on the Pomodoro panel,
then **Skip**: a "Short Break" notification appears. Without a notification service, the app
beeps instead.

**5. Your data**

Close the app and reopen it. Your theme, window layout, zoom mode and speech speed are restored,
and the last book reopens at the page you left (controlled by **Preferences ▸ General**).

**6. Test suite**

```bash
uv sync
uv run pytest
```

The tests run headless and need no display or audio. On minimal systems, install Qt's runtime
libraries first: `sudo apt install libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3`.

## Building packages

### AppImage

Needs `uv` and network access to PyPI and GitHub; `python-appimage` downloads its base image
from GitHub.

```bash
packaging/appimage/build.sh              # dist/Akshara-lite-0.2.0-x86_64.AppImage (system voices)
packaging/appimage/build.sh --with-tts   # dist/Akshara-0.2.0-x86_64.AppImage (CPU PyTorch + Kokoro)
```

Check the result:

```bash
./dist/Akshara-lite-0.2.0-x86_64.AppImage --version
./dist/Akshara-lite-0.2.0-x86_64.AppImage path/to/book.pdf
```

If it fails with a FUSE error, install `libfuse2` or run it with `APPIMAGE_EXTRACT_AND_RUN=1`.
Then work through [Verify your setup](#verify-your-setup) with the AppImage in place of `uv run akshara`.

### Flatpak

```bash
sudo apt install flatpak flatpak-builder
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub org.kde.Sdk//6.9 org.kde.Platform//6.9 com.riverbankcomputing.PyQt.BaseApp//6.9

flatpak-builder --user --install --force-clean build-dir \
    packaging/flatpak/io.github.shailendrasekhar.Akshara.yml
flatpak run io.github.shailendrasekhar.Akshara
```

To make a single-file bundle instead of installing:

```bash
flatpak-builder --repo=repo --force-clean build-dir packaging/flatpak/io.github.shailendrasekhar.Akshara.yml
flatpak build-bundle repo Akshara.flatpak io.github.shailendrasekhar.Akshara
```

Notes:
- **PortAudio checksum.** The PortAudio `sha256` in the manifest has not been verified against
  the download yet. If flatpak-builder reports a checksum mismatch, compute the real value and
  put it in the manifest:
  `curl -sL http://files.portaudio.com/archives/pa_stable_v190700_20210406.tgz | sha256sum`.
- **Runtime version.** The manifest targets KDE runtime / PyQt BaseApp **6.9**. If you change it,
  check the Python version (the wheels are for CPython 3.12 / abi3) and regenerate the deps.
- **Python dependencies.** These are pinned in `packaging/flatpak/python3-deps.json`. Regenerate
  them after `uv lock --upgrade` with `uv run python packaging/flatpak/generate_python_deps.py`.
- **Voices.** The Flatpak ships system voices only; add neural voices from Preferences. The
  manifest grants network access for that and for the model download.

### Validate the desktop metadata

```bash
desktop-file-validate packaging/linux/*.desktop
appstreamcli validate --no-net packaging/linux/*.metainfo.xml
```

### Releasing

Bump `version` in `pyproject.toml` and the `<release>` entry in
`packaging/linux/io.github.shailendrasekhar.Akshara.metainfo.xml`, then:

```bash
git tag v0.2.0 && git push origin v0.2.0
```

`.github/workflows/release.yml` builds the wheel, both AppImages and the Flatpak bundle and
publishes them as a GitHub release. It can also be started manually from the Actions tab
(`workflow_dispatch`); that builds the artifacts without publishing a release.

## Keyboard shortcuts

| Key | Action |
|---|---|
| `Ctrl+O` / `Ctrl+W` | Open / close document |
| `←` `→`, `Ctrl+Home` `Ctrl+End`, `Ctrl+G` | Previous/next page, first/last, go to page |
| `Space` | Read aloud / pause / resume |
| `Ctrl+R` / `Ctrl+Shift+R` | Read current page / read selection |
| `Esc` | Close find bar, stop reading, or leave focus mode |
| `Ctrl+[` `Ctrl+]` | Slower / faster speech |
| `Ctrl+F`, `F3` / `Shift+F3` | Find, next / previous match |
| `Ctrl+B`, `Ctrl+Alt+↑/↓` | Toggle bookmark, jump between bookmarks |
| `Ctrl+C`, `Ctrl+A` | Copy selection, select all on page |
| `Ctrl++` `Ctrl+-` `Ctrl+0`, `Ctrl+1` `Ctrl+2` | Zoom, actual size, fit width, fit page |
| `Ctrl+T`, `Ctrl+Shift+T` | Cycle theme, cycle interface text size |
| `F9`, `F10`, `F11`, `Ctrl+Shift+F` | Sidebar, Pomodoro panel, full screen, focus mode |
| `Ctrl+P`, `Ctrl+Shift+A`, `Ctrl+,` | Start/pause Pomodoro, analytics, preferences |
| `F1` | All shortcuts |

Right-click the page for copy, highlight, read-from-here and bookmark actions.

## Where data lives

| What | Path |
|---|---|
| Library, sessions, bookmarks, highlights (SQLite) | `~/.local/share/akshara/akshara.db` (override: `AKSHARA_DB`) |
| Preferences | `~/.config/akshara/settings.ini` (override: `AKSHARA_CONFIG`) |
| Neural-voice add-on | `~/.local/share/akshara/tts-addon/` |
| Voice model cache | `~/.cache/huggingface/` |

Inside the Flatpak these live under `~/.var/app/io.github.shailendrasekhar.Akshara/`. A database
from an older version upgrades itself in place on first launch. To try the app without touching
your real data, point it at temporary files:

```bash
AKSHARA_DB=/tmp/a.db AKSHARA_CONFIG=/tmp/a.ini uv run akshara
```

## Development

```bash
uv sync                                   # app + dev tools (add --extra tts for neural voices)
uv run akshara --no-splash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest --cov
```

CI (`.github/workflows/ci.yml`) runs lint, format, type checks and tests on Python 3.11–3.13, and
validates the desktop entry and metainfo.

Project layout:

```text
src/akshara/
├── app.py              entry point (CLI, splash, session restore)
├── main_window.py      window, actions, menus, toolbar; wires everything together
├── pdf_viewer.py       continuous-scroll viewer: rendering queue, overlays, selection, links
├── render.py           page rasterisation, theme recolouring, LRU image cache
├── pdf_handler.py      document model: metadata, geometry, text, links, outline, passwords
├── textmap.py          word-level page text ↔ rectangles, sentences, search
├── tts/                speech engines (Kokoro, system), read-aloud controller, voice add-on
├── db.py               SQLite store with versioned migrations
├── settings.py         typed QSettings preferences
├── findbar.py          find bar + incremental search
├── sidebar.py          contents, bookmarks, notes panels
├── library.py          library panel
├── pomodoro.py         Pomodoro panel
├── analytics.py        analytics dialog
└── ui/theme.py         palettes and stylesheet
packaging/
├── appimage/build.sh   AppImage (lite or --with-tts)
├── flatpak/            Flatpak manifest + generated Python deps
├── linux/              desktop entry, AppStream metainfo, icons, user install script
└── make_icons.py       regenerates the icon set from the logo
```

## License

MIT
