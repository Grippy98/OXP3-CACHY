#!/usr/bin/env python3
"""Install/restore only this user's Gamescope Lua profile."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile


def atomic(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".oxp3-profile-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            os.fchmod(out.fileno(), mode)
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main():
    action = sys.argv[1]
    if os.geteuid() == 0:
        raise RuntimeError("Run as the Gaming Mode user, without sudo")
    config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    state = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "oxp3-cachy/panel-refresh"
    target = config / "gamescope/scripts/onexplayer3-sdc-refresh.lua"
    manifest = state / "installed.json"
    for path in [state, target, manifest]:
        if path.is_symlink():
            raise RuntimeError(f"Refusing symlink: {path}")
    if action == "install":
        data = Path(__file__).with_name("onexplayer3-sdc-refresh.lua").read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if manifest.exists():
            old = json.loads(manifest.read_text())
            if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == old["sha256"] == digest:
                print("Refresh profile already installed")
                return
            raise RuntimeError("Managed profile changed; roll back or resolve it first")
        state.mkdir(parents=True, mode=0o700, exist_ok=True)
        backup = target.read_bytes() if target.exists() else None
        if backup is not None:
            atomic(state / "previous.lua", backup, 0o600)
        record = {"sha256": digest, "target": str(target), "had_previous": backup is not None, "previous_sha256": hashlib.sha256(backup).hexdigest() if backup is not None else None, "previous_mode": (target.stat().st_mode & 0o777) if backup is not None else 0o644}
        # State is saved before target mutation, so rollback remains available
        # even if the final atomic replacement is interrupted.
        atomic(manifest, (json.dumps(record) + "\n").encode(), 0o600)
        atomic(target, data)
        print(f"Installed profile only: {target}. Close games and restart Gaming Mode to load it.")
    elif action == "rollback":
        if not manifest.exists():
            print("No managed refresh profile to roll back")
            return
        record = json.loads(manifest.read_text())
        if record["target"] != str(target):
            raise RuntimeError("Configuration directory changed since installation")
        current_hash = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
        allowed = {record["sha256"], record.get("previous_sha256")}
        if current_hash not in allowed:
            raise RuntimeError("Profile was edited after installation; preserving it for manual review")
        if record["had_previous"]:
            atomic(target, (state / "previous.lua").read_bytes(), record.get("previous_mode", 0o644))
        else:
            target.unlink(missing_ok=True)
        manifest.unlink()
        (state / "previous.lua").unlink(missing_ok=True)
        print("Previous profile restored. Close games and restart Gaming Mode to load it.")
    else:
        raise RuntimeError("Expected install or rollback")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        sys.exit(str(error))
