#!/usr/bin/env python3
"""Install a matching oxpec module and provider, preserving charge limit and bypass."""

import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import pwd
import subprocess
import sys

SOURCE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('onex3_charge_deployment_shared',
    SOURCE.parent / 'intel-tdp-mangohud/tdp/deploy.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
STATE_ROOT = Path('/var/lib/onex3-fixes/charge-limit-install')
MODULE_ROOT = Path('/usr/lib/modules')
MODULE_STATE = Path('/sys/module/oxpec')
THRESHOLD = Path('/sys/class/power_supply/BAT0/charge_control_end_threshold')
BEHAVIOUR = Path('/sys/class/power_supply/BAT0/charge_behaviour')
DEST = Path('/usr/local/lib/onex3-fixes/battery-charge-limit/charge-limit-provider.py')
UNIT = 'onex3-charge-limit.service'
ROOTFS_FILES = (
    'etc/systemd/system/onex3-charge-limit.service',
    'etc/dbus-1/system.d/org.onex3.SteamOSManager.ChargeLimit.conf',
    'etc/steamos-manager/remotes.d/onex3-charge-limit.toml',
)
LOAD_CONF = Path('/etc/modules-load.d/80-onex3-charge-limit.conf')


def module_directory(release):
    return MODULE_ROOT / release / 'updates/oxp3-charge-limit'


def module_info(path, release):
    """Validate bytes and the running-kernel release; do not execute/load the module."""
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise RuntimeError('--module must name an absolute regular module file, not a symlink.')
    if path.name.endswith('.ko.zst'):
        suffix = '.ko.zst'
    elif path.name.endswith('.ko'):
        suffix = '.ko'
    else:
        raise RuntimeError('Only .ko and .ko.zst module artifacts are accepted.')
    data = path.read_bytes()
    name = shared.run(['/usr/bin/modinfo', '-F', 'name', str(path)]).stdout.strip()
    vermagic = shared.run(['/usr/bin/modinfo', '-F', 'vermagic', str(path)]).stdout.strip()
    if name != 'oxpec' or not vermagic or vermagic.split()[0] != release:
        raise RuntimeError(f'Module name/vermagic mismatch: {name!r}, {vermagic!r}; running {release}.')
    if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(data).digest():
        raise RuntimeError('Module input changed while checking it; retry with a stable artifact.')
    return suffix, data, vermagic


def read_threshold():
    value = int(THRESHOLD.read_text().strip())
    if not 0 <= value <= 100:
        raise RuntimeError(f'Unexpected charge threshold: {value}.')
    return value


def read_behaviour():
    """Read the optional selected kernel mode; never infer or program one."""
    try:
        text = BEHAVIOUR.read_text(encoding='ascii')
    except FileNotFoundError:
        return None
    modes, selected = [], []
    for token in text.split():
        active = token.startswith('[') and token.endswith(']')
        mode = token[1:-1] if active else token
        if mode not in ('auto', 'inhibit-charge', 'inhibit-charge-awake') or mode in modes:
            raise RuntimeError('Unexpected battery charge behaviour list.')
        modes.append(mode)
        if active:
            selected.append(mode)
    if len(selected) != 1:
        raise RuntimeError('Expected exactly one selected battery charge behaviour.')
    return selected[0]


def payload(user, release, module_suffix, module_data):
    files = {}
    for name in ROOTFS_FILES:
        source = SOURCE / 'rootfs' / name
        if source.is_symlink():
            raise RuntimeError(f'Refusing symlinked payload: {source}.')
        files[Path('/') / name] = source.read_bytes().replace(b'ONEX3_SESSION_USER', user.encode())
    provider = SOURCE / 'charge-limit-provider.py'
    if provider.is_symlink():
        raise RuntimeError(f'Refusing symlinked payload: {provider}.')
    files[DEST] = provider.read_bytes()
    files[LOAD_CONF] = b'oxpec\n'
    directory = module_directory(release)
    # Remove only the other compression form of our own override, with backup.
    for suffix in ('.ko', '.ko.zst'):
        files[directory / f'oxpec{suffix}'] = module_data if suffix == module_suffix else None
    return files


def check_host(user):
    if sys.platform != 'linux' or platform.machine() != 'x86_64':
        raise RuntimeError('The Intel ONEXPLAYER 3 Linux host is required.')
    for name, expected in (('board_vendor', 'ONE-NETBOOK'), ('board_name', 'ONEXPLAYER 3')):
        if (Path('/sys/class/dmi/id') / name).read_text().strip() != expected:
            raise RuntimeError('Exact ONE-NETBOOK / ONEXPLAYER 3 board identity is required.')
    if 'GenuineIntel' not in Path('/proc/cpuinfo').read_text():
        raise RuntimeError('Intel CPU required.')
    for executable in ('python3', 'systemctl', 'runuser', 'env', 'modinfo', 'modprobe', 'depmod'):
        if not os.access(f'/usr/bin/{executable}', os.X_OK):
            raise RuntimeError(f'Required executable missing: {executable}.')
    if not Path('/run/systemd/system').is_dir() or not Path('/usr/lib/steamos-manager').is_file():
        raise RuntimeError('A running systemd host and native steamos-manager package are required.')
    if importlib.util.find_spec('dbus_next') is None:
        raise RuntimeError('Install python-dbus-next separately first.')
    if not user or not user.replace('_', '').replace('-', '').isalnum():
        raise RuntimeError('Use --user with the logged-in Gaming Mode account.')
    account = pwd.getpwnam(user)
    if account.pw_uid == 0 or not Path(f'/run/user/{account.pw_uid}/bus').exists():
        raise RuntimeError('The non-root session account must have a running user D-Bus.')
    return platform.release()


def restore_file(path, entry, directory):
    shared.safe_system_parent(path)
    current = shared.fingerprint(path)
    if current == entry['before']:
        return True
    if current != entry['applied']:
        print(f'Preserved later file change: {path}')
        return False
    before = entry['before']
    if before['kind'] == 'missing':
        path.unlink(missing_ok=True)
    elif before['kind'] == 'symlink':
        path.unlink(missing_ok=True)
        os.symlink(before['target'], path)
        os.lchown(path, before['uid'], before['gid'])
    else:
        data = (directory / entry['backup']).read_bytes()
        if hashlib.sha256(data).hexdigest() != before['sha256']:
            raise RuntimeError(f'Backup integrity check failed: {path}.')
        shared.atomic_file(path, data, before['mode'], before['uid'], before['gid'])
    return True


def reload_managers(user):
    shared.control(None, 'daemon-reload')
    shared.control(None, 'reload', 'dbus')
    shared.control(user, 'daemon-reload')


def rollback(record):
    shared.safe_system_parent(record)
    state = json.loads(record.read_text())
    for name in state['files']:
        shared.safe_system_parent(Path(name))
    current = shared.service_state(None, UNIT, allow_protected=True)
    if current['enabled'] != 'not-found':
        shared.control(None, 'stop', UNIT)
    conflicts = shared.restore_enable(None, UNIT, state['service_before'],
        state.get('service_applied'), current, state['links_before'], state.get('links_applied', {}))
    for name, entry in reversed(list(state['files'].items())):
        if not restore_file(Path(name), entry, record.parent):
            conflicts.append(name)
    shared.run(['/usr/bin/depmod', '-a', state['kernel_release']])
    reload_managers(state['session_user'])
    before, applied = state['service_before'], state.get('service_applied')
    if not conflicts and (not applied or current == applied) and before['active'] == 'active':
        shared.control(None, 'start', UNIT)
    for directory in reversed(state['created_directories']):
        try:
            Path(directory).rmdir()
        except OSError:
            pass
    state['phase'] = 'rollback_conflicts' if conflicts else 'rolled_back'
    state['rollback_conflicts'] = conflicts
    shared.save(record, state)
    if not conflicts:
        (STATE_ROOT / 'active.json').unlink(missing_ok=True)
    print(f'Rollback record retained: {record}')
    print('Rollback did not write or restore the charge threshold or charge behaviour. The passive loaded oxpec module was retained; unload deliberately or reboot when appropriate.')
    return not conflicts


def install(user, module, check=False):
    release = check_host(user)
    suffix, module_data, vermagic = module_info(module, release)
    files = payload(user, release, suffix, module_data)
    for path in files:
        shared.safe_system_parent(path)
    if check:
        print(f'Read-only checks passed: oxpec for {vermagic}; no module loaded, charge threshold or charge behaviour written.')
        return
    active = STATE_ROOT / 'active.json'
    if active.exists():
        raise RuntimeError('An installation is already recorded; roll it back before reinstalling.')
    loaded_before = MODULE_STATE.exists()
    threshold_before = read_threshold() if THRESHOLD.exists() else None
    behaviour_before = read_behaviour()
    if loaded_before and threshold_before is None:
        raise RuntimeError('An existing loaded oxpec lacks charge sysfs support; resolve that module before installing.')
    previous_module = shared.run(['/usr/bin/modinfo', '-n', 'oxpec'], check=False).stdout.strip()
    before = shared.service_state(None, UNIT)
    identifier = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + f'-{os.getpid()}'
    directory = STATE_ROOT / identifier
    directory.mkdir(mode=0o700)
    record = directory / 'state.json'
    state = {'schema': 1, 'phase': 'prepared', 'session_user': user, 'kernel_release': release,
        'module_loaded_before': loaded_before, 'previous_module_path': previous_module,
        'threshold_before': threshold_before, 'charge_behaviour_before': behaviour_before,
        'service_before': before, 'service_applied': None,
        'links_before': shared.enable_links(None, UNIT), 'links_applied': {},
        'created_directories': [], 'files': {}}
    for index, (path, data) in enumerate(files.items()):
        previous = shared.fingerprint(path)
        applied = {'kind': 'missing'} if data is None else {'kind': 'file',
            'sha256': hashlib.sha256(data).hexdigest(), 'uid': 0, 'gid': 0, 'mode': 0o644}
        entry = {'before': previous, 'applied': applied}
        if previous['kind'] == 'file':
            entry['backup'] = f'backup-{index}'
            shared.atomic_file(directory / entry['backup'], path.read_bytes(), 0o600)
        state['files'][str(path)] = entry
    shared.save(record, state)
    shared.save(active, {'state': str(record)})
    try:
        if before['enabled'] != 'not-found':
            shared.control(None, 'stop', UNIT)
        for path, data in files.items():
            shared.ensure_parent(path, state)
            shared.save(record, state)
            if data is None:
                path.unlink(missing_ok=True)
            else:
                shared.atomic_file(path, data)
        shared.run(['/usr/bin/depmod', '-a', release])
        selected = shared.run(['/usr/bin/modinfo', '-n', 'oxpec']).stdout.strip()
        expected = module_directory(release) / f'oxpec{suffix}'
        if Path(selected).resolve() != expected.resolve():
            raise RuntimeError(f'depmod selected {selected!r}, not the staged module; refusing load.')
        shared.run(['/usr/bin/modprobe', 'oxpec'])
        threshold_after = read_threshold()
        if threshold_before is not None and threshold_after != threshold_before:
            raise RuntimeError('Charge threshold changed during installation; retained value is not overwritten.')
        behaviour_after = read_behaviour()
        if behaviour_before is not None and behaviour_after != behaviour_before:
            raise RuntimeError('Charge behaviour changed while loading the module; retained mode is not overwritten.')
        reload_managers(user)
        shared.control(None, 'enable', UNIT)
        state['service_applied'] = shared.service_state(None, UNIT)
        state['links_applied'] = shared.enable_links(None, UNIT)
        shared.save(record, state)
        shared.control(None, 'start', UNIT)
        state['service_applied'] = shared.service_state(None, UNIT)
        if state['service_applied']['active'] != 'active':
            raise RuntimeError('Charge-limit provider did not become active.')
        if read_threshold() != threshold_after:
            raise RuntimeError('Charge threshold changed while starting the provider; retained value is not overwritten.')
        if read_behaviour() != behaviour_after:
            raise RuntimeError('Charge behaviour changed while starting the provider; retained mode is not overwritten.')
        state['phase'] = 'installed'
        state['threshold_after'] = threshold_after
        state['charge_behaviour_after'] = behaviour_after
        shared.save(record, state)
    except Exception:
        state['service_applied'] = shared.service_state(None, UNIT, allow_protected=True)
        state['links_applied'] = shared.enable_links(None, UNIT)
        shared.save(record, state)
        print('Installation failed; restoring recorded files and provider state.', file=sys.stderr)
        rollback(record)
        raise
    print(f'Installed. BAT0 charge threshold remains {threshold_after}%; charge behaviour is {behaviour_after or "unavailable"}. Baseline: {record}')
    if loaded_before:
        print('A preexisting oxpec module stayed loaded; the staged artifact takes effect on its next load.')
    print('Restart the user steamos-manager service and Steam when convenient to refresh cached hardware features.')
    print('No Steam restart, reboot, charge-threshold write or charge-behaviour write was requested by this installer.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['install', 'rollback'])
    parser.add_argument('--module', type=Path, help='absolute oxpec.ko or oxpec.ko.zst for the running kernel')
    parser.add_argument('--user', '--session-user', default=os.environ.get('SUDO_USER'), dest='user')
    parser.add_argument('--check', action='store_true', help='read-only install prerequisites; requires --module')
    args = parser.parse_args()
    if args.command == 'install' and args.module is None:
        parser.error('install requires --module /absolute/path/oxpec.ko[.zst].')
    if args.check:
        if args.command != 'install':
            parser.error('--check is only valid for install.')
        install(args.user, args.module, check=True)
        return
    if os.geteuid() != 0 or sys.platform != 'linux':
        parser.error('Run on the Intel ONEXPLAYER 3 Linux host as root.')
    shared.safe_system_parent(STATE_ROOT / 'lock')
    if not STATE_ROOT.exists():
        shared.ensure_parent(STATE_ROOT, {'created_directories': []})
        STATE_ROOT.mkdir(mode=0o700)
    if STATE_ROOT.is_symlink() or STATE_ROOT.stat().st_uid != 0:
        parser.error('Unsafe installation-state directory.')
    os.chmod(STATE_ROOT, 0o700)
    lock_path = STATE_ROOT / 'lock'
    if lock_path.is_symlink():
        parser.error('Unsafe installation-state lock.')
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.command == 'install':
            install(args.user, args.module)
        else:
            active = STATE_ROOT / 'active.json'
            if not active.is_file():
                parser.error('No installation is recorded by this tool; nothing removed.')
            record = Path(json.loads(active.read_text())['state'])
            if record.parent.parent != STATE_ROOT or record.is_symlink():
                parser.error('Unsafe installation record.')
            if not rollback(record):
                raise SystemExit('Rollback kept later changes; review recorded conflicts before retrying.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error)) from error
