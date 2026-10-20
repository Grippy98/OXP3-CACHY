#!/usr/bin/env bash
set -euo pipefail

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }
[[ $EUID == 0 ]] || die 'Run this script with sudo.'
for command in efibootmgr findmnt flock python3 sha256sum install; do
    command -v "$command" >/dev/null || die "Missing command: $command"
done
helper=$(dirname -- "$(readlink -f -- "$0")")/controller-state.py
[[ -r $helper ]] || die 'The adjacent controller-state.py helper is missing.'
[[ $(findmnt -n -o FSTYPE --mountpoint /boot) == vfat ]] || die '/boot must be the mounted FAT EFI system partition.'
partuuid=$(findmnt -n -o PARTUUID --mountpoint /boot)
[[ $partuuid =~ ^[[:xdigit:]]{8}-[[:xdigit:]]{4}-[[:xdigit:]]{4}-[[:xdigit:]]{4}-[[:xdigit:]]{12}$ ]] || die 'Cannot identify the EFI partition UUID.'
secure_boot_file=/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c
[[ -r $secure_boot_file ]] || die 'Cannot determine Secure Boot state.'
[[ $(od -An -t u1 -j 4 -N 1 "$secure_boot_file" | tr -d '[:space:]') == 0 ]] || die 'This unsigned application requires Secure Boot to be disabled.'

installation=/var/lib/onex3-boot-controller/experimental
promotion=/var/lib/onex3-boot-controller/promoted
experiment=/boot/EFI/limine-oxp3-controller
config=/boot/limine.conf
stock_efi=/boot/EFI/limine/limine_x64.efi
[[ -r $installation/entry-id && -r $installation/efi-sha256 ]] || die 'The recorded experimental installation is missing.'
entry=$(cat "$installation/entry-id")
[[ $entry =~ ^[[:xdigit:]]{4}$ ]] || die 'The recorded EFI entry is invalid.'
entry=${entry^^}
[[ ! -e $promotion ]] || die 'The controller loader is already promoted; roll it back before another promotion.'
[[ -s $stock_efi && -s $config && -s $experiment/BOOTX64.EFI ]] || die 'A required stock or experimental boot file is missing.'
[[ ! -e $experiment/limine.conf || -f $experiment/limine.conf ]] || die 'The experimental sibling configuration is not a regular file.'
[[ $(sha256sum -- "$experiment/BOOTX64.EFI" | cut -d ' ' -f 1) == "$(cat "$installation/efi-sha256")" ]] || die 'The experimental EFI application has changed since installation.'
for shadow in /boot/boot/limine/limine.conf /boot/boot/limine.conf /boot/limine/limine.conf; do
    [[ ! -e $shadow ]] || die "This higher-priority configuration would shadow the live main file: $shadow"
done

install -d /run/lock
exec 200>/run/lock/boot-partition.lock
flock --timeout=10 200 || die 'Another CachyOS boot update is in progress.'
backup=/var/lib/onex3-boot-controller/backups/promotion-$(date -u +%Y%m%dT%H%M%SZ)-$$
install -d -m 700 "$backup"
efibootmgr -v > "$backup/efibootmgr-before.txt"
stock_entry=$(python3 "$helper" find-stock "$backup/efibootmgr-before.txt" "$partuuid")
[[ $entry != "$stock_entry" ]] || die 'The experimental and stock EFI entries must differ.'
mapfile -t orders < <(python3 "$helper" boot-plan promote "$backup/efibootmgr-before.txt" "$entry" "$stock_entry" "$partuuid")
[[ ${#orders[@]} == 2 ]] || die 'EFI entry verification failed.'
before_order=${orders[0]}
desired_order=${orders[1]}
cp -a -- "$config" "$backup/main-limine.conf"
if [[ -f $experiment/limine.conf ]]; then
    cp -a -- "$experiment/limine.conf" "$backup/experimental-limine.conf"
fi
stock_sha=$(sha256sum -- "$stock_efi" | cut -d ' ' -f 1)
install -d -m 700 "$promotion"
printf '%s\n' "$backup" > "$promotion/backup-path"
printf '%s\n' "$entry" > "$promotion/entry-id"
printf '%s\n' "$stock_entry" > "$promotion/stock-entry-id"
config_changed=false
sibling_removed=false
order_attempted=false
cleanup() {
    result=$?
    if (( result != 0 )); then
        recovery_failed=false
        if $order_attempted; then
            if current_order=$(efibootmgr | awk '/^BootOrder:/ {print toupper($2)}'); then
                if [[ $current_order == "$desired_order" ]]; then
                    efibootmgr --bootorder "$before_order" || recovery_failed=true
                elif [[ $current_order != "$before_order" ]]; then
                    recovery_failed=true
                fi
            else
                recovery_failed=true
            fi
        fi
        if $config_changed; then
            install -m 644 "$backup/main-limine.conf" "$config.restore.tmp" && mv -f -- "$config.restore.tmp" "$config" || recovery_failed=true
        fi
        if $sibling_removed; then
            install -m 644 "$backup/experimental-limine.conf" "$experiment/limine.conf" || recovery_failed=true
        fi
        if $recovery_failed; then
            touch "$promotion/incomplete"
            printf 'Automatic recovery was incomplete; promotion state was retained. Stock firmware entry: Boot%s.\n' "$stock_entry" >&2
        else
            rm -rf -- "$promotion"
        fi
        sync
        printf 'Promotion stopped. Inspect the saved boot state at %s.\n' "$backup" >&2
    fi
}
trap cleanup EXIT

config_changed=true
python3 "$helper" enable-config "$config" "$backup/config-settings-before.json"
cp -a -- "$backup/config-settings-before.json" "$promotion/config-settings-before.json"
if [[ -f $experiment/limine.conf ]]; then
    sibling_removed=true
    rm -- "$experiment/limine.conf"
fi
sync -f "$config"
sync -f "$experiment/BOOTX64.EFI"
order_attempted=true
efibootmgr --bootorder "$desired_order"
efibootmgr -v > "$backup/efibootmgr-after.txt"
[[ $(awk '/^BootOrder:/ {print toupper($2)}' "$backup/efibootmgr-after.txt") == "$desired_order" ]] || die 'Firmware did not retain the requested BootOrder.'
[[ ! -e $experiment/limine.conf ]] || die 'The obsolete experimental configuration was recreated unexpectedly.'
[[ $(sha256sum -- "$stock_efi" | cut -d ' ' -f 1) == "$stock_sha" ]] || die 'The stock EFI application changed unexpectedly.'
touch "$promotion/complete"
sync
trap - EXIT
printf 'Controller-enabled Limine is now first in BootOrder (%s). Stock Boot%s remains available.\n' "$desired_order" "$stock_entry"
printf 'It uses the live /boot/limine.conf, including future kernel entries and the existing timeout.\n'
printf 'No reboot was requested. Promotion backups: %s\n' "$backup"
