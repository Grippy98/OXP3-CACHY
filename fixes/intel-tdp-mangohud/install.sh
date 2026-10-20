#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
usage() {
    echo "Usage: $0 tdp [--session-user NAME] | permissions | telemetry [BUILD-DIRECTORY]" >&2
    echo "telemetry builds and stages only; see telemetry/arch/README.md to install a built package." >&2
}
[ "$#" -gt 0 ] || { usage; exit 2; }
component=$1
shift
case "$component" in
    tdp) exec "$here/tdp/install.sh" "$@" ;;
    permissions) exec "$here/permissions/install.sh" "$@" ;;
    telemetry) exec "$here/telemetry/build.sh" "$@" ;;
    -h|--help) usage ;;
    *) usage; exit 2 ;;
esac
