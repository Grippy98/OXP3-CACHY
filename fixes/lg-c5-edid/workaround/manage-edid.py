#!/usr/bin/env python3
"""Capture a user's valid LG TV EDID and manage a Limine/mkinitcpio override."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import stat
import tempfile

ROOT = Path('/')
OWNER_UID = 0
STATE = Path('/var/lib/oxp3-cachy/display-edid')
MANIFEST = STATE / 'installed.json'
LIVE = Path('/sys/module/drm/parameters/edid_firmware')
REBUILD = '/usr/bin/limine-mkinitcpio'


def validate_edid(data):
    if len(data) < 256 or len(data) % 128:
        raise ValueError('Expected a complete LG TV EDID with extension blocks')
    if data[:8] != bytes.fromhex('00ffffffffffff00'):
        raise ValueError('Invalid EDID base header; first restore a working TV connection')
    if len(data) != 128 * (1 + data[126]):
        raise ValueError('EDID extension count does not match the supplied length')
    if any(sum(data[i:i + 128]) % 256 for i in range(0, len(data), 128)):
        raise ValueError('EDID block checksum failed; do not save a broken detection result')
    manufacturer = (data[8] << 8) | data[9]
    vendor = ''.join(chr(64 + ((manufacturer >> shift) & 31)) for shift in (10, 5, 0))
    names = [data[i + 5:i + 18].decode('ascii', errors='replace').strip('\n\0 ')
             for i in range(54, 126, 18) if data[i:i + 5] == b'\x00\x00\x00\xfc\x00']
    if vendor != 'GSM' or not any(name.startswith('LG TV') for name in names):
        raise ValueError('This workaround is restricted to an LG TV EDID (GSM, LG TV name)')
    if not any(data[i] == 0x02 for i in range(128, len(data), 128)):
        raise ValueError('Missing CTA extension; reject generic/fallback display data')
    return names[0]


def secure_path(path):
    """All existing root-managed components must resist unprivileged replacement."""
    try:
        parts = path.relative_to(ROOT).parts
    except ValueError:
        raise RuntimeError(f'Path escapes managed root: {path}')
    current = ROOT
    for part in ('',) + parts:
        current = current / part if part else current
        try:
            info = current.lstat()
        except FileNotFoundError:
            break
        if stat.S_ISLNK(info.st_mode) or info.st_uid != OWNER_UID or info.st_mode & 0o022:
            raise RuntimeError(f'Unsafe ownership, permissions or symlink in managed path: {current}')
        if current != path and not stat.S_ISDIR(info.st_mode):
            raise RuntimeError(f'Non-directory managed parent: {current}')


def atomic(path, data, mode=0o644):
    secure_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.oxp3-edid-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            os.fchmod(out.fileno(), mode)
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def check():
    problems = []
    if sys.platform != 'linux':
        problems.append('Linux is required')
    else:
        try:
            model = Path('/sys/class/dmi/id/product_name').read_text().strip()
            cpu = Path('/proc/cpuinfo').read_text()
            if model.upper() != 'ONEXPLAYER 3' or 'GenuineIntel' not in cpu:
                problems.append('Intel ONEXPLAYER 3 required')
        except OSError:
            problems.append('Cannot verify Intel ONEXPLAYER 3 hardware')
    if not Path('/usr/bin/pacman').is_file():
        problems.append('CachyOS/Arch with pacman is required')
    if not Path(REBUILD).is_file():
        problems.append('CachyOS limine-mkinitcpio is required')
    for path in ['/etc/limine-entry-tool.d', '/etc/mkinitcpio.conf.d']:
        if not Path(path).is_dir():
            problems.append(f'Missing {path}')
    if problems:
        raise RuntimeError('; '.join(problems))
    print('display-edid: Limine/mkinitcpio prerequisites available; installation requires --connector and --capture or --edid')


def rebuild():
    result = subprocess.run([REBUILD], env={'PATH': '/usr/bin:/usr/sbin:/bin:/sbin',
                            'HOME': '/root', 'LANG': 'C.UTF-8'}, check=False)
    if result.returncode:
        raise RuntimeError('limine-mkinitcpio failed; original managed files will be restored')


def file_data(path):
    secure_path(path)
    if path.is_symlink():
        raise RuntimeError(f'Refusing symlink: {path}')
    if path.exists() and not path.is_file():
        raise RuntimeError(f'Expected a regular file: {path}')
    return path.read_bytes() if path.exists() else None


def restore(records):
    for record in records:
        path = Path(record['path'])
        backup = record['backup']
        if backup is None:
            path.unlink(missing_ok=True)
        else:
            atomic(path, (STATE / backup).read_bytes(), record['mode'])


def install(args):
    if not args.connector or bool(args.capture) == bool(args.edid):
        raise ValueError('Specify --connector DP-1 and exactly one of --capture or --edid FILE')
    if not re.fullmatch(r'(?:DP|HDMI-A)-[1-9][0-9]*', args.connector):
        raise ValueError('Expected an external DRM connector name, such as DP-1')
    if MANIFEST.exists():
        raise RuntimeError('An override is already managed; roll it back before installing another')
    if LIVE.exists():
        overrides = LIVE.read_text().strip().split(',')
        if any(e for e in overrides):
            raise RuntimeError('An EDID firmware override is already active; disable it before capturing/installing')
    for directory in ['etc/limine-entry-tool.d', 'etc/default']:
        for config in (ROOT / directory).glob('*.conf' if directory.endswith('.d') else 'limine'):
            if config.name != '20-oxp3-lg-edid.conf' and 'drm.edid_firmware=' in config.read_text():
                raise RuntimeError(f'Existing startup EDID override in {config}; resolve it first')
    if args.capture:
        connectors = list(Path('/sys/class/drm').glob(f'card[0-9]*-{args.connector}'))
        connected = [p for p in connectors if (p / 'status').read_text().strip() == 'connected']
        if len(connected) != 1:
            raise RuntimeError('Expected exactly one connected DRM output with that name')
        port = connected[0]
        if '3840x2160' not in (port / 'modes').read_text().splitlines():
            raise RuntimeError('TV currently lacks a 3840x2160 mode; recover normal detection before capture')
        data = (port / 'edid').read_bytes()
    else:
        data = args.edid.read_bytes()
    name = validate_edid(data)
    firmware = ROOT / f'usr/lib/firmware/edid/oxp3-lg-c5-{args.connector}.bin'
    entry = f'{args.connector}:edid/{firmware.name}'
    targets = {
        firmware: data,
        (ROOT / 'etc/limine-entry-tool.d/20-oxp3-lg-edid.conf'):
            (f'# OXP3-CACHY: connector-scoped LG TV EDID captured by this user.\n'
             f'KERNEL_CMDLINE[default]+=" drm.edid_firmware={entry}"\n').encode(),
        (ROOT / 'etc/mkinitcpio.conf.d/20-oxp3-lg-edid.conf'):
            (f'# OXP3-CACHY: include the saved EDID before graphics initialization.\n'
             f'FILES+=({firmware})\n').encode(),
    }
    records = []
    for number, (path, content) in enumerate(targets.items()):
        before = file_data(path)
        backup = f'previous-{number}' if before is not None else None
        if before is not None:
            atomic(STATE / backup, before, 0o600)
        records.append({'path': str(path), 'backup': backup,
                        'mode': (path.stat().st_mode & 0o777) if before is not None else 0o644,
                        'installed_sha256': hashlib.sha256(content).hexdigest()})
    record = {'schema': 1, 'connector': args.connector, 'display_name': name,
              'files': records, 'status': 'installing'}
    atomic(MANIFEST, (json.dumps(record, indent=2) + '\n').encode(), 0o600)
    try:
        for path, content in targets.items():
            atomic(path, content)
        rebuild()
    except BaseException:
        restore(records)
        # Rebuild old startup files as well as restoring their source snippets.
        try:
            rebuild()
        except Exception:
            print('Recovery rebuild failed; inspect boot/initramfs before restarting. State retained at ' + str(STATE), file=sys.stderr)
        else:
            MANIFEST.unlink(missing_ok=True)
        raise
    record['status'] = 'installed'
    atomic(MANIFEST, (json.dumps(record, indent=2) + '\n').encode(), 0o600)
    print(f'Saved {name} for {args.connector}. Startup files rebuilt; the override becomes active at next boot. No reboot was performed.')


def rollback():
    if not MANIFEST.exists():
        print('No managed LG EDID override to roll back')
        return
    record = json.loads(MANIFEST.read_text())
    if record.get('schema') != 1:
        raise RuntimeError('Unsupported installation state')
    current = {}
    for item in record['files']:
        path = Path(item['path'])
        data = file_data(path)
        if data is None or hashlib.sha256(data).hexdigest() != item['installed_sha256']:
            raise RuntimeError(f'Managed file changed or is missing: {path}; preserving it for manual review')
        current[path] = data
    restore(record['files'])
    try:
        rebuild()
    except BaseException:
        for path, data in current.items():
            atomic(path, data)
        try:
            rebuild()
        except Exception:
            print('Recovery rebuild failed; inspect startup files before restarting.', file=sys.stderr)
        raise
    MANIFEST.unlink()
    for item in record['files']:
        if item['backup']:
            (STATE / item['backup']).unlink(missing_ok=True)
    print('Previous EDID files and startup configuration restored; initramfs regenerated. No reboot was performed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'rollback', 'check'])
    parser.add_argument('--connector')
    parser.add_argument('--capture', action='store_true', help='read the currently working LG TV EDID from sysfs')
    parser.add_argument('--edid', type=Path, help='use your own complete known-good LG TV EDID')
    args = parser.parse_args()
    check()
    if args.action == 'check':
        return
    if os.geteuid() != 0:
        raise RuntimeError('Run through sudo to manage firmware/initramfs files')
    os.umask(0o022)
    secure_path(STATE)
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    secure_path(MANIFEST)
    lock_path = STATE / 'lock'
    secure_path(lock_path)
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        os.close(descriptor)
        raise RuntimeError('Unsafe installation lock')
    with os.fdopen(descriptor, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.action == 'install':
            install(args)
        else:
            rollback()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        sys.exit(str(error))
