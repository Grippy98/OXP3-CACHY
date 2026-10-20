#!/usr/bin/env bash
# Profile only: no kernel, boot, compositor executable or running session changes.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ ${1:-} == --check ]]; then
    command -v python3 >/dev/null
    [[ -r "$here/profile/onexplayer3-sdc-refresh.lua" ]]
    printf 'panel-refresh: profile-only adapter; Python 3 available. Full accepted kernel/runtime is manual (see README).\n'
    exit 0
fi
[[ $# == 0 ]] || { printf 'Usage: %s [--check] (run as the Gaming Mode user)\n' "$0" >&2; exit 2; }
[[ $EUID != 0 ]] || { printf 'Run this profile-only installer as the Gaming Mode user, without sudo.\n' >&2; exit 1; }
exec python3 "$here/profile/manage-profile.py" install
