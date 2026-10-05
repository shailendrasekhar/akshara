#!/usr/bin/env bash
# Run AKSHARA from a source checkout using uv.
# Usage: ./akshara-launcher.sh [file.pdf]
set -euo pipefail
here="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
exec uv run --project "$here" --extra tts akshara "$@"
