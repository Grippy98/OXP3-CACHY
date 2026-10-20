#!/usr/bin/env bash
set -euo pipefail
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
command -v python3 >/dev/null || { echo 'Python 3 is required (sudo pacman -S python).' >&2; exit 1; }
exec python3 "$root/scripts/installer.py" "$@"
