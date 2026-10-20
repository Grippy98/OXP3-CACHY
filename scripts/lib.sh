#!/usr/bin/env bash
# Shared checks for the collection's small native-package adapters.
oxp3_require_root() { [[ $EUID == 0 ]] || { echo 'Run through ./install.sh or with sudo.' >&2; exit 1; }; }
oxp3_require_platform() {
    [[ $(uname -s) == Linux ]] || { echo 'Linux is required.' >&2; exit 1; }
    [[ $(cat /sys/class/dmi/id/product_name) == 'ONEXPLAYER 3' ]] || { echo 'Intel ONEXPLAYER 3 required.' >&2; exit 1; }
    grep -q GenuineIntel /proc/cpuinfo || { echo 'Intel CPU required.' >&2; exit 1; }
    command -v pacman >/dev/null || { echo 'CachyOS/Arch with pacman required.' >&2; exit 1; }
}
oxp3_session_user() {
    local name=${OXP3_SESSION_USER:-${SUDO_USER:-}}
    [[ -n $name && $name != root ]] || { echo 'Run from the logged-in Gaming Mode user.' >&2; return 1; }
    id "$name" >/dev/null
    printf '%s\n' "$name"
}
oxp3_as_session() {
    local name uid
    name=$(oxp3_session_user)
    uid=$(id -u "$name")
    runuser -u "$name" -- env XDG_RUNTIME_DIR="/run/user/$uid" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" "$@"
}
