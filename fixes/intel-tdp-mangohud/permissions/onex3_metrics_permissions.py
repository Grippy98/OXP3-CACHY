#!/usr/bin/env python3
"""Grant the video group read access to three specific OXP3 telemetry sources."""

import argparse
import fcntl
import grp
import json
import os
from pathlib import Path
import stat
import tempfile


STATE = Path('/var/lib/onex3-metrics-permissions/state.json')
BOOT_ID = Path('/proc/sys/kernel/random/boot_id')
READ_MODE = 0o440


def check_device():
    root = Path('/sys/class/dmi/id')
    values = [''.join(c for c in (root / name).read_text().upper() if c.isalnum())
              for name in ('sys_vendor', 'product_name')]
    if values != ['ONENETBOOK', 'ONEXPLAYER3']:
        raise SystemExit('Telemetry access is restricted to ONE-NETBOOK ONEXPLAYER 3.')


def candidates():
    nodes = []
    root = Path('/sys/class/powercap')
    for package in sorted(root.glob('intel-rapl:*')):
        if package.name.count(':') != 1 or not package.is_dir():
            continue
        if (package / 'name').read_text().strip() != 'package-0':
            continue
        nodes.append(package / 'energy_uj')
        for child in sorted(package.glob('intel-rapl:*')):
            if (child / 'name').read_text().strip() == 'uncore':
                nodes.append(child / 'energy_uj')
    for endpoint in sorted(Path('/sys/class/intel_pmt').glob('telem*')):
        if (int((endpoint / 'guid').read_text().strip(), 0) == 0x03086000
                and int((endpoint / 'size').read_text().strip()) == 3352):
            nodes.append(endpoint / 'telem')
    return sorted({node.resolve(strict=True) for node in nodes})


def save_state(state):
    STATE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=STATE.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(state, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, STATE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply():
    boot_id = BOOT_ID.read_text().strip()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    if state.get('boot_id') != boot_id:
        state = {'boot_id': boot_id, 'nodes': {}}
    state.setdefault('pending_apply', {})
    gid = grp.getgrnam('video').gr_gid
    nodes = candidates()
    attempted = []
    try:
        for path in nodes:
            before = path.stat()
            if before.st_uid != 0 or not path.is_file():
                raise OSError(f'Unexpected telemetry ownership or type: {path}')
            key = str(path)
            previous = {'gid': before.st_gid, 'mode': stat.S_IMODE(before.st_mode)}
            if key not in state['nodes']:
                state['nodes'][key] = previous
            # Persist our intended intermediate pair before either mutation.
            # A same-boot restore can then recognize a crash after chown but
            # before chmod, without accepting arbitrary administrator modes.
            earlier_pending = state['pending_apply'].get(key)
            state['pending_apply'][key] = previous
            save_state(state)
            attempted.append((path, previous, earlier_pending))
            os.chown(path, -1, gid)
            os.chmod(path, READ_MODE)
            del state['pending_apply'][key]
            save_state(state)
            print(f'video read access: {path}')
    except OSError as error:
        failures = []
        for path, previous, earlier_pending in reversed(attempted):
            key = str(path)
            try:
                current = path.stat()
                pair = (current.st_gid, stat.S_IMODE(current.st_mode))
                original = (previous['gid'], previous['mode'])
                ours = {(gid, READ_MODE), (gid, previous['mode'])}
                if current.st_uid != 0 or pair not in ours | {original}:
                    failures.append(f'changed attributes retained: {path}')
                    continue
                if pair != original:
                    os.chown(path, -1, previous['gid'])
                    os.chmod(path, previous['mode'])
                if earlier_pending:
                    state['pending_apply'][key] = earlier_pending
                else:
                    state['pending_apply'].pop(key, None)
            except OSError as undo_error:
                failures.append(f'{path}: {undo_error}')
        save_state(state)
        if failures:
            raise OSError(f'Permission apply failed: {error}; incomplete cleanup: {failures}') from error
        raise OSError(f'Permission apply failed: {error}; changes from this attempt restored') from error
    print(f'Applied to {len(nodes)} telemetry files; power-limit write permissions untouched.')


def restore():
    if not STATE.exists():
        return
    state = json.loads(STATE.read_text())
    if state.get('boot_id') != BOOT_ID.read_text().strip():
        print('Saved permissions belong to another boot; current nodes were not changed.')
        return
    gid = grp.getgrnam('video').gr_gid
    for name, previous in state['nodes'].items():
        path = Path(name)
        if not path.exists():
            continue
        current = path.stat()
        pair = (current.st_gid, stat.S_IMODE(current.st_mode))
        expected = {(gid, READ_MODE)}
        pending = state.get('pending_apply', {}).get(name)
        if pending:
            expected.add((gid, pending['mode']))
        if current.st_uid != 0 or pair not in expected:
            print(f'Permissions changed after installation; preserved: {path}')
            continue
        os.chown(path, -1, previous['gid'])
        os.chmod(path, previous['mode'])
        state.get('pending_apply', {}).pop(name, None)
        save_state(state)
        print(f'Restored permissions: {path}')



def secure_state_directory():
    # Every installed-state ancestor is root controlled. Refuse rather than
    # repair a pre-existing unsafe path, and never follow a state/lock symlink.
    for parent in STATE.parents:
        if parent.is_symlink():
            raise OSError(f'Symlinked permission-state parent: {parent}')
        if parent.exists():
            attrs = parent.stat()
            if not stat.S_ISDIR(attrs.st_mode) or attrs.st_uid != 0 or stat.S_IMODE(attrs.st_mode) & 0o022:
                raise OSError(f'Unsafe permission-state parent: {parent}')
    STATE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(STATE.parent.stat().st_mode) & 0o077:
        raise OSError(f'Permission-state directory must be private: {STATE.parent}')
    for path in (STATE, STATE.parent / 'lock'):
        if path.is_symlink():
            raise OSError(f'Symlinked permission-state file: {path}')
        if path.exists():
            attrs = path.stat()
            if not stat.S_ISREG(attrs.st_mode) or attrs.st_uid != 0 or stat.S_IMODE(attrs.st_mode) & 0o077:
                raise OSError(f'Unsafe permission-state file: {path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['apply', 'restore'])
    command = parser.parse_args().command
    if os.geteuid() != 0:
        parser.error('Run as root.')
    check_device()
    secure_state_directory()
    descriptor = os.open(STATE.parent / 'lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if command == 'apply':
            apply()
        else:
            restore()


if __name__ == '__main__':
    main()
