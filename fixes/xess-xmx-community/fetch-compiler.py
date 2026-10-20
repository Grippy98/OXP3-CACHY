#!/usr/bin/env python3
"""Fetch and unpack the pinned Intel compiler into PACKAGE/igc, without running it.

Requires Python 3.12+ and ar. Reading zstd-compressed Debian payloads additionally
requires either Python's zstd support or an installed zstd command. Existing igc
paths, including empty directories and symlinks, are never replaced.
"""

from __future__ import annotations

import argparse
import copy
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import ssl
import subprocess
import sys
import tarfile
import tempfile
from typing import NamedTuple
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, build_opener


class CompilerError(Exception):
    """The compiler bundle has not been published."""


class Asset(NamedTuple):
    filename: str
    url: str
    sha256: str
    component: str


ASSETS = (
    Asset(
        "intel-igc-core-2_2.10.10+18926_amd64.deb",
        "https://github.com/intel/intel-graphics-compiler/releases/download/v2.10.10/"
        "intel-igc-core-2_2.10.10%2B18926_amd64.deb",
        "ec3b8e6bb3d6371d3b9963c32ddb1d5315e6b0c3f4ae1d91a7515b5a8907ffe6",
        "igc",
    ),
    Asset(
        "intel-igc-opencl-2_2.10.10+18926_amd64.deb",
        "https://github.com/intel/intel-graphics-compiler/releases/download/v2.10.10/"
        "intel-igc-opencl-2_2.10.10%2B18926_amd64.deb",
        "0c631f25cd8394a2f7640f9e35b593cc98ca3fbe922419c5cb20b2281477ef4c",
        "igc",
    ),
    Asset(
        "intel-ocloc_25.18.33578.6-0_amd64.deb",
        "https://github.com/intel/compute-runtime/releases/download/25.18.33578.6/"
        "intel-ocloc_25.18.33578.6-0_amd64.deb",
        "c772db8891539890237d50c357af1480b22cbd859c0b8afb5355f605a818d758",
        "neo",
    ),
)
MAX_ASSET_BYTES = 512 * 1024 * 1024
MAX_UNPACKED_BYTES = 2 * 1024 * 1024 * 1024


class HTTPSRedirectsOnly(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        if urlsplit(newurl).scheme.lower() != "https":
            raise CompilerError("refusing a non-HTTPS asset redirect")
        return super().redirect_request(request, fp, code, message, headers, newurl)


def open_https(url: str):
    if urlsplit(url).scheme.lower() != "https":
        raise CompilerError("compiler asset URLs must use HTTPS")
    opener = build_opener(HTTPSHandler(context=ssl.create_default_context()), HTTPSRedirectsOnly())
    return opener.open(url, timeout=60)


def download_verified(asset: Asset, destination: Path) -> None:
    digest = hashlib.sha256()
    total = 0
    with open_https(asset.url) as response, destination.open("xb") as output:
        if urlsplit(response.geturl()).scheme.lower() != "https":
            raise CompilerError("refusing a non-HTTPS asset response")
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_ASSET_BYTES:
                raise CompilerError(f"asset exceeds size limit: {asset.filename}")
            output.write(chunk)
            digest.update(chunk)
    if digest.hexdigest() != asset.sha256:
        raise CompilerError(f"SHA-256 mismatch: {asset.filename}")


def unpack_deb_payload(archive: Path, destination: Path, work: Path) -> None:
    """Read only Debian's data member; never invoke dpkg or maintainer scripts."""
    listing = subprocess.run(["ar", "t", str(archive)], check=True, capture_output=True,
                             text=True, timeout=30).stdout.splitlines()
    candidates = [name for name in listing if name in (
        "data.tar", "data.tar.gz", "data.tar.xz", "data.tar.bz2", "data.tar.zst")]
    if len(candidates) != 1:
        raise CompilerError(f"expected exactly one supported data.tar payload: {archive.name}")
    payload = work / candidates[0]
    with payload.open("xb") as output:
        subprocess.run(["ar", "p", str(archive), candidates[0]], check=True,
                       stdout=output, stderr=subprocess.PIPE, timeout=60)
    try:
        stream = tarfile.open(payload, "r:*")
    except (tarfile.ReadError, tarfile.CompressionError):
        if payload.suffix != ".zst":
            raise
        uncompressed = work / "data.tar"
        with uncompressed.open("xb") as output:
            subprocess.run(["zstd", "--decompress", "--stdout", str(payload)], check=True,
                           stdout=output, stderr=subprocess.PIPE, timeout=120)
        stream = tarfile.open(uncompressed, "r:")
    with stream:
        extract_usr(stream, destination)


def archive_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise CompilerError(f"unsafe archive path: {value}")
    return path


def extract_usr(archive: tarfile.TarFile, destination: Path) -> None:
    """Extract usr/ as this component's root, retaining safe library symlinks."""
    members = archive.getmembers()
    if len(members) > 100000 or sum(member.size for member in members) > MAX_UNPACKED_BYTES:
        raise CompilerError("compiler payload exceeds extraction limit")
    selected = []
    for member in members:
        path = archive_path(member.name)
        if not (member.isdir() or member.isfile() or member.issym() or member.islnk()):
            raise CompilerError(f"unsupported special archive member: {member.name}")
        if member.issym() and PurePosixPath(member.linkname).is_absolute():
            raise CompilerError(f"absolute archive symlink: {member.name}")
        if not path.parts or path.parts[0] != "usr":
            continue
        adjusted = copy.copy(member)
        adjusted.name = str(path.relative_to("usr"))
        if member.islnk():
            target = archive_path(member.linkname)
            if not target.parts or target.parts[0] != "usr":
                raise CompilerError(f"archive hardlink leaves usr: {member.name}")
            adjusted.linkname = str(target.relative_to("usr"))
        # Validate every selected link before extraction. The data filter checks
        # links relative to the retained usr tree, not the original archive root.
        tarfile.data_filter(adjusted, str(destination))
        selected.append(adjusted)
    if not selected:
        raise CompilerError("compiler payload contains no usr tree")
    destination.mkdir(mode=0o700)
    archive.extractall(destination, members=selected, filter="data")


def merge_tree(source: Path, destination: Path) -> None:
    """Merge the two IGC packages without following destination symlinks."""
    destination.mkdir(mode=0o700, exist_ok=True)
    for entry in sorted(source.iterdir()):
        target = destination / entry.name
        exists = os.path.lexists(target)
        if entry.is_symlink():
            if exists:
                if not target.is_symlink() or os.readlink(target) != os.readlink(entry):
                    raise CompilerError(f"conflicting compiler payload: {entry.name}")
            else:
                target.symlink_to(os.readlink(entry))
        elif entry.is_dir():
            if exists and (target.is_symlink() or not target.is_dir()):
                raise CompilerError(f"conflicting compiler directory: {entry.name}")
            merge_tree(entry, target)
        elif entry.is_file():
            if exists:
                if target.is_symlink() or not target.is_file() or target.read_bytes() != entry.read_bytes():
                    raise CompilerError(f"conflicting compiler file: {entry.name}")
            else:
                shutil.copy2(entry, target)


def validate_bundle(bundle: Path) -> None:
    for name in (
        "igc/local/lib/libigc.so.2", "igc/local/lib/libiga64.so.2",
        "igc/local/lib/libigdfcl.so.2", "igc/local/lib/libopencl-clang2.so.15",
        "neo/bin/ocloc-25.18.1", "neo/lib/x86_64-linux-gnu/libocloc.so",
    ):
        path = bundle / name
        if not path.resolve().is_relative_to(bundle.resolve()) or not path.is_file():
            raise CompilerError(f"missing or escaping compiler binary: {name}")
        with path.open("rb") as stream:
            if stream.read(5) != b"\x7fELF\x02":
                raise CompilerError(f"compiler binary is not 64-bit ELF: {name}")
    if not os.access(bundle / "neo/bin/ocloc-25.18.1", os.X_OK):
        raise CompilerError("compiler executable lacks execute permission")
    for name in ("igc/local/lib/igc2/NOTICES.txt", "neo/share/doc/intel-ocloc/copyright"):
        path = bundle / name
        if not path.is_file() or path.stat().st_size == 0:
            raise CompilerError(f"missing Intel license material: {name}")


def publish_noreplace(source: Path, target: Path) -> None:
    """An atomic directory rename which also refuses an existing empty target."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        rename = libc.renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(-100, os.fsencode(source), -100, os.fsencode(target), 1)  # RENAME_NOREPLACE
    elif sys.platform == "darwin" and hasattr(libc, "renamex_np"):
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(os.fsencode(source), os.fsencode(target), 4)  # RENAME_EXCL
    else:
        raise CompilerError("this platform lacks an atomic no-replace directory rename")
    if result:
        code = ctypes.get_errno()
        if code in (errno.EEXIST, errno.ENOTEMPTY):
            raise CompilerError("igc appeared during preparation; existing path was preserved")
        raise OSError(code, os.strerror(code))


def install_compiler(package: Path) -> Path:
    if not package.is_absolute():
        raise CompilerError("PACKAGE must be an absolute path")
    package = package.resolve()
    destination = package / "igc"
    if os.path.lexists(destination):
        raise CompilerError("PACKAGE/igc already exists; refusing to replace it")
    package.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".igc-stage-", dir=package) as temporary:
        stage = Path(temporary)
        bundle = stage / "bundle"
        bundle.mkdir(mode=0o700)
        for index, asset in enumerate(ASSETS):
            archive = stage / asset.filename
            download_verified(asset, archive)
            work = stage / f"unpack-{index}"
            work.mkdir(mode=0o700)
            payload = work / "usr"
            unpack_deb_payload(archive, payload, work)
            merge_tree(payload, bundle / asset.component)
        validate_bundle(bundle)
        (bundle / "compiler-sources.json").write_text(json.dumps({
            "igc": "2.10.10+18926", "computeRuntime": "25.18.33578.6",
            "assets": [asset._asdict() for asset in ASSETS],
        }, indent=2) + "\n", encoding="utf-8")
        publish_noreplace(bundle, destination)
    return destination


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", metavar="PACKAGE", help="absolute private runtime package path")
    options = parser.parse_args(arguments)
    if sys.version_info < (3, 12):
        raise CompilerError("Python 3.12 or newer is required for tar data filtering")
    if os.geteuid() == 0:
        raise CompilerError("run as the normal desktop user, not root")
    result = install_compiler(Path(options.package).expanduser())
    print(f"Verified Intel compiler unpacked to {result}; no downloaded executable was run.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (CompilerError, OSError, subprocess.SubprocessError, tarfile.TarError) as error:
        print(f"fetch-compiler: {error}", file=sys.stderr)
        sys.exit(2)
