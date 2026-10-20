#!/usr/bin/env bash
# Restore the two source/config files changed by build-display-kernel.sh.
# Compiled cache remains the display candidate until rebuilt for another release.
set -euo pipefail
source_dir=${1:?Pass the source directory}
build_evidence=${2:?Pass the build-evidence directory}
source_dir=$(cd -- "$source_dir" && pwd)
build_evidence=$(cd -- "$build_evidence" && pwd)
cd -- "$source_dir"
sha256sum --check "$build_evidence/after.sha256"
cp -- "$build_evidence/original/.config" .config
cp -- "$build_evidence/original/drivers/gpu/drm/i915/display/intel_dsb.c" \
    drivers/gpu/drm/i915/display/intel_dsb.c
sha256sum --check "$build_evidence/before.sha256"
printf 'Original source/config restored; compiled cache remains the candidate.\n'
