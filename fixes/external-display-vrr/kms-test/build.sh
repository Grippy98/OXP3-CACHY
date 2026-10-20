#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
# Compile on the Linux test host (or a matching Linux development environment).
# Debian: libdrm-dev + pkg-config + C compiler. Arch/CachyOS: libdrm + pkgconf + gcc.
exec "${CC:-cc}" -std=c11 -O2 -Wall -Wextra -Werror \
    "$script_dir/oxp3-kms-vrr.c" $(pkg-config --cflags --libs libdrm) \
    -o "${1:-$script_dir/oxp3-kms-vrr}"
