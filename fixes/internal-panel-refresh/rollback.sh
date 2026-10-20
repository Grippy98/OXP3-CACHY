#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ $# == 0 ]] || { printf 'Usage: %s (run as the Gaming Mode user)\n' "$0" >&2; exit 2; }
[[ $EUID != 0 ]] || { printf 'Run as the Gaming Mode user, without sudo.\n' >&2; exit 1; }
exec python3 "$here/profile/manage-profile.py" rollback
