#!/usr/bin/env bash
# Compile an opt-in guarded fixed-refresh lead experiment in a NEW user directory; do not install or run it.
set -euo pipefail
work_dir=${1:?Pass a NEW user-owned Linux build directory}
jobs=${JOBS:-4}
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ $(uname -s) == Linux ]]
[[ ! -e "$work_dir" ]]
[[ "$jobs" =~ ^[1-9][0-9]*$ ]]
patch_file=$script_dir/combined-diagnostic-lead-guard-and-expiration.patch
[[ $(sha256sum -- "$patch_file" | cut -d ' ' -f 1) == fa7360821887d2b9b46e90b5ac5a24573ff75565f5138dcd0e81bae4fd9040f4 ]]
for tool in git meson ninja cmake pkg-config gcc g++ glslangValidator wayland-scanner python3; do
    command -v "$tool" >/dev/null
done
pkg-config --exists wayland-protocols catch2-with-main libdrm vulkan \
    wayland-client wayland-server libpipewire-0.3 libinput libseat \
    libavif libeis-1.0 libdecor-0 libcap luajit pixman-1
mkdir -p -- "$work_dir"
work_dir=$(cd -- "$work_dir" && pwd)
git clone --depth=1 --branch 3.16.25 https://github.com/ValveSoftware/gamescope.git \
    "$work_dir/source" > "$work_dir/clone.log" 2>&1
cd -- "$work_dir/source"
[[ $(git rev-parse HEAD) == 17baf4abd1ab3353fb705e4d0d023f84e870f7e8 ]]
git diff --exit-code > "$work_dir/stock-base-check.txt"
git apply --check "$patch_file"
git apply "$patch_file"
git diff --check
git diff > "$work_dir/applied.diff"
GIT_TERMINAL_PROMPT=0 git submodule update --init --recursive --depth=1 --jobs=4 \
    > "$work_dir/submodules.log" 2>&1
git submodule foreach --recursive 'test "$(git rev-parse HEAD)" = "$sha1"' \
    > "$work_dir/submodule-pin-check.txt"
git submodule status --recursive > "$work_dir/submodule-pins.txt"
meson subprojects download > "$work_dir/wrap-download.log" 2>&1
[[ $(git -C subprojects/glm rev-parse HEAD) == 0af55ccecd98d4e5a8d1fad7de25ba429d60e863 ]]
[[ $(git -C subprojects/stb rev-parse HEAD) == 5736b15f7ea0ffb08dd38af21067c314d6a3aae9 ]]
meson setup build --prefix=/opt/onex3/gamescope --libdir=lib --buildtype=release \
    -Ddrm_backend=enabled -Dpipewire=enabled -Drt_cap=enabled \
    -Dsdl2_backend=enabled -Davif_screenshots=enabled -Dinput_emulation=enabled \
    -Denable_openvr_support=true -Denable_gamescope_wsi_layer=true \
    -Denable_tests=true -Dbenchmark=disabled --wrap-mode=nodownload \
    > "$work_dir/configure.log" 2>&1
meson introspect build --buildoptions > "$work_dir/build-options.json"
nice -n 10 ninja -C build -j"$jobs" > "$work_dir/build.log" 2>&1
meson test -C build --no-rebuild --print-errorlogs > "$work_dir/tests.log" 2>&1
python3 "$script_dir/../stage.py" "$work_dir/source" "$work_dir/stage"
printf 'Accepted runtime source built and staged in %s/stage; no installation or session change.\n' "$work_dir"
