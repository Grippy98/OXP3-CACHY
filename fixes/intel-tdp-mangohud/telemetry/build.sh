#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
if [[ $# -gt 1 || ${1:-} == --* ]]; then
    echo "Usage: $0 [NEW-BUILD-DIRECTORY]" >&2
    exit 2
fi
for command in git meson ninja pkg-config "${CXX:-c++}" python3; do
    command -v "$command" >/dev/null || { echo "Required build tool missing: $command" >&2; exit 1; }
done
if command -v sha256sum >/dev/null; then
    hash_check=(sha256sum --check --status -)
elif command -v shasum >/dev/null; then
    hash_check=(shasum -a 256 --check --status -)
else
    echo "Required: sha256sum or shasum" >&2
    exit 1
fi
# Verify both independent local patch inputs before creating build output.
printf '%s  %s\n' \
    8533955ee8bee194647c1caba69b0959ec6df72744a6d446b3c51259f9b63e21 \
    "$here/mangohud-intel-telemetry.patch" \
    8ff1195d0b13339628615f0728fcd98177d22a91823e055d55733bb6db44b507 \
    "$here/mangoapp-one-render-per-frame.patch" | "${hash_check[@]}"
out=${1:-"$PWD/mangohud-intel-build"}
if [[ -e "$out" || -L "$out" ]]; then
    echo "Refusing to reuse existing build output: $out" >&2
    exit 1
fi
mkdir -p "$out"
out=$(cd "$out" && pwd)
source_dir="$out/source"
git clone --no-checkout https://github.com/flightlessmango/MangoHud.git "$source_dir"
git -C "$source_dir" checkout --detach 992103e4fb744897826de04ea00a2f71e7018214
git -C "$source_dir" apply --check "$here/mangohud-intel-telemetry.patch"
git -C "$source_dir" apply "$here/mangohud-intel-telemetry.patch"
git -C "$source_dir" apply --check "$here/mangoapp-one-render-per-frame.patch"
git -C "$source_dir" apply "$here/mangoapp-one-render-per-frame.patch"
"$here/tests/run-tests.sh" "$source_dir/src"
meson setup "$out/build" "$source_dir" --prefix=/usr --libdir=lib \
    -Dappend_libdir_mangohud=true -Dwith_xnvctrl=disabled \
    -Dmangoapp=true -Dmangohudctl=true -Dtests=disabled
meson compile -C "$out/build"
DESTDIR="$out/staging" meson install -C "$out/build"
echo "Built files staged under $out/staging; no system files were installed."
