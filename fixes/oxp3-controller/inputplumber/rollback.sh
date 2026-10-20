#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Restore the three administrator overrides and previous service state.
set -euo pipefail

if [[ ${1:-} == --help ]]; then
    echo "Usage: sudo bash rollback.sh /var/lib/oxp3-fixes/inputplumber/BACKUP [--force]"
    echo "Restores saved files and service state. --force permits replacing later edits."
    exit 0
fi
if (($# < 1 || $# > 2)) || [[ ${2:-} != '' && ${2:-} != --force ]]; then
    echo "Usage: sudo bash rollback.sh BACKUP [--force]" >&2
    exit 2
fi
if [[ $(uname -s) != Linux || $EUID != 0 ]]; then
    echo "Run this script as root on the Linux device." >&2
    exit 1
fi
backup=$(readlink -f -- "$1")
if [[ ! -f "$backup/format" || $(cat "$backup/format") != oxp3-inputplumber-backup-v1 ]]; then
    echo "Not an OXP3 InputPlumber backup: $backup" >&2
    exit 1
fi
enabled_state=$(cat "$backup/service-enabled")
active_state=$(cat "$backup/service-active")
case "$enabled_state" in
    enabled|enabled-runtime|disabled) ;;
    *) echo "Unrecognized saved service state." >&2; exit 1 ;;
esac
files=(
    etc/inputplumber/devices.d/50-onexplayer_3.yaml
    etc/inputplumber/capability_maps.d/onexplayer_type9.yaml
    etc/udev/hwdb.d/61-onexplayer3-inputplumber-autostart.hwdb
)
for file in "${files[@]}"; do
    [[ -f "$backup/installed/$file" ]] || { echo "Incomplete backup: $file" >&2; exit 1; }
    if [[ ${2:-} != --force ]]; then
        if [[ ! -f /$file || -L /$file ]] || ! cmp -s -- "/$file" "$backup/installed/$file"; then
            echo "Current file differs from this installation: /$file" >&2
            echo "Save later edits before retrying with --force." >&2
            exit 1
        fi
    fi
    if grep -Fxq -- "$file" "$backup/previous-present"; then
        [[ -e "$backup/previous/$file" || -L "$backup/previous/$file" ]] || {
            echo "Missing previous file in backup: $file" >&2
            exit 1
        }
    fi
done
systemctl stop inputplumber.service
for file in "${files[@]}"; do
    rm -f -- "/$file"
    if grep -Fxq -- "$file" "$backup/previous-present"; then
        install -d -m 0755 "/$(dirname "$file")"
        cp -a -- "$backup/previous/$file" "/$file"
    fi
done
systemd-hwdb update
systemctl disable inputplumber.service
case "$enabled_state" in
    enabled) systemctl enable inputplumber.service ;;
    enabled-runtime) systemctl enable --runtime inputplumber.service ;;
esac
if [[ $active_state == active ]]; then
    systemctl start inputplumber.service
fi
printf '%s\n' rolled-back > "$backup/install-status"
echo "Restored prior files and service enablement. Prior active state: $active_state."
echo "InputPlumber remains installed; this script does not remove packages or kernel modules."
