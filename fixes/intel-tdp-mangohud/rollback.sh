#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
[ "$#" -eq 1 ] || { echo "Usage: $0 tdp|permissions" >&2; exit 2; }
case "$1" in
    tdp) exec "$here/tdp/rollback.sh" ;;
    permissions) exec "$here/permissions/rollback.sh" ;;
    *) echo "Usage: $0 tdp|permissions" >&2; exit 2 ;;
esac
