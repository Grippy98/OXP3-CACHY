#!/usr/bin/env bash
# Per-game environment profile only; settings and game files are not edited.
# Optional --hdr selects the separately installed private Gamescope WSI layer.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$script_dir/gta-launch.py" "$@"
