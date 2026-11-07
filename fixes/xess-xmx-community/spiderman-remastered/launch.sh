#!/bin/sh
# Spider-Man only: native XeSS SR, OptiScaler FSRFG -> XeFG, native HDR.
set -eu
if [ "$(id -u)" = 0 ]; then
    echo 'Run Spider-Man as your normal Steam user.' >&2
    exit 2
fi
profile_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
game_dir=${OXP3_SPIDER_GAME:-"$HOME/.local/share/Steam/steamapps/common/Marvel's Spider-Man Remastered"}
package="$HOME/.local/lib/oxp3-xess-community/20261104"
if [ "${OXP3_SPIDER_DEBUG:-0}" != 1 ]; then
    python3 "$profile_dir/quiet-logs.py" "$game_dir/OptiScaler.ini"
fi
export MESA=26.3
export XESS_FG=2
export FFX_XEFG_MULT=2
export VKD3D_DISABLE_EXTENSIONS="${VKD3D_DISABLE_EXTENSIONS:+$VKD3D_DISABLE_EXTENSIONS,}VK_KHR_present_wait2"
exec python3 "$package/launcher.py" --package "$package" -- "$@"
