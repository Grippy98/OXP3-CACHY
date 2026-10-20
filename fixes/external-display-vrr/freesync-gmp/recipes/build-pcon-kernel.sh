#!/usr/bin/env bash
# Build the opt-in SDR FreeSync/GMP prototype on a copied accepted VRR cache.
set -euo pipefail
source_dir=${1:?Pass a copied, prepared 7.2.9-onex3-vrr-test build tree}
output_dir=${2:?Pass a NEW build-evidence directory}
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
experiment_dir=$(cd -- "$script_dir/../.." && pwd)
patch_path=${3:-$experiment_dir/intel-pcon-vrr-experimental.patch}
baseline_evidence=${4:?Pass the accepted baseline build output directory}
mode_vtotal_patch=${5:-$experiment_dir/intel-vrr-mode-vtotal-f26a8df.patch}
freesync_patch=${6:-$script_dir/../intel-pcon-freesync-gmp-prototype.patch}
jobs=${JOBS:-16}
llvm=${LLVM_SUFFIX:--19}
source_dir=$(cd -- "$source_dir" && pwd)
[[ ! -e "$output_dir" ]]
[[ "$jobs" =~ ^[1-9][0-9]*$ ]]
check_sha() {
    [[ $(sha256sum -- "$1" | cut -d ' ' -f 1) == "$2" ]]
}
check_sha "$source_dir/.config" 9753cf116157b197869ceff02cbee8b83b4b0ea613ef5c16667049af4cdaafe5
check_sha "$source_dir/drivers/gpu/drm/i915/display/intel_vrr.c" e0c39e63eeb144fa2a2e512f1566b6331a4d26f37e5c4167b0bae0f05f0a0f09
check_sha "$source_dir/drivers/gpu/drm/i915/display/intel_dsb.c" c6bc000b8b1f2e52b05bf4ea65ec301d5aacac55198497fb0462b79436d4a4ed
[[ -s "$patch_path" ]]
[[ -s "$mode_vtotal_patch" ]]
[[ -s "$freesync_patch" ]]
cd -- "$source_dir"
python3 "$script_dir/require-inputplumber-kernel.py" .config
git apply --check "$patch_path"
mkdir -p -- "$output_dir/original/drivers/gpu/drm/i915/display"
output_dir=$(cd -- "$output_dir" && pwd)
cp -- .config "$output_dir/original/.config"
for name in intel_ddi.c intel_display.c intel_display_params.c intel_display_params.h intel_display_types.h intel_dp.c intel_dp.h intel_vrr.c; do
    cp -- "drivers/gpu/drm/i915/display/$name" "$output_dir/original/drivers/gpu/drm/i915/display/$name"
done
install -m644 -- "$patch_path" "$output_dir/intel-pcon-vrr-experimental.patch"
install -m644 -- "$mode_vtotal_patch" "$output_dir/intel-vrr-mode-vtotal-f26a8df.patch"
install -m644 -- "$freesync_patch" "$output_dir/intel-pcon-freesync-gmp-prototype.patch"
for name in edid-segment-reset-retry.patch intel-dsb-delayed-vblank-scanline-f7140c7c.patch \
            intel-dsb-safe-window-fixed-refresh-4a68c751.patch intel-vrr-disable-dc-balance-c034e8a.patch; do
    install -m644 -- "$baseline_evidence/$name" "$output_dir/$name"
    git apply --reverse --check "$output_dir/$name"
done
install -m644 -- "$baseline_evidence/build-provenance.txt" "$output_dir/baseline-build-provenance.txt"
sha256sum .config drivers/gpu/drm/i915/display/intel_{ddi.c,display.c,display_params.c,display_params.h,display_types.h,dp.c,dp.h,vrr.c,dsb.c} > "$output_dir/before.sha256"
git apply "$output_dir/intel-pcon-vrr-experimental.patch"
git apply --reverse --check "$output_dir/intel-pcon-vrr-experimental.patch"
git apply --check "$output_dir/intel-vrr-mode-vtotal-f26a8df.patch"
git apply "$output_dir/intel-vrr-mode-vtotal-f26a8df.patch"
git apply --reverse --check "$output_dir/intel-vrr-mode-vtotal-f26a8df.patch"
git apply --check "$output_dir/intel-pcon-freesync-gmp-prototype.patch"
git apply "$output_dir/intel-pcon-freesync-gmp-prototype.patch"
git apply --reverse --check "$output_dir/intel-pcon-freesync-gmp-prototype.patch"
scripts/config --set-str LOCALVERSION -onex3-pcon-vrr-test
scripts/config --disable LOCALVERSION_AUTO
make ARCH=x86_64 LLVM="$llvm" olddefconfig > "$output_dir/configure.log" 2>&1
make ARCH=x86_64 LLVM="$llvm" syncconfig >> "$output_dir/configure.log" 2>&1
[[ $(make -s ARCH=x86_64 LLVM="$llvm" kernelrelease) == 7.2.9-onex3-pcon-vrr-test ]]
python3 "$script_dir/require-inputplumber-kernel.py" .config
python3 - "$output_dir/original/.config" .config <<'PY'
from pathlib import Path
import sys
def options(path):
    return {line.split('=', 1)[0]: line for line in Path(path).read_text().splitlines()
            if line.startswith('CONFIG_') and '=' in line}
before, after = map(options, sys.argv[1:])
assert before.pop('CONFIG_LOCALVERSION') == 'CONFIG_LOCALVERSION="-onex3-vrr-test"'
assert after.pop('CONFIG_LOCALVERSION') == 'CONFIG_LOCALVERSION="-onex3-pcon-vrr-test"'
assert before == after, 'Unexpected kernel option changes'
PY
cp -- .config "$output_dir/pcon-kernel.config"
sha256sum .config drivers/gpu/drm/i915/display/intel_{ddi.c,display.c,display_params.c,display_params.h,display_types.h,dp.c,dp.h,vrr.c,dsb.c} > "$output_dir/after.sha256"
diff -u "$output_dir/original/.config" .config > "$output_dir/config.diff" || [[ $? == 1 ]]
clang${llvm} --version > "$output_dir/compiler.txt"
pahole --version > "$output_dir/pahole.txt"
uname -m > "$output_dir/build-host-architecture.txt"
printf 'make ARCH=x86_64 LLVM=%s -j%s bzImage modules\n' "$llvm" "$jobs" > "$output_dir/build-command.txt"
{
    printf 'Experimental Intel SST PCON VRR build; not a distribution release.\n'
    printf 'Release: 7.2.9-onex3-pcon-vrr-test\nPackage: linux-onex3-pcon-vrr-test 7.2.9-3\n'
    printf 'Baseline: accepted 7.2.9-onex3-vrr-test; retained EDID, DSB, DC-balance and controller fixes.\n'
    printf 'Complete baseline source and patch identities are appended below.\n'
    printf 'Experimental patch SHA256: '
    sha256sum "$output_dir/intel-pcon-vrr-experimental.patch" | cut -d ' ' -f 1
    printf 'Upstream mode-VTotal patch SHA256: '
    sha256sum "$output_dir/intel-vrr-mode-vtotal-f26a8df.patch" | cut -d ' ' -f 1
    printf 'FreeSync/GMP prototype patch SHA256: '
    sha256sum "$output_dir/intel-pcon-freesync-gmp-prototype.patch" | cut -d ' ' -f 1
    printf 'Config SHA256: '
    sha256sum .config | cut -d ' ' -f 1
    printf 'All config options except LOCALVERSION match the accepted baseline.\n'
    printf 'PCON VRR and FreeSync/GMP remain disabled by default; hardware testing is a separate step.\n'
    printf '\nBaseline provenance:\n'
    cat -- "$output_dir/baseline-build-provenance.txt"
} > "$output_dir/build-provenance.txt"
date -u +%FT%TZ > "$output_dir/build-started-utc.txt"
set +e
make ARCH=x86_64 LLVM="$llvm" -j"$jobs" bzImage modules > "$output_dir/build.log" 2>&1
result=$?
set -e
date -u +%FT%TZ > "$output_dir/build-finished-utc.txt"
printf '%s\n' "$result" > "$output_dir/build.exit"
[[ $result == 0 ]]
cp -- arch/x86/boot/bzImage "$output_dir/bzImage"
printf 'Built 7.2.9-onex3-pcon-vrr-test; no target installation or boot performed.\n'
