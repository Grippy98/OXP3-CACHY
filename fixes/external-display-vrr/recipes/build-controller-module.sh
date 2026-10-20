#!/usr/bin/env bash
# Preserve the existing PR 13 controller fix in the separate test kernel.
set -euo pipefail
source_dir=${1:?Pass the completed PCON VRR candidate kernel build tree}
output_dir=${2:?Pass a new controller-module output directory}
llvm=${LLVM_SUFFIX:--19}
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
controller_source=${3:-$script_dir/controller-source}
source_dir=$(cd -- "$source_dir" && pwd)
[[ ! -e "$output_dir" ]]
check_sha() {
    [[ $(sha256sum -- "$1" | cut -d ' ' -f 1) == "$2" ]]
}
check_sha "$controller_source/hid-oxp.c" 64e1edb403f31808f44d6b347017b4c73d3dd7670d5bba995231e8e6ec9a9e29
check_sha "$controller_source/hid-ids.h" a2365e0160a12365aa3e89208844f2a27a43b78fd6803ca0c19dd10edff79f1b
check_sha "$controller_source/Makefile" 3c2e28860d039ae46239f38fe81eaf6db3cf6b2ad56d7d2a18daffb1e789f4dd
python3 "$script_dir/require-inputplumber-kernel.py" "$source_dir/.config"
[[ $(make -s -C "$source_dir" ARCH=x86_64 LLVM="$llvm" kernelrelease) == 7.2.9-onex3-pcon-vrr-test ]]
[[ -s "$source_dir/Module.symvers" ]]
mkdir -p -- "$output_dir"
output_dir=$(cd -- "$output_dir" && pwd)
install -m644 -- "$controller_source/hid-oxp.c" "$controller_source/hid-ids.h" \
    "$controller_source/Makefile" "$output_dir/"
make -C "$source_dir" ARCH=x86_64 LLVM="$llvm" M="$output_dir" W=1 modules \
    > "$output_dir/build.log" 2>&1
llvm-strip${llvm} --strip-debug "$output_dir/hid-oxp.ko"
"$source_dir/scripts/sign-file" sha512 "$source_dir/certs/signing_key.pem" \
    "$source_dir/certs/signing_key.x509" "$output_dir/hid-oxp.ko"
zstd -19 -T0 -q -o "$output_dir/hid-oxp.ko.zst" "$output_dir/hid-oxp.ko"
modinfo "$output_dir/hid-oxp.ko.zst" > "$output_dir/modinfo.txt"
[[ $(modinfo -F vermagic "$output_dir/hid-oxp.ko.zst") == '7.2.9-onex3-pcon-vrr-test '* ]]
[[ -n $(modinfo -F signer "$output_dir/hid-oxp.ko.zst") ]]
sha256sum "$output_dir/hid-oxp.ko.zst" > "$output_dir/module.sha256"
printf 'Built and signed the pinned PR 13 hid-oxp module for the PCON VRR candidate release.\n'
