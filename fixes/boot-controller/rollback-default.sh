#!/usr/bin/env bash
set -euo pipefail

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }
[[ $EUID == 0 ]] || die 'Run this script with sudo.'
for command in efibootmgr findmnt flock python3; do
    command -v "$command" >/dev/null || die "Missing command: $command"
done
helper=$(dirname -- "$(readlink -f -- "$0")")/controller-state.py
[[ -r $helper ]] || die 'The adjacent controller-state.py helper is missing.'
[[ $(findmnt -n -o FSTYPE --mountpoint /boot) == vfat ]] || die '/boot must be the mounted FAT EFI system partition.'
partuuid=$(findmnt -n -o PARTUUID --mountpoint /boot)
[[ $partuuid =~ ^[[:xdigit:]]{8}-[[:xdigit:]]{4}-[[:xdigit:]]{4}-[[:xdigit:]]{4}-[[:xdigit:]]{12}$ ]] || die 'Cannot identify the EFI partition UUID.'
promotion=/var/lib/onex3-boot-controller/promoted
[[ -r $promotion/entry-id && -r $promotion/stock-entry-id && -r $promotion/config-settings-before.json && -r $promotion/backup-path ]] || die 'No promotion state was found.'
entry=$(cat "$promotion/entry-id")
stock_entry=$(cat "$promotion/stock-entry-id")
[[ $entry =~ ^[[:xdigit:]]{4}$ && $stock_entry =~ ^[[:xdigit:]]{4}$ && ${entry^^} != "${stock_entry^^}" ]] || die 'Invalid saved EFI entry IDs.'
entry=${entry^^}
stock_entry=${stock_entry^^}
backup=$(cat "$promotion/backup-path")
[[ $backup == /var/lib/onex3-boot-controller/backups/promotion-* && -d $backup ]] || die 'The promotion backup directory is missing or unexpected.'
install -d /run/lock
exec 200>/run/lock/boot-partition.lock
flock --timeout=10 200 || die 'Another CachyOS boot update is in progress.'
efibootmgr -v > "$backup/efibootmgr-before-rollback.txt"
mapfile -t orders < <(python3 "$helper" boot-plan rollback "$backup/efibootmgr-before-rollback.txt" "$entry" "$stock_entry" "$partuuid")
[[ ${#orders[@]} == 2 ]] || die 'EFI entry verification failed.'
desired_order=${orders[1]}
next_entry=$(awk '/^BootNext:/ {print toupper($2)}' "$backup/efibootmgr-before-rollback.txt")
if [[ $next_entry == "$entry" ]]; then
    efibootmgr --delete-bootnext
fi
efibootmgr --bootorder "$desired_order"
efibootmgr -v > "$backup/efibootmgr-after-rollback.txt"
[[ $(awk '/^BootOrder:/ {print toupper($2)}' "$backup/efibootmgr-after-rollback.txt") == "$desired_order" ]] || die 'Firmware did not retain the stock-first BootOrder.'
python3 "$helper" restore-config /boot/limine.conf "$promotion/config-settings-before.json"
rm -rf -- "$promotion"
sync
printf 'Stock Boot%s is first again. Newer kernel entries and unrelated firmware entries were preserved.\n' "$stock_entry"
printf 'The custom EFI remains installed for opt-in testing. To remove it, now run rollback-experimental.sh.\n'
printf 'Promotion backups remain at %s. No reboot was requested.\n' "$backup"
