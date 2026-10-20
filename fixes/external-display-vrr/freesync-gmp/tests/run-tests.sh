#!/bin/sh
set -eu
here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/oxp3-freesync-tests.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
python3 "$here/extract.py" "$work/extracted.c"
"${CC:-clang}" -std=gnu11 -Wall -Wextra -Werror -Wno-unused-function -g -O1 \
  -fsanitize=address,undefined -fno-omit-frame-pointer \
  -I"$here" -I"$work" "$here/test_freesync.c" -o "$work/test-freesync"
"$work/test-freesync"
