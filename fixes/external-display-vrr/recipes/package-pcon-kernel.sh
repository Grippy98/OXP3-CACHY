#!/usr/bin/env bash
# Package a completed cross build without host binaries or kernel headers.
set -euo pipefail
source_dir=${1:?Pass the completed source/build tree}
build_evidence=${2:?Pass the build-evidence directory}
stage=${3:?Pass a NEW installation staging directory}
package_dir=${4:?Pass the package output directory}
llvm=${LLVM_SUFFIX:--19}
release=7.2.9-onex3-pcon-vrr-test
package=linux-onex3-pcon-vrr-test
version=7.2.9-2
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source_dir=$(cd -- "$source_dir" && pwd)
build_evidence=$(cd -- "$build_evidence" && pwd)
[[ ! -e "$stage" ]]
[[ $(cat "$build_evidence/build.exit") == 0 ]]
cd -- "$source_dir"
[[ $(make -s ARCH=x86_64 LLVM="$llvm" kernelrelease) == "$release" ]]
cmp -- .config "$build_evidence/pcon-kernel.config"
python3 "$script_dir/require-inputplumber-kernel.py" .config
[[ -s "$build_evidence/controller-module/hid-oxp.ko.zst" ]]
mkdir -p -- "$stage" "$package_dir"
stage=$(cd -- "$stage" && pwd)
package_dir=$(cd -- "$package_dir" && pwd)
package_path=$package_dir/$package-$version-x86_64.pkg.tar.zst
[[ ! -e "$package_path" ]]
make ARCH=x86_64 LLVM="$llvm" INSTALL_MOD_PATH="$stage" INSTALL_MOD_STRIP=1 DEPMOD=/bin/true \
    modules_install > "$build_evidence/modules-install.log" 2>&1
module_dir=$stage/lib/modules/$release
[[ -d "$module_dir" ]]
mkdir -p -- "$module_dir/updates/dkms"
install -m644 -- "$build_evidence/controller-module/hid-oxp.ko.zst" \
    "$module_dir/updates/dkms/hid-oxp.ko.zst"
depmod -b "$stage" "$release"
modprobe -d "$stage" -S "$release" --show-depends hid-oxp \
    > "$build_evidence/controller-load-path.txt"
[[ $(cat "$build_evidence/controller-load-path.txt") == *'/updates/dkms/hid-oxp.ko.zst'* ]]
# modules_install creates links into the build tree. They are not target payload.
for link in build source; do
    [[ ! -e "$module_dir/$link" || -L "$module_dir/$link" ]]
    [[ ! -L "$module_dir/$link" ]] || rm -- "$module_dir/$link"
done
mkdir -p -- "$stage/usr/lib/modules"
mv -- "$module_dir" "$stage/usr/lib/modules/"
rmdir -- "$stage/lib/modules" "$stage/lib"
module_dir=$stage/usr/lib/modules/$release
install -m644 -- arch/x86/boot/bzImage "$module_dir/vmlinuz"
install -m644 -- .config "$module_dir/config"
python3 "$script_dir/require-inputplumber-kernel.py" "$module_dir/config" "$module_dir"
install -m644 -- System.map "$module_dir/System.map"
printf '%s\n' "$package" > "$module_dir/pkgbase"
mkdir -p -- "$stage/usr/share/licenses/$package" "$stage/usr/share/doc/$package"
install -m644 -- LICENSES/preferred/GPL-2.0 "$stage/usr/share/licenses/$package/GPL-2.0"
install -m644 -- "$build_evidence/pcon-kernel.config" \
    "$build_evidence/edid-segment-reset-retry.patch" \
    "$build_evidence/intel-dsb-delayed-vblank-scanline-f7140c7c.patch" \
    "$build_evidence/intel-dsb-safe-window-fixed-refresh-4a68c751.patch" \
    "$build_evidence/intel-vrr-disable-dc-balance-c034e8a.patch" \
    "$build_evidence/intel-pcon-vrr-experimental.patch" \
    "$build_evidence/intel-vrr-mode-vtotal-f26a8df.patch" \
    "$build_evidence/build-provenance.txt" "$stage/usr/share/doc/$package/"
mkdir -p -- "$stage/usr/share/doc/$package/controller-source"
install -m644 -- "$build_evidence/controller-module/hid-oxp.c" \
    "$build_evidence/controller-module/hid-ids.h" \
    "$build_evidence/controller-module/Makefile" \
    "$stage/usr/share/doc/$package/controller-source/"
size=$(du -sb "$stage/usr" | cut -f1)
cat > "$stage/.PKGINFO" <<EOF
pkgname = $package
pkgbase = $package
pkgver = $version
pkgdesc = OXP3 experimental Intel SST PCON VRR with existing controller, DSB and EDID fixes
url = https://github.com/CachyOS/linux/releases/tag/cachyos-7.2.9-2
builddate = $(date +%s)
packager = local experimental build
size = $size
arch = x86_64
license = GPL-2.0-only
depend = coreutils
depend = kmod
depend = initramfs
optdepend = linux-firmware: firmware for hardware devices
EOF
tar --zstd -cf "$package_path" -C "$stage" .PKGINFO usr
sha256sum -- "$package_path" > "$build_evidence/package.sha256"
tar --zstd -tf "$package_path" > "$build_evidence/package-files.txt"
printf 'Packaged %s; no target installation or boot performed.\n' "$package_path"
