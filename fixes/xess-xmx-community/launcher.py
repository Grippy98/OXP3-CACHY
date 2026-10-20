#!/usr/bin/env python3
"""Select the community XeSS XMX runtime for one child process.

No prefix, Proton, Steam, systemd or session configuration is modified. The only
launcher-created file is a private Vulkan ICD manifest. --probe is a Vulkan
loading/enumeration preflight, not an XMX, image-quality or frame-generation test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from typing import Mapping, Sequence


DEFAULT_PACKAGE = "~/.local/lib/oxp3-xess-community/20261018"
DISABLED_EXTENSION = "VK_EXT_descriptor_buffer"
PRINT_KEYS = (
    "VK_DRIVER_FILES", "VK_ICD_FILENAMES", "VK_ADD_DRIVER_FILES",
    "VKD3D_DISABLE_EXTENSIONS", "ANV_CM_KERNEL_DIR", "ANV_CM_HELPER",
    "INTC_ALT_DRIVER_EXTENSIONS_PATH", "force_vk_vendor",
    "IGDEXT_TRACE", "IGDEXT_FORCE_FALLBACK", "PROTON_ENABLE_HDR", "DXVK_HDR",
)


class LauncherError(Exception):
    """An invalid package or configuration; the child has not been started."""


def checked_package(value: str) -> Path:
    package = Path(value).expanduser()
    if not package.is_absolute():
        raise LauncherError("--package must be an absolute path")
    package = package.resolve()
    # A colon cannot be represented inside the loader's colon-delimited list;
    # a literal Unix backslash cannot be represented in the Windows Z: path.
    if any(character in str(package) for character in (":", "\\", "\n", "\r")):
        raise LauncherError("package paths cannot contain colons, backslashes or line breaks")
    for relative in (
        "lib/libvulkan_intel.so", "shim/igdext64.dll",
        "tools/cm-compile.sh", "tools/cmk_pack.py",
    ):
        if not (package / relative).is_file():
            raise LauncherError(f"missing package file: {relative}")
    if not os.access(package / "tools/cm-compile.sh", os.X_OK):
        raise LauncherError("package helper is not executable: tools/cm-compile.sh")
    if not (package / "kernels").is_dir():
        raise LauncherError("missing package directory: kernels")
    if not any(path.is_file() and os.access(path, os.X_OK)
               for path in (package / "igc/neo/bin").glob("ocloc*")):
        raise LauncherError("missing executable compiler: igc/neo/bin/ocloc*")
    if not (package / "igc/igc/local/lib").is_dir():
        raise LauncherError("missing compiler library directory: igc/igc/local/lib")
    return package


def default_driver_dirs(environment: Mapping[str, str]) -> list[Path]:
    home = Path(environment.get("HOME", str(Path.home())))
    config_home = Path(environment.get("XDG_CONFIG_HOME", str(home / ".config")))
    data_home = Path(environment.get("XDG_DATA_HOME", str(home / ".local/share")))
    config_dirs = environment.get("XDG_CONFIG_DIRS", "/etc/xdg").split(os.pathsep)
    data_dirs = environment.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(os.pathsep)
    roots = [config_home, *(Path(p) for p in config_dirs if p),
             Path("/etc"), data_home, *(Path(p) for p in data_dirs if p)]
    return list(dict.fromkeys(root / "vulkan/icd.d" for root in roots))


def expand_driver_entries(entries: Sequence[str]) -> list[Path]:
    result: list[Path] = []
    for entry in entries:
        if not entry:
            continue
        path = Path(entry)
        try:
            children = sorted(path.glob("*.json")) if path.is_dir() else [path]
        except OSError as error:
            raise LauncherError(f"cannot inspect driver directory {path}: {error}") from error
        result.extend(children)
    return result


def is_64bit_anv(manifest: Path) -> bool:
    """Identify ANV using its library name and declared/inferable ELF class.

    Unknown or malformed manifests are retained rather than deleting another
    driver's selection. A 32-bit ANV manifest always remains available.
    """
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        icd = data["ICD"]
        library = icd["library_path"]
        if not isinstance(library, str):
            return False
        if not re.fullmatch(r"libvulkan_intel\.so(?:\.\d+)*", Path(library).name):
            return False
        architecture = str(icd.get("library_arch", ""))
        if architecture == "32":
            return False
        if architecture == "64":
            return True
        name = manifest.name.lower()
        library_lower = library.lower()
        if re.search(r"(?:i[3-6]86|x86-32|32bit)", name) or any(
                part in library_lower for part in ("/lib32/", "/i386-linux-gnu/", "/i686-linux-gnu/")):
            return False
        if any(part in name for part in ("x86_64", "amd64", "64bit")):
            return True
        candidate = Path(library)
        candidates = ([candidate] if candidate.is_absolute() else
                      [manifest.parent / candidate, Path("/usr/lib") / candidate,
                       Path("/usr/lib64") / candidate, Path("/lib64") / candidate])
        for candidate in candidates:
            try:
                with candidate.open("rb") as stream:
                    header = stream.read(5)
            except OSError:
                continue
            if header[:4] == b"\x7fELF":
                return header[4:5] == b"\x02"
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return False


def retained_driver_files(environment: Mapping[str, str],
                          search_dirs: Sequence[Path] | None = None) -> list[Path]:
    # VK_DRIVER_FILES takes precedence over the deprecated VK_ICD_FILENAMES.
    # Preserve an explicitly empty selection instead of scanning default paths.
    if "VK_DRIVER_FILES" in environment:
        entries = environment["VK_DRIVER_FILES"].split(os.pathsep)
    elif "VK_ICD_FILENAMES" in environment:
        entries = environment["VK_ICD_FILENAMES"].split(os.pathsep)
    else:
        entries = environment.get("VK_ADD_DRIVER_FILES", "").split(os.pathsep)
        entries += [str(path) for path in
                    (search_dirs if search_dirs is not None else default_driver_dirs(environment))
                    if path.is_dir()]
    retained: list[Path] = []
    for path in expand_driver_entries(entries):
        if not is_64bit_anv(path) and path not in retained:
            retained.append(path)
    return retained


def runtime_directory(environment: Mapping[str, str]) -> Path:
    home = Path(environment.get("HOME", str(Path.home())))
    if environment.get("XDG_RUNTIME_DIR"):
        base = Path(environment["XDG_RUNTIME_DIR"])
    else:
        base = Path(environment.get("XDG_CACHE_HOME", str(home / ".cache")))
    if not base.is_absolute():
        raise LauncherError("runtime/cache directory must be absolute")
    if ":" in str(base):
        raise LauncherError("runtime/cache directory cannot contain the Vulkan path-list delimiter ':'")
    directory = base / "oxp3-xess-community"
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise LauncherError("runtime directory must be a private directory owned by the current user")
    except OSError as error:
        raise LauncherError(f"cannot create private runtime directory: {error}") from error
    return directory


def write_icd(package: Path, environment: Mapping[str, str]) -> Path:
    directory = runtime_directory(environment)
    identity = hashlib.sha256(os.fsencode(package)).hexdigest()[:20]
    manifest = directory / f"intel_icd.oxp3-xess-{identity}.x86_64.json"
    contents = json.dumps({
        "file_format_version": "1.0.1",
        "ICD": {"library_path": str(package / "lib/libvulkan_intel.so"),
                "library_arch": "64", "api_version": "1.4.348"},
    }, indent=2) + "\n"
    try:
        if manifest.is_file() and not manifest.is_symlink() and manifest.read_text() == contents:
            return manifest
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory,
                                         prefix=".icd-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(contents)
        try:
            os.replace(temporary, manifest)
        finally:
            temporary.unlink(missing_ok=True)
    except OSError as error:
        raise LauncherError(f"cannot write private ICD manifest: {error}") from error
    return manifest


def launch_environment(package: Path, original: Mapping[str, str], *,
                       trace: bool = False, fallback: bool = False,
                       search_dirs: Sequence[Path] | None = None) -> dict[str, str]:
    environment = dict(original)
    retained = retained_driver_files(original, search_dirs)
    manifest = write_icd(package, original)
    environment["VK_DRIVER_FILES"] = os.pathsep.join(str(path) for path in [manifest, *retained])
    extensions = [part.strip() for part in original.get("VKD3D_DISABLE_EXTENSIONS", "").split(",")
                  if part.strip()]
    if DISABLED_EXTENSION not in extensions:
        extensions.append(DISABLED_EXTENSION)
    environment["VKD3D_DISABLE_EXTENSIONS"] = ",".join(dict.fromkeys(extensions))
    environment["ANV_CM_KERNEL_DIR"] = str(package / "kernels")
    environment["ANV_CM_HELPER"] = str(package / "tools/cm-compile.sh")
    environment["INTC_ALT_DRIVER_EXTENSIONS_PATH"] = "Z:" + str(package / "shim").replace("/", "\\")
    environment["force_vk_vendor"] = "0"
    if trace:
        environment["IGDEXT_TRACE"] = "1"
    if fallback:
        environment["IGDEXT_FORCE_FALLBACK"] = "1"
    return environment


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--package", default=DEFAULT_PACKAGE, help="absolute private runtime package path")
    result.add_argument("--trace", action="store_true", help="request the shim's diagnostic trace")
    result.add_argument("--fallback", action="store_true", help="force the shim's fallback path for an A/B comparison")
    result.add_argument("--off", action="store_true", help="execute with the original environment, without package checks or writes")
    result.add_argument("--probe", action="store_true", help="run vulkaninfo --summary only; this is not an XMX/FG correctness test")
    result.add_argument("--print-env", action="store_true", help="print only the runtime/HDR environment whitelist, without executing a child")
    result.add_argument("command", nargs=argparse.REMAINDER, help="child command, normally after --")
    return result


def main(arguments: Sequence[str] | None = None) -> int:
    options = parser().parse_args(arguments)
    command = options.command
    if command[:1] == ["--"]:
        command = command[1:]
    if os.geteuid() == 0:
        raise LauncherError("run this launcher as the normal desktop user, not root")
    if options.probe and command:
        raise LauncherError("--probe does not accept a child command")
    if not command and not options.probe and not options.print_env:
        raise LauncherError("a child command is required (use -- COMMAND ...)")
    original = dict(os.environ)
    environment = (original if options.off else launch_environment(
        checked_package(options.package), original, trace=options.trace, fallback=options.fallback))
    if options.print_env:
        print(json.dumps({key: environment[key] for key in PRINT_KEYS if key in environment}, indent=2))
        return 0
    if options.probe:
        print("Preflight only: Vulkan driver loading and GPU enumeration; XMX, frame generation and HDR are unverified.",
              file=sys.stderr)
        command = ["vulkaninfo", "--summary"]
    try:
        os.execvpe(command[0], command, environment)
    except OSError as error:
        raise LauncherError(f"cannot execute {command[0]}: {error}") from error
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LauncherError as error:
        print(f"xess-xmx-community: {error}", file=sys.stderr)
        sys.exit(2)
