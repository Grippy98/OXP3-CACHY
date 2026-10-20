#!/usr/bin/env bash
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
die() { printf 'Error: %s\n' "$*" >&2; exit 1; }
usage() { printf 'Usage: bash install.sh --check | BUILT_EFI [EXPECTED_SHA256]\n'; }
if [[ ${1:-} == --help ]]; then usage; exit 0; fi
if [[ ${1:-} == --check ]]; then
    [[ $# == 1 ]] || { usage >&2; exit 2; }
    [[ $(uname -s) == Linux ]] || die 'Run on the ONEXPLAYER 3 Linux handheld.'
    [[ -r /sys/class/dmi/id/product_name && -r /sys/class/dmi/id/sys_vendor ]] || die 'Cannot read DMI identity.'
    [[ $(cat /sys/class/dmi/id/product_name) == 'ONEXPLAYER 3' &&
       $(cat /sys/class/dmi/id/sys_vendor) == ONE-NETBOOK ]] || die 'Requires ONE-NETBOOK ONEXPLAYER 3.'
    for dependency in efibootmgr findmnt lsblk python3 sha256sum install flock readlink od; do
        command -v "$dependency" >/dev/null || die "Missing command: $dependency"
    done
    [[ -d /sys/firmware/efi ]] || die 'Requires a UEFI boot.'
    [[ $(findmnt -n -o FSTYPE --mountpoint /boot) == vfat ]] || die '/boot must be the mounted FAT ESP.'
    [[ -s /boot/limine.conf && -s /boot/EFI/limine/limine_x64.efi ]] || die 'Stock CachyOS Limine files are missing.'
    printf 'CachyOS Limine layout and tools found. Install also validates the supplied x86-64 EFI image and Secure Boot state.\n'
    exit 0
fi
[[ $# -ge 1 && $# -le 2 ]] || { usage >&2; exit 2; }
exec bash "$here/install-experimental.sh" "$@"
