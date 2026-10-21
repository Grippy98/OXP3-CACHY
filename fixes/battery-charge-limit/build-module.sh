#!/usr/bin/env bash
# Build the pinned driver externally; never change the kernel source/configuration.
set -euo pipefail
if [[ ${1:-} == --help ]]; then
    echo 'Usage: build-module.sh KERNEL_BUILD_DIR OUTPUT_DIR'
    echo 'Both paths must be absolute; OUTPUT_DIR must not exist. Requires a prepared x86 kernel tree.'
    echo 'Honors LLVM, LLVM_IAS, CROSS_COMPILE, MAKEFLAGS and JOBS; installs nothing.'
    exit 0
fi
[[ $# == 2 ]] || { echo 'Usage: build-module.sh KERNEL_BUILD_DIR OUTPUT_DIR' >&2; exit 2; }
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
kernel_build=$1
output=$2
[[ $kernel_build == /* && $output == /* ]] || { echo 'Use absolute paths.' >&2; exit 2; }
[[ $(uname -s) == Linux ]] || { echo 'Build inside Linux, including an appropriate Linux container.' >&2; exit 1; }
[[ ! -e $output && ! -L $output && -d $(dirname -- "$output") ]] || {
    echo 'OUTPUT_DIR must be new and its parent must exist.' >&2; exit 1;
}
for command in make patch python3 modinfo; do
    command -v "$command" >/dev/null || { echo "Required build tool: $command" >&2; exit 1; }
done
for file in .config Makefile Module.symvers include/generated/autoconf.h include/config/kernel.release; do
    [[ -f $kernel_build/$file ]] || { echo "Prepared kernel file missing: $file" >&2; exit 1; }
done
arch=${ARCH:-x86_64}
[[ $arch == x86 || $arch == x86_64 ]] || { echo 'This module targets an x86-64 kernel.' >&2; exit 1; }
grep -q '^CONFIG_X86_64=y$' "$kernel_build/.config" || { echo 'CONFIG_X86_64=y is required.' >&2; exit 1; }
jobs=${JOBS:-$(getconf _NPROCESSORS_ONLN)}
[[ $jobs =~ ^[1-9][0-9]*$ ]] || { echo 'JOBS must be a positive integer.' >&2; exit 2; }
python3 - "$here" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
expected = json.loads((root / 'SOURCE.json').read_text())['driver']['sha256']
actual = hashlib.sha256((root / 'source/oxpec.c').read_bytes()).hexdigest()
if actual != expected:
    raise SystemExit('Pinned oxpec.c checksum mismatch; refusing build.')
PY
mkdir -m 0755 -- "$output"
cp -- "$here/source/oxpec.c" "$output/oxpec.c"
patch --batch --forward --fuzz=0 "$output/oxpec.c" "$here/patches/0001-oxpec-add-onexplayer3-quirk.patch"
printf 'obj-m += oxpec.o\n' > "$output/Makefile"
make_args=("ARCH=$arch" "M=$output")
if [[ -n ${LLVM:-} ]]; then make_args+=("LLVM=$LLVM"); fi
make -C "$kernel_build" "${make_args[@]}" -j "$jobs" modules
release=$(cat "$kernel_build/include/config/kernel.release")
[[ $(modinfo -F name "$output/oxpec.ko") == oxpec ]] || { echo 'Unexpected module name.' >&2; exit 1; }
vermagic=$(modinfo -F vermagic "$output/oxpec.ko")
[[ ${vermagic%% *} == "$release" ]] || { echo 'Built module vermagic does not match the prepared tree.' >&2; exit 1; }
python3 - "$output/oxpec.ko" <<'PY'
import hashlib, sys
from pathlib import Path
path = Path(sys.argv[1])
print(f'Built {path}\nSHA256 {hashlib.sha256(path.read_bytes()).hexdigest()}')
PY
echo "Target kernel: $release. Sign the module separately if your kernel requires a trusted signature."
