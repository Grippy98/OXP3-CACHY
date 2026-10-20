#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Install the tested ONEXPLAYER 3 administrator overrides.
set -eEuo pipefail

if [[ ${1:-} == --help ]]; then
    echo "Usage: sudo bash install.sh"
    echo "Requires the InputPlumber package. Saves a backup and enables the service."
    exit 0
fi
if (($#)); then
    echo "Usage: sudo bash install.sh" >&2
    exit 2
fi
if [[ $(uname -s) != Linux || $EUID != 0 ]]; then
    echo "Run this script as root on the ONEXPLAYER 3 Linux device." >&2
    exit 1
fi
if [[ $(cat /sys/class/dmi/id/sys_vendor) != ONE-NETBOOK ||
      $(cat /sys/class/dmi/id/product_name) != 'ONEXPLAYER 3' ]]; then
    echo "This configuration matches ONE-NETBOOK / ONEXPLAYER 3 only." >&2
    exit 1
fi
for command in inputplumber systemctl systemd-hwdb install cp mktemp rm date; do
    if ! command -v "$command" >/dev/null; then
        echo "Missing command: $command. Install InputPlumber first: sudo pacman -S inputplumber" >&2
        exit 1
    fi
done
systemctl cat inputplumber.service >/dev/null
bundle_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
files=(
    etc/inputplumber/devices.d/50-onexplayer_3.yaml
    etc/inputplumber/capability_maps.d/onexplayer_type9.yaml
    etc/udev/hwdb.d/61-onexplayer3-inputplumber-autostart.hwdb
)
for file in "${files[@]}"; do
    [[ -f "$bundle_dir/local-config/$file" ]] || {
        echo "Missing bundle file: $file" >&2
        exit 1
    }
done
enabled_state=$(systemctl is-enabled inputplumber.service 2>/dev/null || true)
case "$enabled_state" in
    enabled|enabled-runtime|disabled) ;;
    *) echo "Unsupported existing service state: $enabled_state. No changes made." >&2; exit 1 ;;
esac
active_state=$(systemctl is-active inputplumber.service 2>/dev/null || true)
already_installed=true
for file in "${files[@]}"; do
    if [[ ! -f /$file || -L /$file ]] || ! cmp -s "$bundle_dir/local-config/$file" "/$file"; then
        already_installed=false
    fi
done
if $already_installed && [[ $enabled_state == enabled && $active_state == active ]]; then
    echo 'The matching InputPlumber overrides are already installed and active; no changes made.'
    exit 0
fi
state_dir=/var/lib/oxp3-fixes/inputplumber
install -d -m 0700 "$state_dir"
backup=$(mktemp -d "$state_dir/$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
printf '%s\n' "$enabled_state" > "$backup/service-enabled"
printf '%s\n' "$active_state" > "$backup/service-active"
for file in "${files[@]}"; do
    install -d -m 0700 "$backup/previous/$(dirname "$file")" "$backup/installed/$(dirname "$file")"
    if [[ -e /$file || -L /$file ]]; then
        cp -a -- "/$file" "$backup/previous/$file"
        printf '%s\n' "$file" >> "$backup/previous-present"
    fi
    cp -- "$bundle_dir/local-config/$file" "$backup/installed/$file"
done
touch "$backup/previous-present"
printf '%s\n' 'oxp3-inputplumber-backup-v1' > "$backup/format"
echo "Backup: $backup"

restore_after_error() {
    local status=$?
    trap - ERR
    echo "Installation failed; restoring the previous configuration from $backup." >&2
    if ! bash "$bundle_dir/rollback.sh" "$backup" --force; then
        echo "Automatic rollback failed. Retry: sudo bash '$bundle_dir/rollback.sh' '$backup' --force" >&2
    fi
    exit "$status"
}
trap restore_after_error ERR
for file in "${files[@]}"; do
    install -d -m 0755 "/$(dirname "$file")"
    # Replace an existing symlink instead of writing through its target.
    rm -f -- "/$file"
    install -m 0644 "$bundle_dir/local-config/$file" "/$file"
done
systemd-hwdb update
systemctl enable inputplumber.service
systemctl restart inputplumber.service
systemctl is-active --quiet inputplumber.service
trap - ERR
printf '%s\n' completed > "$backup/install-status"
printf '%s\n' "$backup" > "$state_dir/latest-backup"
echo "Installed and active. Physical button testing is still required on this installation."
echo "Rollback: sudo bash '$bundle_dir/rollback.sh' '$backup'"
