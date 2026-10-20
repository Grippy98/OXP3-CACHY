#!/bin/sh
set -eu
test_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
picoefi_dir=${PICOEFI_INCLUDE:-"$test_dir/../reference-headers/picoefi/inc"}
output=$(mktemp -d)
trap 'rm -rf "$output"' EXIT HUP INT TERM
${CC:-cc} -std=gnu11 -Wall -Wextra -Werror -DUEFI \
    -I"$test_dir/../limine/common" -I"$picoefi_dir" \
    "$test_dir/gamepad_firmware_test.c" \
    "$test_dir/../limine/common/drivers/gamepad_state.c" \
    -o "$output/gamepad-firmware-test"
"$output/gamepad-firmware-test"
