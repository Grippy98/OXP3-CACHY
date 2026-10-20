#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
source_dir=${1:-"$here/../patched-source/src"}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
"${CXX:-c++}" -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined \
  -fno-omit-frame-pointer -I "$source_dir" "$here/telemetry_test.cpp" -o "$work/telemetry-test"
"$work/telemetry-test"
