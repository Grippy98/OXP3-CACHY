#!/bin/sh
set -eu
test_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
output=$(mktemp -d)
trap 'rm -rf "$output"' EXIT HUP INT TERM
${CC:-cc} -std=c99 -Wall -Wextra -Werror -pedantic \
    -I"$test_dir/../limine/common" \
    "$test_dir/gamepad_state_test.c" \
    "$test_dir/../limine/common/drivers/gamepad_state.c" \
    -o "$output/gamepad-state-test"
"$output/gamepad-state-test"
