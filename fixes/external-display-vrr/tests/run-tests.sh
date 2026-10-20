#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
build_dir=$(mktemp -d "${TMPDIR:-/tmp}/intel-pcon-host-tests.XXXXXX")
trap 'rm -rf "$build_dir"' EXIT HUP INT TERM
python3 "$script_dir/extract.py" "$build_dir/extracted_functions.h"
"${CC:-cc}" -std=c11 -Wall -Wextra -Werror -pedantic \
  -fsanitize=address,undefined -fno-omit-frame-pointer -g \
  -I "$build_dir" "$script_dir/test_intel_pcon.c" -o "$build_dir/test_intel_pcon"
"$build_dir/test_intel_pcon"
