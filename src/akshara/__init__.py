"""AKSHARA — a focused PDF reader with neural text-to-speech."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("akshara")
except PackageNotFoundError:  # running from a source tree without install
    __version__ = "0.0.0+local"

APP_NAME = "AKSHARA"
APP_ID = "io.github.shailendrasekhar.Akshara"
