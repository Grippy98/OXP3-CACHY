#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ ${1:-} == --check ]]; then
    shift
    exec python3 "$here/workaround/manage-edid.py" check "$@"
fi
exec python3 "$here/workaround/manage-edid.py" install "$@"
