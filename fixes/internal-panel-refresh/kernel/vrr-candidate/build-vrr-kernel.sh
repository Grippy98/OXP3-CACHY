#!/usr/bin/env bash
# Build a separate candidate from the verified completed revision 3 source/cache.
# Use a copied build tree: this deliberately changes its release and source.
set -euo pipefail
source_dir=${1:?Pass a copied, prepared revision 3 source/build tree}
output_dir=${2:?Pass a NEW build-evidence directory}
jobs=${JOBS:-16}
llvm=${LLVM_SUFFIX:--19}
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source_dir=$(cd -- "$source_dir" && pwd)
[[ ! -e "$output_dir" ]]
[[ "$jobs" =~ ^[1-9][0-9]*$ ]]
patch_dir=$script_dir/../../upstream
new_patch=$patch_dir/intel-vrr-disable-dc-balance-c034e8a.patch
check_sha() {
    [[ $(sha256sum -- "$1" | cut -d ' ' -f 1) == "$2" ]]
}
check_sha "$new_patch" 8dadc15c473105793d515a0e68e33faf24327f5118012fccc0ceb4c7b05d33d7
check_sha "$source_dir/.config" 80b1ece7b9185d75b7df202ac0dfbf544983e131be9ee98285fffed6dae2b72c
check_sha "$source_dir/drivers/gpu/drm/i915/display/intel_dsb.c" c6bc000b8b1f2e52b05bf4ea65ec301d5aacac55198497fb0462b79436d4a4ed
check_sha "$source_dir/drivers/gpu/drm/i915/display/intel_display_params.c" 202c2497429d1858eadd4d99f0f4df0c7ea05ff3a11de25ac9a87405353e4b8c
check_sha "$source_dir/drivers/gpu/drm/i915/display/intel_display_params.h" 169bdc84eb93d87d7dd62c3e640f494c0e75a8b5639b91848503eba3a058b6f3
check_sha "$source_dir/drivers/gpu/drm/i915/display/intel_vrr.c" ded95aea4810697bbc399b8cdfd6ec42d1e1c897321a2ec820fa52ad518223b5
cd -- "$source_dir"
python3 "$script_dir/../require-inputplumber-kernel.py" .config
git apply --reverse --check "$script_dir/../../../lg-c5-edid/kernel/edid-segment-reset-retry.patch"
git apply --check "$new_patch"
mkdir -p -- "$output_dir/original/drivers/gpu/drm/i915/display"
output_dir=$(cd -- "$output_dir" && pwd)
cp -- .config "$output_dir/original/.config"
for name in intel_display_params.c intel_display_params.h intel_vrr.c; do
    cp -- "drivers/gpu/drm/i915/display/$name" "$output_dir/original/drivers/gpu/drm/i915/display/$name"
done
sha256sum .config drivers/gpu/drm/i915/display/intel_{display_params.c,display_params.h,vrr.c,dsb.c} > "$output_dir/before.sha256"
install -m644 -- "$new_patch" "$patch_dir/intel-dsb-delayed-vblank-scanline-f7140c7c.patch" \
    "$patch_dir/intel-dsb-safe-window-fixed-refresh-4a68c751.patch" \
    "$script_dir/../../../lg-c5-edid/kernel/edid-segment-reset-retry.patch" "$output_dir/"
git apply "$new_patch"
git apply --reverse --check "$new_patch"
scripts/config --set-str LOCALVERSION -onex3-vrr-test
scripts/config --disable LOCALVERSION_AUTO
make ARCH=x86_64 LLVM="$llvm" olddefconfig > "$output_dir/configure.log" 2>&1
make ARCH=x86_64 LLVM="$llvm" syncconfig >> "$output_dir/configure.log" 2>&1
[[ $(make -s ARCH=x86_64 LLVM="$llvm" kernelrelease) == 7.2.9-onex3-vrr-test ]]
check_sha .config 9753cf116157b197869ceff02cbee8b83b4b0ea613ef5c16667049af4cdaafe5
python3 "$script_dir/../require-inputplumber-kernel.py" .config
cp -- .config "$output_dir/vrr-kernel.config"
sha256sum .config drivers/gpu/drm/i915/display/intel_{display_params.c,display_params.h,vrr.c,dsb.c} > "$output_dir/after.sha256"
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
date -u +%FT%TZ > "$output_dir/build-started-utc.txt"
set +e
make ARCH=x86_64 LLVM="$llvm" -j"$jobs" bzImage modules > "$output_dir/build.log" 2>&1
result=$?
set -e
date -u +%FT%TZ > "$output_dir/build-finished-utc.txt"
printf '%s\n' "$result" > "$output_dir/build.exit"
[[ $result == 0 ]]
printf 'Built 7.2.9-onex3-vrr-test; no target installation or boot performed.\n'
