#!/usr/bin/env bash
set -euo pipefail

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

[[ $EUID == 0 ]] || die 'Run this script with sudo.'
[[ $# -ge 1 && $# -le 2 ]] || die 'Usage: install-experimental.sh BUILT_EFI [EXPECTED_SHA256]'
for command in efibootmgr findmnt lsblk python3 sha256sum install flock readlink od; do
    command -v "$command" >/dev/null || die "Missing command: $command"
done

efi_source=$(readlink -f -- "$1")
[[ -f $efi_source && -s $efi_source ]] || die 'The built EFI application is missing or empty.'
actual_sha=$(sha256sum -- "$efi_source" | cut -d ' ' -f 1)
expected_sha=${2:-}
if [[ -n $expected_sha ]]; then
    [[ $expected_sha =~ ^[[:xdigit:]]{64}$ ]] || die 'EXPECTED_SHA256 must contain 64 hexadecimal characters.'
    [[ ${expected_sha,,} == "$actual_sha" ]] || die 'The supplied SHA256 does not match the EFI application.'
fi
checksum_file=$1.sha256
if [[ -f $checksum_file ]]; then
    read -r expected_sha _ < "$checksum_file"
    [[ $expected_sha =~ ^[[:xdigit:]]{64}$ ]] || die 'The adjacent .sha256 file is invalid.'
    [[ ${expected_sha,,} == "$actual_sha" ]] || die 'The adjacent checksum does not match the EFI application.'
fi

[[ -d /sys/firmware/efi ]] || die 'This installer requires a UEFI boot.'
[[ -r /sys/class/dmi/id/sys_vendor && -r /sys/class/dmi/id/product_name ]] || die 'Cannot identify the machine through DMI.'
dmi_vendor=$(tr -cd '[:alnum:]' < /sys/class/dmi/id/sys_vendor | tr '[:lower:]' '[:upper:]')
dmi_product=$(tr -cd '[:alnum:]' < /sys/class/dmi/id/product_name | tr '[:lower:]' '[:upper:]')
[[ $dmi_vendor == ONENETBOOK && $dmi_product == ONEXPLAYER3 ]] || die 'This bundle is restricted to ONE-NETBOOK ONEXPLAYER 3.'
secure_boot_file=/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c
[[ -r $secure_boot_file ]] || die 'Cannot determine Secure Boot state.'
[[ $(od -An -t u1 -j 4 -N 1 "$secure_boot_file" | tr -d '[:space:]') == 0 ]] || die 'This unsigned experimental application requires Secure Boot to be disabled.'

esp=/boot
[[ $(findmnt -n -o FSTYPE --mountpoint "$esp") == vfat ]] || die '/boot must be the mounted FAT EFI system partition.'
esp_device=$(readlink -f -- "$(findmnt -n -o SOURCE --mountpoint "$esp")")
[[ $(lsblk -n -d -o TYPE "$esp_device") == part ]] || die 'Cannot identify the EFI partition.'
disk_name=$(lsblk -n -d -o PKNAME "$esp_device")
partition=$(cat "/sys/class/block/${esp_device##*/}/partition")
[[ -n $disk_name && $partition =~ ^[0-9]+$ ]] || die 'Cannot identify the EFI partition disk and number.'
disk=/dev/$disk_name

stock_efi=$esp/EFI/limine/limine_x64.efi
stock_config=$esp/limine.conf
experiment=$esp/EFI/limine-oxp3-controller
efi_loader='\EFI\limine-oxp3-controller\BOOTX64.EFI'
entry_label='ONEXPLAYER 3 controller test'
state=/var/lib/onex3-boot-controller/experimental
[[ -s $stock_efi && -s $stock_config ]] || die 'The stock CachyOS Limine files were not found.'
install -d /run/lock
exec 200>/run/lock/boot-partition.lock
flock --timeout=10 200 || die 'Another boot update is in progress.'
if [[ -d $state && -f $state/efi-sha256 && -f $state/entry-id ]]; then
    if [[ $(cat "$state/efi-sha256") == "$actual_sha" && -s $experiment/BOOTX64.EFI &&
          $(sha256sum -- "$experiment/BOOTX64.EFI" | cut -d ' ' -f 1) == "$actual_sha" ]]; then
        entry=$(cat "$state/entry-id")
        [[ $entry =~ ^[[:xdigit:]]{4}$ ]] || die 'The saved firmware entry ID is invalid.'
        snapshot=$(efibootmgr -v)
        printf '%s\n' "$snapshot" | python3 -c '
import re, sys
entry, loader = sys.argv[1:]
lines = sys.stdin.read().splitlines()
pattern = re.escape(loader.casefold()) + r"(?=$|[)\s])"
if not any(re.match(r"^Boot" + re.escape(entry) + r"\*?\s", line, re.I)
           and re.search(pattern, line.replace("/", "\\").casefold()) for line in lines):
    raise SystemExit("The saved firmware entry is missing or points elsewhere.")
' "$entry" "$efi_loader"
        printf 'This EFI image is already staged as Boot%s. Boot settings are unchanged.\n' "$entry"
        exit 0
    fi
fi
[[ ! -e $experiment && ! -e $state ]] || die 'A different or incomplete installation exists; inspect it and run rollback-experimental.sh first.'

python3 - "$efi_source" "$stock_config" <<'PY'
from pathlib import Path
import re
import struct
import sys

data = Path(sys.argv[1]).read_bytes()
if len(data) < 64 or data[:2] != b'MZ':
    raise SystemExit('The supplied file is not a PE EFI application.')
pe = struct.unpack_from('<I', data, 0x3c)[0]
if pe + 96 > len(data) or data[pe:pe + 4] != b'PE\0\0':
    raise SystemExit('The supplied file has no valid PE header.')
if struct.unpack_from('<H', data, pe + 4)[0] != 0x8664:
    raise SystemExit('The EFI application must target x86-64.')
if struct.unpack_from('<H', data, pe + 24 + 68)[0] != 10:
    raise SystemExit('The PE subsystem must be EFI application.')
config = Path(sys.argv[2]).read_text()
if not re.search(r'(?m)^[ \t]*/[^/\r\n]', config):
    raise SystemExit('No Limine menu entries were found in the live configuration.')
PY

backup=/var/lib/onex3-boot-controller/backups/$(date -u +%Y%m%dT%H%M%SZ)-$$
install -d -m 700 "$backup"
cp -a -- "$stock_efi" "$backup/stock-limine_x64.efi"
cp -a -- "$stock_config" "$backup/stock-limine.conf"
efibootmgr -v > "$backup/efibootmgr-before.txt"
before_order=$(awk '/^BootOrder:/ {print $2}' "$backup/efibootmgr-before.txt")
before_next=$(awk '/^BootNext:/ {print $2}' "$backup/efibootmgr-before.txt")
[[ -n $before_order ]] || die 'Cannot read the current firmware BootOrder.'
if python3 - "$backup/efibootmgr-before.txt" "$efi_loader" <<'PY'
from pathlib import Path
import re
import sys

path = sys.argv[2].replace('/', '\\').casefold()
pattern = re.escape(path) + r'(?=$|[)\s])'
found = any(re.match(r'^Boot[0-9A-Fa-f]{4}\*?\s', line)
            and re.search(pattern, line.replace('/', '\\').casefold())
            for line in Path(sys.argv[1]).read_text().splitlines())
raise SystemExit(0 if found else 1)
PY
then
    die 'A firmware entry already references the experimental path; remove that installation first.'
fi
stock_efi_sha=$(sha256sum -- "$stock_efi" | cut -d ' ' -f 1)
stock_config_sha=$(sha256sum -- "$stock_config" | cut -d ' ' -f 1)

install -d -m 700 "$state"
printf '%s\n' "$backup" > "$state/backup-path"
printf '%s\n' "$actual_sha" > "$state/efi-sha256"
created_entry=
staged=false
cleanup() {
    result=$?
    if (( result != 0 )); then
        if [[ -n $created_entry ]]; then
            efibootmgr --bootnum "$created_entry" --delete-bootnum || true
        fi
        if $staged; then
            rm -rf -- "$experiment"
        fi
        rm -rf -- "$state"
        printf 'Installation stopped. Stock backups are retained at %s.\n' "$backup" >&2
    fi
}
trap cleanup EXIT

install -d "$experiment"
staged=true
install -m 644 -- "$efi_source" "$experiment/BOOTX64.EFI"
python3 - "$stock_config" "$experiment/limine.conf" <<'PY'
from pathlib import Path
import re
import sys

text = Path(sys.argv[1]).read_text()
lines = text.splitlines(keepends=True)
first_entry = next((i for i, line in enumerate(lines) if line.lstrip().startswith('/')), len(lines))
global_text = ''.join(lines[:first_entry])
entries = ''.join(lines[first_entry:])
settings = {
    'timeout': 'no',
    'quiet': 'no',
    'gamepad': 'yes',
    'interface_branding': 'ONEXPLAYER 3 - experimental controller menu',
    'remember_last_entry': 'no',
}
for key, value in settings.items():
    pattern = rf'(?mi)^[ \t]*{key}[ \t]*:.*$'
    line = f'{key}: {value}'
    global_text = re.sub(pattern, line, global_text) if re.search(pattern, global_text) else line + '\n' + global_text
Path(sys.argv[2]).write_text(global_text + entries)
PY
chmod 644 "$experiment/limine.conf"
[[ $(sha256sum -- "$experiment/BOOTX64.EFI" | cut -d ' ' -f 1) == "$actual_sha" ]] || die 'The staged EFI checksum does not match.'

efibootmgr --create-only --disk "$disk" --part "$partition" \
    --label "$entry_label" --loader "$efi_loader" > "$backup/efibootmgr-create.txt"
efibootmgr -v > "$backup/efibootmgr-after.txt"
created_entry=$(python3 - "$backup/efibootmgr-before.txt" "$backup/efibootmgr-after.txt" "$efi_loader" "$entry_label" <<'PY'
from pathlib import Path
import re
import sys

before = {entry.upper() for entry in re.findall(r'(?m)^Boot([0-9A-Fa-f]{4})\*?\s', Path(sys.argv[1]).read_text())}
path = sys.argv[3].replace('/', '\\').casefold()
pattern = re.escape(path) + r'(?=$|[)\s])'
matches = []
for line in Path(sys.argv[2]).read_text().splitlines():
    match = re.match(r'^Boot([0-9A-Fa-f]{4})\*?\s', line)
    if (match and match[1].upper() not in before
            and line[match.end():].startswith(sys.argv[4])
            and re.search(pattern, line.replace('/', '\\').casefold())):
        matches.append(match[1].upper())
if len(matches) != 1:
    raise SystemExit('Cannot identify the new experimental firmware entry; inspect the saved efibootmgr output.')
print(matches[0])
PY
)
printf '%s\n' "$created_entry" > "$state/entry-id"
[[ $(awk '/^BootOrder:/ {print $2}' "$backup/efibootmgr-after.txt") == "$before_order" ]] || die 'Firmware BootOrder changed unexpectedly.'
[[ $(awk '/^BootNext:/ {print $2}' "$backup/efibootmgr-after.txt") == "$before_next" ]] || die 'Firmware BootNext changed unexpectedly.'
[[ $(sha256sum -- "$stock_efi" | cut -d ' ' -f 1) == "$stock_efi_sha" ]] || die 'The stock EFI application changed unexpectedly.'
[[ $(sha256sum -- "$stock_config" | cut -d ' ' -f 1) == "$stock_config_sha" ]] || die 'The stock Limine configuration changed unexpectedly.'
sync
trap - EXIT

printf 'Staged controller test as firmware entry %s; current boot settings are unchanged.\n' "$created_entry"
printf 'EFI SHA256: %s\nBackups: %s\n' "$actual_sha" "$backup"
printf 'When ready to test once:\n  sudo efibootmgr --bootnext %s\n  sudo systemctl reboot\n' "$created_entry"
