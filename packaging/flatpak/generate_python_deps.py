"""
Generate the Flatpak module that installs Akshara's Python dependencies.

    uv run python packaging/flatpak/generate_python_deps.py

Versions are pinned from uv.lock (pip: latest) and wheels are resolved on
PyPI with their sha256, one wheel per architecture. PyQt6 itself comes from
the com.riverbankcomputing.PyQt.BaseApp base, so it is not listed here.
Re-run after `uv lock --upgrade`.
"""

from __future__ import annotations

import json
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_name("python3-deps.json")

# Runtime deps not provided by the PyQt BaseApp. pip is included so the
# in-app "Install neural voices" add-on can run inside the sandbox; hatchling
# and its dependencies are the build backend for `pip install .`.
PACKAGES = ["pymupdf", "pip", "hatchling", "packaging", "pathspec", "pluggy", "trove-classifiers"]
ARCHES = {"x86_64": "manylinux", "aarch64": "manylinux"}
PY_TAGS = ("cp312", "cp39-abi3", "cp310-abi3", "cp38-abi3", "py3-none-any")


def locked_versions() -> dict[str, str]:
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    return {p["name"].lower(): p["version"] for p in lock.get("package", [])}


def pypi_files(name: str, version: str | None) -> tuple[str, list[dict]]:
    url = (
        f"https://pypi.org/pypi/{name}/{version}/json"
        if version
        else f"https://pypi.org/pypi/{name}/json"
    )
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.load(r)
    return data["info"]["version"], data["urls"]


def pick(files: list[dict], arch: str | None) -> dict | None:
    wheels = [f for f in files if f["packagetype"] == "bdist_wheel"]
    for tag in PY_TAGS:
        for f in wheels:
            fn = f["filename"]
            if tag not in fn:
                continue
            if arch is None and fn.endswith("-none-any.whl"):
                return f
            if arch is not None and "manylinux" in fn and fn.endswith(f"_{arch}.whl"):
                return f
    return None


def main() -> None:
    locked = locked_versions()
    sources: list[dict] = []
    names: list[str] = []
    for name in PACKAGES:
        version, files = pypi_files(name, locked.get(name))
        names.append(f"{name}=={version}")
        universal = pick(files, None)
        if universal:
            sources.append(
                {"type": "file", "url": universal["url"], "sha256": universal["digests"]["sha256"]}
            )
            continue
        for arch in ARCHES:
            f = pick(files, arch)
            if f is None:
                raise SystemExit(f"no {arch} wheel for {name} {version}")
            sources.append(
                {
                    "type": "file",
                    "url": f["url"],
                    "sha256": f["digests"]["sha256"],
                    "only-arches": [arch],
                }
            )
    module = {
        "name": "python3-deps",
        "buildsystem": "simple",
        "build-commands": [
            'pip3 install --verbose --exists-action=i --no-index --find-links="file://${PWD}" '
            "--prefix=${FLATPAK_DEST} "
            + " ".join(f'"{n}"' for n in names)
            + " --no-build-isolation"
        ],
        "sources": sources,
    }
    OUT.write_text(json.dumps(module, indent=2) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {', '.join(names)}")


if __name__ == "__main__":
    main()
