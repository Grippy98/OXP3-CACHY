#!/usr/bin/env bash
set -euo pipefail

[[ $# == 1 ]] || { printf 'Usage: bash check-patch.sh CLEAN_LIMINE_SOURCE_DIRECTORY\n' >&2; exit 2; }
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source_dir=$(cd -- "$1" && pwd)
patch=$here/limine-gamepad-tested-v12.9.0.patch
expected=c569a94dd9a0a16c56eefa425263b5be717e77140ef37c7ee18828eeaf2f344f
[[ -f $source_dir/common/menu.c && -f $source_dir/CONFIG.md ]] || { printf 'Not a full Limine source directory.\n' >&2; exit 1; }
if command -v sha256sum >/dev/null; then
    actual=$(sha256sum "$patch" | awk '{print $1}')
else
    actual=$(shasum -a 256 "$patch" | awk '{print $1}')
fi
[[ $actual == "$expected" ]] || { printf 'The preserved tested patch checksum differs.\n' >&2; exit 1; }
git -C "$source_dir" apply --check --whitespace=error-all "$patch"
printf 'The unchanged tested patch applies cleanly. No source files were changed.\n'
printf 'This check does not establish build or hardware compatibility.\n'
