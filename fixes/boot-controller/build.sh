#!/usr/bin/env bash
set -euo pipefail
bundle_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
output_dir=${1:-"$bundle_dir/build"}
[[ $# -le 1 ]] || { echo 'Usage: bash build.sh [OUTPUT_DIRECTORY]' >&2; exit 2; }
for dependency in curl patch tar shasum docker; do
    command -v "$dependency" >/dev/null || { printf 'Missing command: %s\n' "$dependency" >&2; exit 1; }
done
mkdir -p "$output_dir"
output_dir=$(cd -- "$output_dir" && pwd)
build_tmp=$(mktemp -d)
trap 'rm -rf "$build_tmp"' EXIT
archive="$build_tmp/limine-12.9.0.tar.xz"
curl --fail --location --retry 2 \
    https://github.com/Limine-Bootloader/Limine/releases/download/v12.9.0/limine-12.9.0.tar.xz \
    --output "$archive"
actual=$(shasum -a 256 "$archive" | awk '{print $1}')
[[ $actual == 86107e8754365124b1871479f766697461f16ce9d847b3c23bb269335588c565 ]] || {
    echo 'The upstream source checksum differs from the pinned release.' >&2; exit 1;
}
mkdir "$build_tmp/src" "$build_tmp/build"
tar -xf "$archive" --strip-components=1 -C "$build_tmp/src"
patch -d "$build_tmp/src" -p1 < "$bundle_dir/limine-gamepad.patch"
build_image=${OXP3_LIMINE_BUILD_IMAGE:-oxp3-limine-builder:clang19}
docker build -t "$build_image" "$bundle_dir"
docker run --rm --user "$(id -u):$(id -g)" \
    -v "$build_tmp:/work" "$build_image" sh -ec '
        cd /work/build
        ../src/configure --enable-uefi-x86-64 CC=cc \
            CC_FOR_TARGET=clang-19 LD_FOR_TARGET=ld.lld-19 \
            OBJCOPY_FOR_TARGET=llvm-objcopy-19 \
            OBJDUMP_FOR_TARGET=llvm-objdump-19 READELF_FOR_TARGET=llvm-readelf-19
        make -j4
    ' > "$output_dir/build.log" 2>&1
cp "$build_tmp/build/bin/BOOTX64.EFI" "$output_dir/BOOTX64.EFI"
(cd "$output_dir" && shasum -a 256 BOOTX64.EFI > BOOTX64.EFI.sha256)
echo "Built x86-64 EFI application: $output_dir/BOOTX64.EFI"
cat "$output_dir/BOOTX64.EFI.sha256"
