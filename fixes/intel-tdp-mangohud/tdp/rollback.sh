#!/bin/sh
set -eu
[ -x /usr/bin/python3 ] || { echo "Required: /usr/bin/python3" >&2; exit 1; }
exec /usr/bin/python3 "$(dirname "$0")/deploy.py" rollback "$@"
