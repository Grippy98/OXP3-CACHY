#!/usr/bin/env bash
set -euo pipefail

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }
[[ $EUID == 0 ]] || die 'Run this script with sudo.'
for command in efibootmgr findmnt python3 flock sha256sum; do
    command -v "$command" >/dev/null || die "Missing command: $command"
done

state=/var/lib/onex3-boot-controller/experimental
[[ ! -e /var/lib/onex3-boot-controller/promoted ]] || die 'Run rollback-default.sh first to restore the stock default and main configuration.'
experiment=/boot/EFI/limine-oxp3-controller
efi_loader='\EFI\limine-oxp3-controller\BOOTX64.EFI'
[[ $(findmnt -n -o FSTYPE --mountpoint /boot) == vfat ]] || die '/boot must be the mounted FAT EFI system partition.'
[[ -r $state/entry-id && -r $state/efi-sha256 ]] || die 'No recorded experimental installation was found.'
install -d /run/lock
exec 200>/run/lock/boot-partition.lock
flock --timeout=10 200 || die 'Another boot update is in progress.'
if [[ -e $experiment/BOOTX64.EFI ]]; then
    [[ -f $experiment/BOOTX64.EFI && $(sha256sum -- "$experiment/BOOTX64.EFI" | cut -d ' ' -f 1) == "$(cat "$state/efi-sha256")" ]] || die 'The staged EFI image changed after installation; preserve it and inspect before removing.'
fi
entry=$(cat "$state/entry-id")
[[ $entry =~ ^[[:xdigit:]]{4}$ ]] || die 'The recorded firmware entry ID is invalid.'
entry=${entry^^}
backup=$(cat "$state/backup-path")
current=$(efibootmgr -v)

ENTRY_TO_REMOVE="$entry" EXPECTED_LOADER="$efi_loader" CURRENT_EFI_ENTRIES="$current" python3 - <<'PY'
import os
import re

entry = os.environ['ENTRY_TO_REMOVE']
path = os.environ['EXPECTED_LOADER'].replace('/', '\\').casefold()
pattern = re.escape(path) + r'(?=$|[)\s])'
for line in os.environ['CURRENT_EFI_ENTRIES'].splitlines():
    if re.match(rf'^Boot{entry}\*?\s', line, flags=re.I):
        if not re.search(pattern, line.replace('/', '\\').casefold()):
            raise SystemExit('The recorded entry now points elsewhere; refusing to remove it.')
        break
PY

next_entry=$(printf '%s\n' "$current" | awk '/^BootNext:/ {print toupper($2)}')
if [[ $next_entry == "$entry" ]]; then
    efibootmgr --delete-bootnext
fi
if printf '%s\n' "$current" | grep -Eiq "^Boot${entry}\\*?[[:space:]]"; then
    efibootmgr --bootnum "$entry" --delete-bootnum
fi
rm -rf -- "$experiment" "$state"
sync
printf 'Removed the experimental controller entry and files. Stock boot files were not changed.\n'
printf 'Backups remain at %s.\n' "$backup"
