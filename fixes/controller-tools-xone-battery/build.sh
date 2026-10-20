#!/usr/bin/env bash
# Build source only; never installs software or restarts Steam/Decky.
set -euo pipefail
fix_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_dir=$(cd -- "$fix_dir/../.." && pwd)
work_dir=${OXP3_CONTROLLER_TOOLS_BUILD_DIR:-"$repo_dir/build/controller-tools-xone-battery"}
pin=dcc05d953679c30b81ea3fb94a920af42fa3b44e
if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then
    echo 'Use an x86_64 Linux build environment (or the documented cross-build recipe).' >&2
    exit 1
fi
for tool in git cargo rustc node pnpm pkg-config cc; do
    command -v "$tool" >/dev/null || { echo "Missing build tool: $tool" >&2; exit 1; }
done
pkg-config --exists libudev || { echo 'Missing libudev development files.' >&2; exit 1; }
node -e 'const [major,minor]=process.versions.node.split(".").map(Number); if (major < 22 || (major === 22 && minor < 6)) process.exit(1)' || {
    echo 'Use Node 22.6 or newer for the source tests.' >&2; exit 1;
}
if [[ -e $work_dir ]]; then
    echo "Refusing to replace existing build directory: $work_dir" >&2
    echo 'Choose a fresh OXP3_CONTROLLER_TOOLS_BUILD_DIR or retain/move the previous build.' >&2
    exit 1
fi
mkdir -p -- "$work_dir"
git clone --no-checkout https://github.com/jfernandez/ControllerTools.git "$work_dir/source"
git -C "$work_dir/source" checkout --detach "$pin"
git -C "$work_dir/source" apply --check "$fix_dir/patches/0001-xone-wireless-battery.patch"
git -C "$work_dir/source" apply "$fix_dir/patches/0001-xone-wireless-battery.patch"
cd -- "$work_dir/source"
pnpm install --frozen-lockfile --ignore-scripts
pnpm exec tsc --noEmit
pnpm run build
node --experimental-strip-types --test tests/*.test.mjs
# This pinned upstream settings test already fails: its implementation does not
# create/write the file the test assumes. Keep that unrelated failure explicit.
cargo test --manifest-path backend/Cargo.toml --release --locked -- --skip settings::test::test_settings
cargo build --manifest-path backend/Cargo.toml --release --locked
payload="$work_dir/package/ControllerTools"
mkdir -p -- "$payload/bin" "$payload/dist"
cp -- main.py plugin.json package.json README.md LICENSE.md "$payload/"
install -m 755 backend/target/release/controller-tools "$payload/bin/backend"
install -m 644 dist/index.js dist/index.js.map "$payload/dist/"
printf 'Built payload: %s\nNo plugin has been installed. Follow the README for backup, deployment and reload.\n' "$payload"
