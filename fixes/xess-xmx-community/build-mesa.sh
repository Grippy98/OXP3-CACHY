#!/usr/bin/env bash
# Build a private ANV driver and its pinned runtime helpers; never activate it.
set -euo pipefail

SOURCE_URL=https://github.com/HHHHanasak1/xess-xmx-linux.git
SOURCE_PIN=627566641c360c7a0e5d529898b2a81daef1c7ab
MESA_VERSION=26.3.0-rc1
MESA_URL=https://archive.mesa3d.org/mesa-26.3.0-rc1.tar.xz
MESA_SHA256=63327d58a51d189c1d1600746c505609bba5c495123b4e51de4e0c038b745542

usage() {
  printf 'Usage: %s BUILDDIR PACKAGE\n' "$0"
  printf '%s\n' 'Linux x86-64 only; install the documented build dependencies beforehand.' \
    'Python 3.12+ is required by the pinned runtime kernel packer.' \
    'Both paths must be absolute. BUILDDIR must not exist; its parent must exist.' \
    'Stages the driver, kernel helpers and licenses without overwriting existing files.'
}
die() { printf 'build-mesa: %s\n' "$*" >&2; exit 1; }
if [[ ${1:-} == --help ]]; then usage; exit 0; fi
[[ $# == 2 ]] || { usage >&2; exit 2; }
build=$1
package=$2
for path in "$build" "$package"; do
  [[ $path == /* ]] || die "an absolute path is required: $path"
done
[[ $(uname -s):$(uname -m) == Linux:x86_64 ]] || die 'requires a native Linux x86-64 build environment'
for command in git curl tar patch python3 cc c++ pkg-config meson ninja; do
  command -v "$command" >/dev/null || die "missing prerequisite: $command"
done
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else "Python 3.12+ is required by cmk_pack.py")'
python3 -c 'import mako, yaml, packaging, ply' || die 'missing Python build dependencies (Mako, PyYAML, packaging or PLY)'
[[ ! -e $build && ! -L $build ]] || die "build directory already exists: $build"
python3 - "$package" <<'PY'
from pathlib import Path
import sys

package = Path(sys.argv[1])
for relative in (
    'lib/libvulkan_intel.so', 'tools/cm-compile.sh', 'tools/cmk_pack.py',
    'licenses/community-MIT.txt', 'licenses/dxvk-igdext-MIT.txt',
    'licenses/THIRD_PARTY.md', 'licenses/mesa-license.rst',
):
    target = package / relative
    if target.exists() or target.is_symlink():
        raise SystemExit('Output already exists: ' + str(target))
kernels = package / 'kernels'
if kernels.is_symlink() or (kernels.exists() and not kernels.is_dir()):
    raise SystemExit('kernels must be a real directory: ' + str(kernels))
PY
mkdir -- "$build"
source=$build/community-source
git -c init.templateDir= -c core.hooksPath=/dev/null init --quiet "$source"
git -C "$source" -c core.hooksPath=/dev/null -c fetch.fsckObjects=true \
  fetch --quiet --depth=1 --no-tags "$SOURCE_URL" "$SOURCE_PIN"
[[ $(git -C "$source" rev-parse FETCH_HEAD) == "$SOURCE_PIN" ]] || die 'source commit does not match the pin'
git -C "$source" -c core.hooksPath=/dev/null checkout --quiet --detach "$SOURCE_PIN"
archive=$build/mesa-$MESA_VERSION.tar.xz
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  --output "$archive" "$MESA_URL"
python3 - "$archive" "$MESA_SHA256" <<'PY'
import hashlib
from pathlib import Path
import sys
archive, expected = sys.argv[1:]
with Path(archive).open('rb') as stream:
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(block)
if digest.hexdigest() != expected:
    raise SystemExit('Mesa archive SHA-256 does not match the pin; refusing extraction')
PY
tar -xf "$archive" -C "$build"
mesa=$build/mesa-$MESA_VERSION
[[ -f $mesa/meson.build ]] || die 'the verified archive did not contain the expected source directory'
[[ -f $mesa/docs/license.rst ]] || die 'the verified Mesa archive is missing docs/license.rst'
bash -n "$source/tools/cm-compile.sh"
python3 - "$source/tools/cmk_pack.py" <<'PY'
import ast
from pathlib import Path
import sys
path = Path(sys.argv[1])
ast.parse(path.read_text(), filename=str(path))
PY
for name in \
  0001-anv-cm-kernel-injection.patch \
  0002-anv-cm-debug-tools.patch \
  0003-anv-cm-xe2-large-grf.patch \
  0004-anv-jay-divergent-barriers.patch; do
  patch --batch --forward -p1 -d "$mesa" -i "$source/patches/mesa-26.3/$name"
done

# Match the reviewed ANV-only recipe, including Intel RT and system drirc paths.
# Meson checks the LLVM/SPIR-V, graphics and system-library build dependencies;
# this helper never installs packages or runs a downloaded package manager.
meson setup "$build/mesa-build" "$mesa" \
  -Dprefix=/usr -Dsysconfdir=/etc -Dbuildtype=release \
  -Dvulkan-drivers=intel -Dgallium-drivers= \
  -Dglx=disabled -Dgbm=disabled -Degl=disabled -Dgles1=disabled \
  -Dgles2=disabled -Dopengl=false -Dllvm=enabled -Dintel-rt=enabled \
  -Dvideo-codecs= -Dvulkan-layers= -Dtools=
ninja -C "$build/mesa-build" src/intel/vulkan/libvulkan_intel.so
binary=$build/mesa-build/src/intel/vulkan/libvulkan_intel.so
python3 - "$binary" "$package" "$source" "$mesa" <<'PY'
import hashlib
from pathlib import Path
import shutil
import struct
import sys

binary, package, community, mesa = map(Path, sys.argv[1:])
data = binary.read_bytes()
if len(data) < 20 or data[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', data, 18)[0] != 62:
    raise SystemExit('The driver is not a Linux x86-64 ELF shared library')
if struct.unpack_from('<H', data, 16)[0] != 3:
    raise SystemExit('The driver is not an ELF shared object')
if b'/usr/share/drirc.d' not in data:
    raise SystemExit('The driver does not reference the system drirc directory')
payload = (
    (binary, 'lib/libvulkan_intel.so', 0o755),
    (community / 'tools/cm-compile.sh', 'tools/cm-compile.sh', 0o755),
    (community / 'tools/cmk_pack.py', 'tools/cmk_pack.py', 0o644),
    (community / 'LICENSE', 'licenses/community-MIT.txt', 0o644),
    (community / 'shim/LICENSE.md', 'licenses/dxvk-igdext-MIT.txt', 0o644),
    (community / 'THIRD_PARTY.md', 'licenses/THIRD_PARTY.md', 0o644),
    (mesa / 'docs/license.rst', 'licenses/mesa-license.rst', 0o644),
)
for source, relative, mode in payload:
    if not source.is_file():
        raise SystemExit('Missing pinned package input: ' + str(source))
    target = package / relative
    if target.exists() or target.is_symlink():
        raise SystemExit('Output already exists: ' + str(target))
kernels = package / 'kernels'
if kernels.is_symlink() or (kernels.exists() and not kernels.is_dir()):
    raise SystemExit('kernels must be a real directory: ' + str(kernels))
created = []
try:
    for source, relative, mode in payload:
        target = package / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation refuses a collision appearing during the build.
        with source.open('rb') as input_file, target.open('xb') as output:
            created.append(target)
            shutil.copyfileobj(input_file, output)
            output.flush()
            target.chmod(mode)
    kernels.mkdir(exist_ok=True)
except BaseException:
    for target in reversed(created):
        target.unlink()
    raise
target = package / 'lib/libvulkan_intel.so'
print(hashlib.sha256(target.read_bytes()).hexdigest() + '  ' + str(target))
print('Staged pinned kernel helpers, kernels directory and component licenses; no compiler or shim was replaced.')
print('GPU loading, synchronization, HDR and XeSS/XeFG still need target tests.')
PY
