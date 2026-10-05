"""Bundled static assets (icons, images)."""

from __future__ import annotations

from pathlib import Path

RESOURCE_DIR = Path(__file__).resolve().parent


def resource_path(*parts: str) -> Path:
    """Return the absolute path of a bundled resource."""
    return RESOURCE_DIR.joinpath(*parts)
