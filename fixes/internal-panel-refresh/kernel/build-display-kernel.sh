#!/usr/bin/env bash
# Build from the already prepared, verified EDID test source/cache on Linux.
# This script changes only the supplied build tree; it never installs or boots.
set -euo pipefail
source_dir=${1:?Pass the prepared cachyos-7.2.9-2 source directory}
output_dir=${2:?Pass a new build-evidence directory}
jobs=${JOBS:-16}
llvm=${LLVM_SUFFIX:--19}
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source_dir=$(cd -- "$source_dir" && pwd)
[[ ! -e "$output_dir" ]]
[[ "$jobs" =~ ^[1-9][0-9]*$ ]]
dsb_path=drivers/gpu/drm/i915/display/intel_dsb.c
first_patch=$script_dir/../upstream/intel-dsb-delayed-vblank-scanline-f7140c7c.patch
second_patch=$script_dir/../upstream/intel-dsb-safe-window-fixed-refresh-4a68c751.patch
edid_patch=$script_dir/../../lg-c5-edid/kernel/edid-segment-reset-retry.patch
check_sha() {
    [[ $(sha256sum -- "$1" | cut -d ' ' -f 1) == "$2" ]]
}
check_sha "$first_patch" 76029ba44baabe31f911e1515f5badd7618fe859fd2cde30d419304b70754c3f
check_sha "$second_patch" 2c9654487f7b139eeca480cf78ea80d919fcc151f5ddff8af3acc5dc4f90767d
check_sha "$edid_patch" ee0912dff16e866f0c8c75ad1152b093e32a0b00ffbf587d1d5292e13097b8cc
check_sha "$source_dir/$dsb_path" 3bee9187f1ef4a2cb526768dde8a6d9960da92e6a4c0480ef0709cb3759a8c21
check_sha "$source_dir/.config" 9f253f9e3b47a31a425ecb97af0402de73cd3aa4051f780adbc177703eaf53f0
cd -- "$source_dir"
make ARCH=x86_64 LLVM="$llvm" syncconfig
[[ $(make -s ARCH=x86_64 LLVM="$llvm" kernelrelease) == 7.2.9-onex3-edid-test ]]
git apply --reverse --check "$edid_patch"
mkdir -p -- "$output_dir/original/drivers/gpu/drm/i915/display"
output_dir=$(cd -- "$output_dir" && pwd)
cp -- .config "$output_dir/original/.config"
cp -- "$dsb_path" "$output_dir/original/$dsb_path"
install -m644 -- "$first_patch" "$second_patch" "$edid_patch" "$output_dir/"
sha256sum .config "$dsb_path" > "$output_dir/before.sha256"
git apply --check "$first_patch"
git apply "$first_patch"
git apply --check "$second_patch"
git apply "$second_patch"
check_sha "$dsb_path" c6bc000b8b1f2e52b05bf4ea65ec301d5aacac55198497fb0462b79436d4a4ed
scripts/config --set-str LOCALVERSION -onex3-display-test
scripts/config --disable LOCALVERSION_AUTO
scripts/config --module UHID --module INPUT_UINPUT
make ARCH=x86_64 LLVM="$llvm" olddefconfig > "$output_dir/configure.log" 2>&1
make ARCH=x86_64 LLVM="$llvm" syncconfig >> "$output_dir/configure.log" 2>&1
[[ $(make -s ARCH=x86_64 LLVM="$llvm" kernelrelease) == 7.2.9-onex3-display-test ]]
python3 "$script_dir/require-inputplumber-kernel.py" .config
cp -- .config "$output_dir/display-kernel.config"
sha256sum .config "$dsb_path" > "$output_dir/after.sha256"
diff -u "$output_dir/original/.config" .config > "$output_dir/config.diff" || [[ $? == 1 ]]
{
    printf 'Pinned source: CachyOS/linux cachyos-7.2.9-2, commit 09bc889a111715e4509b3819b628c9b9d9d09a0b\n'
    printf 'Distribution recipe: CachyOS/linux-cachyos ee39638ff003ef2def73671ec1677d48218e7c03\n'
    printf 'Source inputs: see fixes/lg-c5-edid/docs/SOURCES.md in the source repository.\n'
    printf 'Release: '; make -s ARCH=x86_64 LLVM="$llvm" kernelrelease
    printf 'Config and applied patch identities:\n'
    sha256sum .config "$output_dir/"*.patch
} > "$output_dir/build-provenance.txt"
clang${llvm} --version > "$output_dir/compiler.txt"
pahole --version > "$output_dir/pahole.txt"
uname -m > "$output_dir/build-host-architecture.txt"
printf 'make ARCH=x86_64 LLVM=%s -j%s bzImage modules\n' "$llvm" "$jobs" > "$output_dir/build-command.txt"
set +e
make ARCH=x86_64 LLVM="$llvm" -j"$jobs" bzImage modules > "$output_dir/build.log" 2>&1
result=$?
set -e
printf '%s\n' "$result" > "$output_dir/build.exit"
[[ $result == 0 ]]
printf 'Built 7.2.9-onex3-display-test; no installation or boot performed.\n'
