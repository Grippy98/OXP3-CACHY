#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -eEuo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
die() { printf 'Error: %s\n' "$*" >&2; exit 1; }
usage() { printf 'Usage: bash install.sh [--check] [KERNEL_RELEASE]\n'; }
if [[ ${1:-} == --help ]]; then usage; exit 0; fi
check=false
if [[ ${1:-} == --check ]]; then check=true; shift; fi
[[ $# -le 1 ]] || { usage >&2; exit 2; }
[[ $(uname -s) == Linux ]] || die 'Run on the CachyOS ONEXPLAYER 3 handheld.'
[[ -r /sys/class/dmi/id/product_name && -r /sys/class/dmi/id/sys_vendor ]] || die 'Cannot read DMI identity.'
[[ $(cat /sys/class/dmi/id/product_name) == 'ONEXPLAYER 3' &&
   $(cat /sys/class/dmi/id/sys_vendor) == ONE-NETBOOK ]] || die 'Requires ONE-NETBOOK ONEXPLAYER 3.'
kernel=${1:-$(uname -r)}
[[ $kernel =~ ^[[:alnum:]_.+-]+$ && $kernel == *-cachyos* ]] || die 'Select an installed CachyOS kernel release with matching headers.'
modules=/usr/lib/modules/$kernel
[[ -d $modules ]] || die "Kernel modules are missing: $modules"
for dependency in pacman systemctl systemd-hwdb install cp cmp mktemp readlink sha256sum flock; do
    command -v "$dependency" >/dev/null || die "Missing command: $dependency"
done
for file in hid-oxp.c hid-ids.h Makefile dkms.conf; do
    [[ -s $here/kernel/$file ]] || die "Missing source: kernel/$file"
done
[[ $(sha256sum "$here/kernel/hid-oxp.c" | cut -d ' ' -f 1) == 64e1edb403f31808f44d6b347017b4c73d3dd7670d5bba995231e8e6ec9a9e29 ]] || die 'Pinned driver source checksum differs.'
header_package=
if [[ ! -e $modules/build/Makefile ]]; then
    [[ -r $modules/pkgbase ]] || die "Install headers matching $kernel before running this installer."
    pkgbase=$(cat "$modules/pkgbase")
    [[ $pkgbase =~ ^linux[[:alnum:]_.+-]*$ ]] || die 'Cannot determine the matching header package.'
    header_package=$pkgbase-headers
fi
if $check; then
    printf 'Target kernel: %s\nRequired packages: base-devel dkms inputplumber %s\n' "$kernel" "$header_package"
    [[ -e $modules/build/Makefile ]] || die "Install $header_package and confirm it matches $kernel; repository headers may target a newer kernel."
    for dependency in dkms make cc modinfo depmod inputplumber; do
        command -v "$dependency" >/dev/null || die "Missing command: $dependency; installation can add the required CachyOS packages."
    done
    systemctl cat inputplumber.service >/dev/null
    command -v limine-mkinitcpio >/dev/null || command -v mkinitcpio >/dev/null || die 'Missing initramfs generator: limine-mkinitcpio or mkinitcpio'
    printf 'Controller build prerequisites are available; no changes made.\n'
    exit 0
fi
[[ $EUID == 0 ]] || die 'Run with sudo.'
command -v limine-mkinitcpio >/dev/null || command -v mkinitcpio >/dev/null || die 'Missing initramfs generator: limine-mkinitcpio or mkinitcpio'
refresh_initramfs() {
    if command -v limine-mkinitcpio >/dev/null; then limine-mkinitcpio; else mkinitcpio -P; fi
}
install -d /run/lock
exec 200>/run/lock/oxp3-controllers.lock
flock --timeout=10 200 || die 'Another controller installation is in progress.'
packages=(base-devel dkms inputplumber)
[[ -z $header_package ]] || packages+=("$header_package")
pacman -S --needed "${packages[@]}"
for dependency in dkms make cc modinfo depmod inputplumber; do
    command -v "$dependency" >/dev/null || die "Missing command after dependency installation: $dependency"
done
[[ -e $modules/build/Makefile ]] || die "Headers for $kernel are missing; boot the matching updated kernel or install its exact headers."
built_release=$(make -s -C "$modules/build" kernelrelease)
[[ $built_release == "$kernel" ]] || die "Header release $built_release differs from selected kernel $kernel."
name=hid-oxp-onex3
version=0.1.4396c18
source_dir=/usr/src/$name-$version
if [[ -e $source_dir ]]; then
    for file in hid-oxp.c hid-ids.h Makefile; do
        cmp -s "$here/kernel/$file" "$source_dir/$file" || die "Existing DKMS source differs: $source_dir/$file"
    done
    [[ -f $source_dir/dkms.conf ]] || die 'Existing DKMS configuration is missing.'
    cmp -s <(sed '/^[[:space:]]*#/d; /^[[:space:]]*$/d' "$here/kernel/dkms.conf") \
           <(sed '/^[[:space:]]*#/d; /^[[:space:]]*$/d' "$source_dir/dkms.conf") || die 'Existing DKMS configuration differs.'
fi
state=/var/lib/oxp3-fixes/controllers
install -d -m 0700 "$state"
backup=$(mktemp -d "$state/$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
printf '%s\n' oxp3-controllers-backup-v1 > "$backup/format"
printf '%s\n' "$kernel" > "$backup/kernel"
printf '%s\n' "$name" > "$backup/dkms-name"
printf '%s\n' "$version" > "$backup/dkms-version"
printf '%s\n' "$source_dir" > "$backup/source-dir"
prior_status=$(dkms status -m "$name" -v "$version" 2>/dev/null || true)
printf '%s\n' "$prior_status" > "$backup/dkms-before"
stock=$(modinfo -k "$kernel" -n hid_oxp 2>/dev/null || true)
if [[ -f $stock ]]; then
    cp -a -- "$stock" "$backup/$(basename "$stock")"
    printf '%s\n' "$stock" > "$backup/module-path-before"
fi
created_source=false
created_registration=false
installed_target=false
ip_previous=
ip_installed=
[[ ! -r /var/lib/oxp3-fixes/inputplumber/latest-backup ]] || ip_previous=$(cat /var/lib/oxp3-fixes/inputplumber/latest-backup)
recover() {
    status=$?
    trap - EXIT
    (( status != 0 )) || return 0
    if [[ -n $ip_installed ]]; then bash "$here/inputplumber/rollback.sh" "$ip_installed" || true; fi
    if $installed_target; then dkms remove -m "$name" -v "$version" -k "$kernel" || true; fi
    if $created_registration; then dkms remove -m "$name" -v "$version" --all || true; fi
    if $created_source; then rm -rf -- "$source_dir"; fi
    depmod -a "$kernel" || true
    refresh_initramfs || true
    printf 'Installation failed. Saved prior state: %s\n' "$backup" >&2
    exit "$status"
}
trap recover EXIT
if [[ ! -e $source_dir ]]; then
    install -d "$source_dir"
    created_source=true
    install -m 0644 "$here/kernel/"{hid-oxp.c,hid-ids.h,Makefile,dkms.conf} "$source_dir/"
fi
if [[ -z $prior_status ]]; then
    created_registration=true
    dkms add -m "$name" -v "$version"
fi
if ! printf '%s\n' "$prior_status" | grep -F "$kernel," | grep -q ': installed'; then
    installed_target=true
    dkms install -m "$name" -v "$version" -k "$kernel"
fi
depmod -a "$kernel"
resolved=$(modinfo -k "$kernel" -n hid_oxp)
[[ $resolved == "$modules/updates/dkms/"* || $resolved == /lib/modules/"$kernel"/updates/dkms/* ]] || die "DKMS override is not selected: $resolved"
printf '%s\n' "$resolved" > "$backup/module-path-installed"
if $installed_target; then refresh_initramfs; fi
bash "$here/inputplumber/install.sh"
if [[ -r /var/lib/oxp3-fixes/inputplumber/latest-backup ]]; then
    ip_current=$(cat /var/lib/oxp3-fixes/inputplumber/latest-backup)
    if [[ $ip_current != "$ip_previous" ]]; then
        ip_installed=$ip_current
        printf '%s\n' "$ip_installed" > "$backup/inputplumber-backup"
    fi
fi
printf '%s\n' "$created_source" > "$backup/created-source"
printf '%s\n' "$installed_target" > "$backup/installed-target"
printf '%s\n' "$created_registration" > "$backup/created-registration"
printf '%s\n' completed > "$backup/install-status"
printf '%s\n' "$backup" > "$state/latest-backup"
trap - EXIT
printf 'Installed controller support for %s. Backup: %s\n' "$kernel" "$backup"
printf 'Restart the handheld to load the driver. Rollback: sudo bash %q %q\n' "$here/rollback.sh" "$backup"
