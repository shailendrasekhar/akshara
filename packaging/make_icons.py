"""
Generate the application icon set from the brand logo.

    uv run python packaging/make_icons.py

Crops the "A" mark out of src/akshara/resources/icons/logo.png, converts its
off-white background to transparency, and draws it on a rounded paper plate.
Writes hicolor PNGs for the desktop entry plus the in-app window icon.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "src/akshara/resources/icons/logo.png"
APP_ID = "io.github.shailendrasekhar.Akshara"
SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

# Region of the mark in the 2816x1536 source (excludes the wordmark).
CROP = (960, 160, 960, 860)  # x, y, w, h
PAPER = QColor("#f4ecd8")
INK = (0x1A, 0x14, 0x0E)


def mark_with_alpha() -> QImage:
    src = QImage(str(LOGO)).convertToFormat(QImage.Format.Format_RGBA8888)
    src = src.copy(*CROP)
    w, h = src.width(), src.height()
    ptr = src.bits()
    ptr.setsize(h * src.bytesPerLine())
    arr = np.frombuffer(ptr, np.uint8).reshape(h, src.bytesPerLine())[:, : w * 4].reshape(h, w, 4)
    lum = arr[..., :3].mean(axis=2)
    # Dark pixels become opaque ink; the light background fades out.
    alpha = np.clip((235 - lum) / (235 - 60), 0, 1) * 255
    out = np.empty((h, w, 4), np.uint8)
    out[..., 0], out[..., 1], out[..., 2] = INK
    out[..., 3] = alpha.astype(np.uint8)
    img = QImage(out.tobytes(), w, h, w * 4, QImage.Format.Format_RGBA8888)
    return img.copy()


def render(size: int, mark: QImage) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    inset = size * 0.04
    plate = QRectF(inset, inset, size - 2 * inset, size - 2 * inset)
    path = QPainterPath()
    path.addRoundedRect(plate, size * 0.2, size * 0.2)
    p.fillPath(path, PAPER)
    pad = size * 0.14
    target = plate.adjusted(pad, pad, -pad, -pad)
    scaled = mark.scaled(
        int(target.width()),
        int(target.height()),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    p.drawImage(
        QRectF(
            target.x() + (target.width() - scaled.width()) / 2,
            target.y() + (target.height() - scaled.height()) / 2,
            scaled.width(),
            scaled.height(),
        ),
        scaled,
    )
    p.end()
    return img


def main() -> None:
    _app = QGuiApplication([])
    mark = mark_with_alpha()
    for size in SIZES:
        out = ROOT / f"packaging/linux/icons/hicolor/{size}x{size}/apps/{APP_ID}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        render(size, mark).save(str(out))
    render(256, mark).save(str(ROOT / "src/akshara/resources/icons/akshara.png"))
    print(f"wrote {len(SIZES)} hicolor icons and the window icon")


if __name__ == "__main__":
    main()
