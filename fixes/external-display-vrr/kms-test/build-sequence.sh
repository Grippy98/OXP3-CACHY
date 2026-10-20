#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "${CC:-cc}" -std=c11 -O2 -Wall -Wextra -Werror \
    "$script_dir/crtc-sequence.c" $(pkg-config --cflags --libs libdrm) \
    -o "${1:-$script_dir/crtc-sequence}"
