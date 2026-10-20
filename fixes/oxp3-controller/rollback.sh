#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail
die() { printf 'Error: %s\n' "$*" >&2; exit 1; }
[[ ${1:-} != --help ]] || { printf 'Usage: sudo bash rollback.sh BACKUP_DIRECTORY\n'; exit 0; }
[[ $# == 1 && $EUID == 0 && $(uname -s) == Linux ]] || die 'Usage: sudo bash rollback.sh BACKUP_DIRECTORY'
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
backup=$(readlink -f -- "$1")
[[ $backup == /var/lib/oxp3-fixes/controllers/* && -f $backup/format &&
   $(cat "$backup/format") == oxp3-controllers-backup-v1 &&
   $(cat "$backup/install-status") == completed ]] || die 'Select a completed controller installer backup.'
kernel=$(cat "$backup/kernel")
[[ $kernel =~ ^[[:alnum:]_.+-]+$ ]] || die 'Invalid saved kernel release.'
exec 200>/run/lock/oxp3-controllers.lock
flock --timeout=10 200 || die 'Another controller operation is in progress.'
if [[ -f $backup/inputplumber-backup && ! -f $backup/profile-rolled-back ]]; then
    bash "$here/inputplumber/rollback.sh" "$(cat "$backup/inputplumber-backup")"
    touch "$backup/profile-rolled-back"
fi
if [[ $(cat "$backup/installed-target") == true && ! -f $backup/module-removed ]]; then
    dkms remove -m hid-oxp-onex3 -v 0.1.4396c18 -k "$kernel"
    touch "$backup/module-removed"
fi
remaining=$(dkms status -m hid-oxp-onex3 -v 0.1.4396c18)
if [[ $(cat "$backup/created-registration") == true ]] && ! printf '%s\n' "$remaining" | grep -q ', '; then
    [[ -z $remaining ]] || dkms remove -m hid-oxp-onex3 -v 0.1.4396c18 --all
    if [[ $(cat "$backup/created-source") == true ]]; then rm -rf -- /usr/src/hid-oxp-onex3-0.1.4396c18; fi
fi
depmod -a "$kernel"
if command -v limine-mkinitcpio >/dev/null; then limine-mkinitcpio; else mkinitcpio -P; fi
printf '%s\n' rolled-back > "$backup/install-status"
printf 'Restored prior controller setup for %s. Reboot to activate it. Backup: %s\n' "$kernel" "$backup"
printf 'Dependency packages remain installed.\n'
