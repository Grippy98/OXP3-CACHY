#!/usr/bin/env bash
set -euo pipefail
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
source "$here/../../scripts/lib.sh"
oxp3_require_root
oxp3_require_platform
state=/var/lib/oxp3-cachy/power-button
[[ -f $state/baseline.json ]] || { echo 'No installer baseline; nothing removed.'; exit 0; }
mapfile -t baseline < <(python3 - "$state/baseline.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert isinstance(d['preexisting'],bool)
print(int(d['preexisting'])); print(d['previous_active']); print(d['session_user']); print(d['installed_version'])
PY
)
[[ ${#baseline[@]} == 4 ]] || { echo 'Invalid baseline; refusing rollback.' >&2; exit 1; }
export OXP3_SESSION_USER=${baseline[2]}
oxp3_session_user >/dev/null
if [[ ${baseline[0]} == 1 ]]; then
    if [[ ${baseline[1]} == active ]]; then
        if oxp3_as_session systemctl --user is-active --quiet gamescope-session.service; then
            oxp3_as_session systemctl --user start steamos-powerbuttond.service
        fi
    else
        oxp3_as_session systemctl --user stop steamos-powerbuttond.service
    fi
    echo 'Kept the preexisting package and restored its previous session activity.'
elif installed_version=$(pacman -Q steamos-powerbuttond 2>/dev/null); then
    [[ $installed_version == "${baseline[3]}" ]] || {
        echo 'Package version changed since installation; keep it and review manual removal.' >&2; exit 1;
    }
    was_active=$(oxp3_as_session systemctl --user is-active steamos-powerbuttond.service 2>/dev/null || true)
    oxp3_as_session systemctl --user stop steamos-powerbuttond.service || true
    if ! pacman -R steamos-powerbuttond; then
        if [[ $was_active == active ]]; then
            oxp3_as_session systemctl --user start steamos-powerbuttond.service || true
        fi
        echo 'Package removal did not complete; baseline retained.' >&2
        exit 1
    fi
fi
systemd-hwdb update
udevadm control --reload
mv "$state/baseline.json" "$state/last-rollback.json"
echo 'Power-button rollback completed. No reboot was requested.'
