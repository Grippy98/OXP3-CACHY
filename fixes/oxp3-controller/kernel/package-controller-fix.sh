#!/usr/bin/env bash
set -euo pipefail
bundle_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ $# -le 1 ]] || { echo 'Usage: package-controller-fix.sh [OUTPUT_DIRECTORY]' >&2; exit 2; }
output_dir=${1:-"$bundle_dir/build"}
mkdir -p "$output_dir"
output_dir=$(cd -- "$output_dir" && pwd)
cd "$bundle_dir"
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
package=hid-oxp-onex3-dkms
version=0.1.4396c18
source_dir="$stage/usr/src/hid-oxp-onex3-$version"
doc_dir="$stage/usr/share/doc/$package"
install -d "$source_dir" "$doc_dir"
install -m 0644 hid-oxp.c "$source_dir/hid-oxp.c"
install -m 0644 hid-ids.h Makefile dkms.conf "$source_dir/"
install -m 0644 SOURCES.md hid-oxp-pr13-cachyos-7.2.9.patch \
  sysfs-driver-hid-oxp COPYING GPL-2.0 "$doc_dir/"
size=$(du -sk "$stage/usr" | awk '{print $1 * 1024}')
cat > "$stage/.PKGINFO" <<EOF
pkgname = $package
pkgbase = $package
pkgver = $version-1
pkgdesc = Pinned ONEXPLAYER 3 controller fixes from OGC PR 13
url = https://github.com/OpenGamingCollective/linux-unstable/pull/13
builddate = $(date +%s)
size = $size
arch = any
license = GPL-2.0-or-later
depend = dkms
optdepend = linux-headers: exact matching kernel headers are required for DKMS
EOF
archive="$output_dir/$package-$version-1-any.pkg.tar.gz"
python3 - "$stage" "$archive" <<'PY'
from pathlib import Path
import sys
import tarfile
stage = Path(sys.argv[1])
with tarfile.open(sys.argv[2], 'w:gz', format=tarfile.GNU_FORMAT) as archive:
    for entry in [stage / '.PKGINFO', stage / 'usr', *sorted((stage / 'usr').rglob('*'))]:
        info = archive.gettarinfo(str(entry), arcname=entry.relative_to(stage).as_posix())
        info.uid = info.gid = 0
        info.uname = info.gname = 'root'
        if entry.is_file():
            with entry.open('rb') as stream:
                archive.addfile(info, stream)
        else:
            archive.addfile(info)
PY
if command -v sha256sum >/dev/null; then sha256sum "$archive"; else shasum -a 256 "$archive"; fi
