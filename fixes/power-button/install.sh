#!/usr/bin/env bash
set -euo pipefail
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
source "$here/../../scripts/lib.sh"
oxp3_require_platform
if [[ ${1:-} == --check ]]; then
    command -v systemd-hwdb >/dev/null
    command -v udevadm >/dev/null
    if pacman -Q steamos-powerbuttond; then
        echo 'Native package is installed; inspect its user unit in Gaming Mode.'
    else
        echo 'Native steamos-powerbuttond package is needed.'
    fi
    exit 0
fi
[[ $# == 0 ]] || { echo 'Usage: install.sh [--check]' >&2; exit 2; }
oxp3_require_root
session_user=$(oxp3_session_user)
umask 077
state=/var/lib/oxp3-cachy/power-button
install -d -m 0700 "$state"
if [[ -f $state/baseline.json ]]; then
    saved_user=$(python3 - "$state/baseline.json" <<'PY'
import json,sys
print(json.load(open(sys.argv[1]))['session_user'])
PY
)
    [[ $saved_user == "$session_user" ]] || {
        echo 'A different session user owns this baseline; roll it back before changing users.' >&2; exit 1;
    }
fi
preexisting=0
if pacman -Q steamos-powerbuttond >/dev/null 2>&1; then preexisting=1; fi
previous_active=$(oxp3_as_session systemctl --user is-active steamos-powerbuttond.service 2>/dev/null || true)
status=0
pacman -S --needed steamos-powerbuttond || status=$?
if [[ ! -f $state/baseline.json ]] && { [[ $status == 0 ]] || [[ $preexisting == 0 ]]; }; then
    if installed_version=$(pacman -Q steamos-powerbuttond 2>/dev/null); then
        python3 - "$state/baseline.json" "$preexisting" "$previous_active" "$session_user" "$installed_version" <<'PY'
import json,os,sys
from pathlib import Path
p=Path(sys.argv[1]); temporary=p.with_suffix('.tmp')
temporary.write_text(json.dumps({'preexisting':sys.argv[2]=='1', 'previous_active':sys.argv[3],
                                'session_user':sys.argv[4], 'installed_version':sys.argv[5]})+'\n')
os.chmod(temporary,0o600); temporary.replace(p)
PY
    fi
fi
[[ $status == 0 ]] || exit "$status"
systemd-hwdb update
udevadm control --reload
for node in /sys/class/input/event*; do
    if [[ -f $node/device/name && $(cat "$node/device/name") == 'Power Button' ]]; then
        udevadm trigger --action=change "$node"
    fi
done
udevadm settle
oxp3_as_session systemctl --user daemon-reload
if oxp3_as_session systemctl --user is-active --quiet gamescope-session.service; then
    oxp3_as_session systemctl --user restart steamos-powerbuttond.service
    oxp3_as_session systemctl --user --no-pager status steamos-powerbuttond.service
else
    echo 'Configured. The packaged unit starts with the next Gaming Mode session.'
fi
echo 'Test a short power-button press, then wake. No reboot or logind policy change was made.'
