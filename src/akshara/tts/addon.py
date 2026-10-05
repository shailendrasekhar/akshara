"""
Neural-voice add-on: install Kokoro + CPU PyTorch into the user's data dir.

Lightweight builds (Flatpak, the "lite" AppImage, `uv tool install akshara`
without the `tts` extra) ship without PyTorch. Instead of a separate build,
the reader can install the neural engine on demand; the packages land in
``$XDG_DATA_HOME/akshara/tts-addon/py3.X`` and are put on ``sys.path`` at
startup by :func:`activate`.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import shutil
import sys
from pathlib import Path

PACKAGES = ["kokoro>=0.9.4", "sounddevice>=0.4.6", "numpy>=1.24"]
TORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"


def addon_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    tag = f"py{sys.version_info.major}.{sys.version_info.minor}"
    return Path(base) / "akshara" / "tts-addon" / tag


def is_installed() -> bool:
    return (addon_dir() / ".complete").exists()


def activate() -> bool:
    """Put an installed add-on on sys.path. Safe to call more than once."""
    d = addon_dir()
    if not is_installed():
        return False
    path = str(d)
    if path not in sys.path:
        sys.path.append(path)  # after the app's own packages: never shadow them
        importlib.invalidate_caches()
    return True


def install_command() -> list[str] | None:
    """The command that installs the add-on, or None if no installer is available."""
    target = str(addon_dir())
    common = ["--target", target, "--upgrade", "--extra-index-url", TORCH_CPU_INDEX, *PACKAGES]
    if importlib.util.find_spec("pip") is not None:
        return [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-input",
            "--disable-pip-version-check",
            *common,
        ]
    uv = shutil.which("uv")
    if uv:
        return [uv, "pip", "install", "--python", sys.executable, *common]
    return None


def mark_complete() -> None:
    d = addon_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / ".complete").write_text("ok\n")


def uninstall() -> None:
    shutil.rmtree(addon_dir(), ignore_errors=True)
