#!/usr/bin/env python3
"""Install only the pinned GTA app-directory vkd3d Core, with checked rollback.

No loader, prefix, Proton, DLL override, INI or Steam setting is changed.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request


VERSION = "3.1"
ASSET_URL = "https://github.com/HansKristian-Work/vkd3d-proton/releases/download/v3.1/vkd3d-proton-3.1.tar.zst"
ARCHIVE_SHA256 = "b85ea8219b71093a3924913dd7aae6172333dc0c069983ed510816d67f02120b"
CORE_SHA256 = "0dfd690a39ef8361ca3b64e9fd8e945b27d2c568dac5dc0dce1a45abf65914cc"
MEMBER = "vkd3d-proton-3.1/x64/d3d12core.dll"
TARGET = "d3d12core.dll"
STATE_DIR = ".oxp3-vkd3d-core"
MAX_ARCHIVE = 16 * 1024 * 1024
MAX_FILE = 128 * 1024 * 1024


class InstallError(Exception):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_regular(path: Path, limit: int = MAX_FILE) -> tuple[bytes, os.stat_result]:
    """Never follow a last-component symlink while reading state or DLL bytes."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise InstallError(f"Expected a bounded regular file: {path}")
        data = stream.read(limit + 1)
        if len(data) > limit:
            raise InstallError(f"File exceeds size limit: {path}")
        return data, info


def checked_game(value: str | None) -> Path:
    if value:
        candidates = [Path(value).expanduser()]
    else:
        home = Path.home()
        candidates = [home / ".local/share/Steam/steamapps/common/Grand Theft Auto V Enhanced",
                      home / ".steam/steam/steamapps/common/Grand Theft Auto V Enhanced"]
    games = set()
    for path in candidates:
        if path.is_dir() and (path / "GTA5_Enhanced.exe").is_file():
            games.add(path.resolve())
    if len(games) != 1:
        raise InstallError("Choose --game-dir containing GTA5_Enhanced.exe; no unique default game was found.")
    return games.pop()


def refuse_running(proc: Path = Path("/proc")) -> None:
    if not proc.is_dir():
        raise InstallError("Linux /proc is required to check that GTA is stopped.")
    for entry in proc.iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            arguments = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            arguments = []
        try:
            comm = (entry / "comm").read_text().strip().casefold()
        except (OSError, UnicodeError):
            comm = ""  # Either field can disappear as a process exits.
        names = [argument.decode(errors="replace").strip('"').replace("\\", "/").rsplit("/", 1)[-1].casefold()
                 for argument in arguments]
        if "gta5_enhanced.exe" in names or comm.startswith("gta5_enhanced"):
            raise InstallError("GTA V Enhanced is running. Close it fully before check/install/rollback.")


def target_path(game: Path, recorded: str | None = None) -> Path:
    matches = [path for path in game.iterdir() if path.name.casefold() == TARGET]
    if len(matches) > 1:
        raise InstallError("Conflicting case variants of d3d12core.dll; reconcile them manually.")
    if recorded is not None:
        if not isinstance(recorded, str) or recorded.casefold() != TARGET or any(char in recorded for char in "/\\"):
            raise InstallError("Invalid recorded Core filename.")
        if matches and matches[0].name != recorded:
            raise InstallError("Core filename case changed since installation; refusing to overwrite it.")
        return game / recorded
    return matches[0] if matches else game / TARGET


def snapshot(path: Path) -> tuple[dict, bytes | None]:
    if path.is_symlink():
        return {"kind": "symlink", "target": os.readlink(path)}, None
    if not path.exists():
        return {"kind": "absent"}, None
    data, info = read_regular(path)
    return {"kind": "file", "sha256": sha(data), "mode": stat.S_IMODE(info.st_mode),
            "mtime_ns": info.st_mtime_ns}, data


def same_original(path: Path, original: dict) -> bool:
    current, _ = snapshot(path)
    if current["kind"] != original["kind"]:
        return False
    if current["kind"] == "file":
        return current["sha256"] == original["sha256"] and current["mode"] == original["mode"]
    return current == original


def installed(path: Path) -> bool:
    if path.is_symlink() or not path.exists():
        return False
    return sha(read_regular(path)[0]) == CORE_SHA256


def state_directory(game: Path) -> Path:
    directory = game / STATE_DIR
    if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
        raise InstallError("State directory must be a real directory in the selected game.")
    if directory.exists():
        for entry in directory.iterdir():
            if entry.name not in {"state.json", "original.dll", "lock"} or entry.is_symlink() or not entry.is_file():
                raise InstallError("State directory contains an unrecognized file or symlink.")
        if (directory / "original.dll").exists() and not (directory / "state.json").exists():
            raise InstallError("Unrecorded backup exists; preserve it and inspect before continuing.")
    return directory


def load_state(game: Path) -> dict | None:
    directory = state_directory(game)
    path = directory / "state.json"
    if not path.exists():
        return None
    state = json.loads(read_regular(path, 64 * 1024)[0])
    if (not isinstance(state, dict) or state.get("format") != 1 or state.get("game_dir") != str(game) or
            state.get("installed_sha256") != CORE_SHA256 or state.get("version") != VERSION or
            state.get("status") not in {"prepared", "installed", "rolled_back"}):
        raise InstallError("State does not match this game path and pinned Core release.")
    target_path(game, state.get("target_name", ""))
    original = state.get("original", {})
    if not isinstance(original, dict):
        raise InstallError("Invalid original-file metadata.")
    kind = original.get("kind")
    if kind == "file":
        if (not isinstance(original.get("mode"), int) or not 0 <= original["mode"] <= 0o7777 or
                not isinstance(original.get("mtime_ns"), int) or original["mtime_ns"] < 0 or
                not re.fullmatch("[0-9a-f]{64}", original.get("sha256", ""))):
            raise InstallError("Invalid original-file metadata.")
        if sha(read_regular(directory / "original.dll")[0]) != original["sha256"]:
            raise InstallError("Original backup hash mismatch; refusing to modify the game.")
    elif kind == "symlink":
        if not isinstance(original.get("target"), str) or "\0" in original["target"]:
            raise InstallError("Invalid original symlink metadata.")
    elif kind != "absent":
        raise InstallError("Invalid original-file state.")
    return state


def atomic_bytes(path: Path, data: bytes, mode: int = 0o600) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".oxp3-core-")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def save_state(game: Path, state: dict) -> None:
    atomic_bytes(game / STATE_DIR / "state.json", (json.dumps(state, indent=2) + "\n").encode())


@contextlib.contextmanager
def mutation_lock(game: Path):
    directory = state_directory(game)
    directory.mkdir(mode=0o700, exist_ok=True)
    descriptor = os.open(directory / "lock", os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise InstallError("Another Core install/rollback is running.") from error
        refuse_running()
        yield


def verified_archive(path: Path) -> Path:
    path = path.expanduser().resolve(strict=True)
    if sha(read_regular(path, MAX_ARCHIVE)[0]) != ARCHIVE_SHA256:
        raise InstallError("Archive SHA-256 mismatch; game files were not changed.")
    return path


def download(path: Path) -> None:
    request = urllib.request.Request(ASSET_URL, headers={"User-Agent": "OXP3-CACHY-Core-installer"})
    with urllib.request.urlopen(request, timeout=30) as response, path.open("xb") as stream:
        size = 0
        while block := response.read(128 * 1024):
            size += len(block)
            if size > MAX_ARCHIVE:
                raise InstallError("Release download exceeds the pinned asset size limit.")
            stream.write(block)


def extract_core(archive: Path) -> bytes:
    """Print only the fixed regular member; never extract paths or run scripts."""
    bsdtar = shutil.which("bsdtar")
    if bsdtar:
        command = [bsdtar, "-tvf", str(archive), "--", MEMBER]
    elif shutil.which("zstd") and shutil.which("tar"):
        command = [shutil.which("tar"), "--use-compress-program=" + shutil.which("zstd"),
                   "-tvf", str(archive), "--", MEMBER]
    else:
        raise InstallError("Install bsdtar (libarchive), or GNU tar and zstd; this helper installs no packages.")
    listing = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             timeout=60).stdout.decode().splitlines()
    if len(listing) != 1 or not listing[0].startswith("-") or not listing[0].endswith(" " + MEMBER):
        raise InstallError("Expected exactly one regular x64 Core archive member.")
    command[command.index("-tvf")] = "-xOf"
    core = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=60).stdout
    if len(core) > MAX_FILE or sha(core) != CORE_SHA256:
        raise InstallError("Extracted Core SHA-256 mismatch; game files were not changed.")
    return core


def release_core(archive: Path | None) -> bytes:
    with tempfile.TemporaryDirectory(prefix="oxp3-vkd3d-") as temporary:
        if archive is None:
            archive = Path(temporary) / "release.tar.zst"
            download(archive)
        return extract_core(verified_archive(archive))


def install(game: Path, archive: Path | None = None) -> str:
    state = load_state(game)
    target = target_path(game, state["target_name"] if state else None)
    if state and state["status"] != "rolled_back" and installed(target):
        return "Already installed; original backup retained."
    core = release_core(archive)
    with mutation_lock(game):
        state = load_state(game)
        target = target_path(game, state["target_name"] if state else None)
        if state:
            if state["status"] != "rolled_back" and installed(target):
                return "Already installed; original backup retained."
            if not same_original(target, state["original"]):
                raise InstallError("Core changed outside this installer; original backup retained, no overwrite.")
        else:
            original, data = snapshot(target)
            state = {"format": 1, "version": VERSION, "game_dir": str(game),
                     "target_name": target.name, "installed_sha256": CORE_SHA256,
                     "archive_sha256": ARCHIVE_SHA256, "original": original, "status": "prepared"}
            if data is not None:
                atomic_bytes(game / STATE_DIR / "original.dll", data)
            save_state(game, state)
        if not same_original(target, state["original"]):
            raise InstallError("Original Core changed during preparation; no overwrite.")
        state["status"] = "prepared"
        save_state(game, state)
        refuse_running()
        atomic_bytes(target, core, 0o644)
        state["status"] = "installed"
        save_state(game, state)
    return "Installed only app-directory d3d12core.dll; loader and configuration unchanged."


def rollback(game: Path) -> str:
    if load_state(game) is None:
        return "No recorded installation; nothing changed."
    with mutation_lock(game):
        state = load_state(game)
        target = target_path(game, state["target_name"])
        if same_original(target, state["original"]):
            # A previous restore may have completed before its state write.
            # Finalize metadata only; never rewrite an already restored file.
            if state["status"] != "rolled_back":
                state["status"] = "rolled_back"
                save_state(game, state)
            return "Already rolled back; original backup retained."
        if state["status"] == "rolled_back":
            raise InstallError("Original state changed after rollback; nothing overwritten.")
        if not installed(target):
            raise InstallError("Installed Core hash changed or file was replaced; rollback refuses to overwrite it.")
        original = state["original"]
        refuse_running()
        if original["kind"] == "absent":
            target.unlink()
        elif original["kind"] == "file":
            atomic_bytes(target, read_regular(game / STATE_DIR / "original.dll")[0], original["mode"])
            os.utime(target, ns=(original["mtime_ns"], original["mtime_ns"]))
        else:
            descriptor, temporary = tempfile.mkstemp(dir=game, prefix=".oxp3-core-link-")
            os.close(descriptor)
            Path(temporary).unlink()
            try:
                os.symlink(original["target"], temporary)
                os.replace(temporary, target)
            finally:
                Path(temporary).unlink(missing_ok=True)
        state["status"] = "rolled_back"
        save_state(game, state)
    return "Original Core state restored; original backup retained."


def check(game: Path) -> tuple[str, int]:
    state = load_state(game)
    if state is None:
        return "No recorded installation; game files unchanged.", 1
    target = target_path(game, state["target_name"])
    if state["status"] != "rolled_back" and installed(target):
        return "Pinned vkd3d Core 3.1 installed; original backup verified.", 0
    if same_original(target, state["original"]):
        return "Pinned Core not active; original state and backup verified.", 1
    raise InstallError("Core no longer matches installed or original state; inspect without overwriting.")


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "install", "rollback"))
    parser.add_argument("--game-dir", help="GTA folder containing GTA5_Enhanced.exe")
    parser.add_argument("--archive", type=Path, help="Pinned official archive instead of downloading (install only)")
    args = parser.parse_args(arguments)
    try:
        if args.archive is not None and args.action != "install":
            raise InstallError("--archive applies only to install.")
        game = checked_game(args.game_dir)
        refuse_running()
        if args.action == "check":
            message, code = check(game)
        else:
            message = install(game, args.archive) if args.action == "install" else rollback(game)
            code = 0
        print(message)
        return code
    except (InstallError, OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
        print(f"vkd3d-core: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
