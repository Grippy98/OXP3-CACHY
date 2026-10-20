#!/usr/bin/env bash
# Build the pinned community shim with a caller-verified LLVM-MinGW toolchain.
set -euo pipefail

SOURCE_URL=https://github.com/HHHHanasak1/xess-xmx-linux.git
SOURCE_PIN=627566641c360c7a0e5d529898b2a81daef1c7ab

usage() {
  printf 'Usage: %s MINGWROOT BUILDDIR PACKAGE\n' "$0"
  printf '%s\n' 'All paths must be absolute. BUILDDIR must not exist; its parent must exist.' \
    'Use a verified LLVM-MinGW toolchain for this host; no toolchain is downloaded.' \
    'Writes PACKAGE/shim/igdext64.dll only if that output does not already exist.'
}
die() { printf 'build-shim: %s\n' "$*" >&2; exit 1; }
if [[ ${1:-} == --help ]]; then usage; exit 0; fi
[[ $# == 3 ]] || { usage >&2; exit 2; }
mingw=$1
build=$2
package=$3
for path in "$mingw" "$build" "$package"; do
  [[ $path == /* ]] || die "an absolute path is required: $path"
done
case $(uname -s):$(uname -m) in
  Darwin:arm64|Darwin:x86_64|Linux:x86_64) ;;
  *) die 'requires macOS or Linux x86-64 with a matching native LLVM-MinGW toolchain' ;;
esac
for command in git cmake ninja python3; do
  command -v "$command" >/dev/null || die "missing prerequisite: $command"
done
for command in x86_64-w64-mingw32-clang++ x86_64-w64-mingw32-windres llvm-readobj; do
  [[ -x $mingw/bin/$command ]] || die "missing toolchain executable: $mingw/bin/$command"
done
[[ ! -e $build && ! -L $build ]] || die "build directory already exists: $build"
target=$package/shim/igdext64.dll
[[ ! -e $target && ! -L $target ]] || die "output already exists: $target"
mkdir -- "$build"
source=$build/community-source
git -c init.templateDir= -c core.hooksPath=/dev/null init --quiet "$source"
git -C "$source" -c core.hooksPath=/dev/null -c fetch.fsckObjects=true \
  fetch --quiet --depth=1 --no-tags "$SOURCE_URL" "$SOURCE_PIN"
[[ $(git -C "$source" rev-parse FETCH_HEAD) == "$SOURCE_PIN" ]] || die 'source commit does not match the pin'
git -C "$source" -c core.hooksPath=/dev/null checkout --quiet --detach "$SOURCE_PIN"

# Every path is one argv value. No generated CMake source or shell evaluation is
# needed, including when the toolchain/build directories contain spaces.
cmake -S "$source/shim" -B "$build/cmake" -G Ninja \
  -DCMAKE_SYSTEM_NAME=Windows -DCMAKE_SYSTEM_PROCESSOR=x86_64 \
  "-DCMAKE_CXX_COMPILER=$mingw/bin/x86_64-w64-mingw32-clang++" \
  "-DCMAKE_RC_COMPILER=$mingw/bin/x86_64-w64-mingw32-windres" \
  "-DCMAKE_FIND_ROOT_PATH=$mingw/x86_64-w64-mingw32" \
  -DCMAKE_FIND_ROOT_PATH_MODE_PROGRAM=NEVER \
  -DCMAKE_FIND_ROOT_PATH_MODE_LIBRARY=ONLY \
  -DCMAKE_FIND_ROOT_PATH_MODE_INCLUDE=ONLY \
  -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=ONLY \
  -DCMAKE_CXX_FLAGS=-fms-extensions \
  -DCMAKE_SHARED_LINKER_FLAGS=-Wl,--no-insert-timestamp \
  -DCMAKE_BUILD_TYPE=Release -DXMX_STATIC_TABLE=OFF
cmake --build "$build/cmake" --parallel

python3 - "$mingw/bin/llvm-readobj" "$build/cmake/igdext64.dll" "$source/shim/src/dll/Igdext.def" "$target" <<'PY'
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys

reader, binary, definitions, target = sys.argv[1:]
headers = subprocess.check_output([reader, '--file-headers', binary], text=True)
if 'IMAGE_FILE_MACHINE_AMD64' not in headers or 'IMAGE_FILE_DLL' not in headers:
    raise SystemExit('The shim is not a Windows x86-64 DLL')
exports = subprocess.check_output([reader, '--coff-exports', binary], text=True)
actual = {}
for block in re.findall(r'Export \{(.*?)\n\}', exports, re.S):
    name = re.search(r'^  Name: (.+)$', block, re.M)
    if name:
        if re.search(r'RVA: 0x0\b', block):
            raise SystemExit('Null export: ' + name[1])
        actual[name[1]] = int(re.search(r'Ordinal: (\d+)', block)[1])
expected = {}
for raw in Path(definitions).read_text().splitlines():
    line = raw.split(';', 1)[0].strip()
    if line and not line.startswith(('LIBRARY', 'EXPORTS')):
        parts = line.split()
        expected[parts[0]] = next((int(p[1:]) for p in parts[1:] if p.startswith('@')), None)
if actual.keys() != expected.keys() or any(n is not None and actual[k] != n for k, n in expected.items()):
    raise SystemExit('Shim exports differ from the pinned DEF')
imports = subprocess.check_output([reader, '--coff-imports', binary], text=True)
imports = re.findall(r'^  Name: (.+)$', imports, re.M)
if any(n.lower() not in ('kernel32.dll', 'advapi32.dll') and not n.lower().startswith('api-ms-win-crt-') for n in imports):
    raise SystemExit('Unexpected DLL imports: ' + ', '.join(imports))
print('Verified exports and static C++ runtime; Windows UCRT API imports still require a Wine/Proton load test.')
target = Path(target)
target.parent.mkdir(parents=True, exist_ok=True)
# Exclusive creation also refuses an output appearing during this build.
with open(binary, 'rb') as source, target.open('xb') as output:
    try:
        shutil.copyfileobj(source, output)
        output.flush()
        target.chmod(0o644)
    except BaseException:
        target.unlink()
        raise
print(hashlib.sha256(target.read_bytes()).hexdigest() + '  ' + str(target))
PY
