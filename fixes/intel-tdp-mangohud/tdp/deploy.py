#!/usr/bin/env python3
"""Scoped local install/rollback; never installs or removes distribution packages."""

import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parent
STATE_ROOT = Path('/var/lib/onex3-fixes/tdp-install')
PROVIDER = 'onex3-tdp.service'
MANAGER = 'steamos-manager.service'
OLD_ACTIVATION = Path('/usr/share/dbus-1/system-services/org.onex3.SteamOSManager.PowerControl.service')
DEST = Path('/usr/local/lib/onex3-fixes/tdp')
ENABLE_STATES = {'enabled', 'enabled-runtime', 'disabled', 'static', 'indirect', 'not-found'}
ROOTFS_FILES = (
    'etc/onex3-tdp.json',
    'etc/steamos-manager/remotes.d/onex3-tdp.toml',
    'etc/dbus-1/system.d/org.onex3.SteamOSManager.PowerControl.conf',
    'etc/systemd/system/onex3-tdp.service',
    'etc/systemd/user/steamos-manager.service.d/80-onex3-tdp.conf',
    'usr/share/dbus-1/system-services/org.onex3.PowerControlActivator.service',
)


def run(args, *, check=True):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=40)
    if check and result.returncode:
        raise RuntimeError(f'{args!r} failed: {result.stderr.strip()}')
    return result


def control(user, *args, check=True):
    if user is None:
        command = ['/usr/bin/systemctl', *args]
    else:
        uid = pwd.getpwnam(user).pw_uid
        command = ['/usr/bin/runuser', '-u', user, '--', '/usr/bin/env',
                   f'XDG_RUNTIME_DIR=/run/user/{uid}',
                   f'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus',
                   '/usr/bin/systemctl', '--user', *args]
    return run(command, check=check)


def service_state(user, unit, allow_protected=False):
    enabled = control(user, 'is-enabled', unit, check=False)
    # "not-found" is sometimes emitted on stderr rather than stdout.
    missing = any(text in enabled.stderr for text in (
        'does not exist', 'not found', 'could not be found', 'No such file or directory'))
    value = enabled.stdout.strip() or ('not-found' if missing else '')
    allowed = ENABLE_STATES | ({'masked', 'masked-runtime'} if allow_protected else set())
    if value not in allowed:
        raise RuntimeError(f'Unsupported or protected enable state for {unit}: {value!r}; resolve it before install/rollback.')
    active = control(user, 'show', unit, '--property=ActiveState', '--value', check=False).stdout.strip()
    if active not in {'active', 'inactive', 'failed', ''}:
        raise RuntimeError(f'{unit} is changing state ({active}); wait for it to settle.')
    return {'enabled': value, 'active': active or 'inactive'}


def enable_links(user, unit):
    if user is None:
        roots = [Path('/etc/systemd/system'), Path('/run/systemd/system')]
    else:
        account = pwd.getpwnam(user)
        roots = [Path(account.pw_dir) / '.config/systemd/user',
                 Path(f'/run/user/{account.pw_uid}/systemd/user')]
    links = {}
    for root in roots:
        if root.is_symlink():
            raise RuntimeError(f'Refusing symlinked systemd configuration: {root}')
        if user is None:
            safe_system_parent(root / '.onex3-parent-check')
        if not root.exists():
            continue
        for path in root.rglob('*'):
            if path.is_symlink() and (path.name == unit or Path(os.readlink(path)).name == unit):
                # The unit path itself is covered separately by the payload
                # snapshot; enable links live below target.wants/requires or
                # alias names, rather than replacing that unit definition.
                if path == root / unit:
                    continue
                links[str(path)] = fingerprint(path)
    return links


def safe_parent(path):
    for ancestor in path.parents:
        if ancestor.is_symlink():
            raise RuntimeError(f'Refusing a symlinked parent: {ancestor}')


def safe_system_parent(path):
    """Validate existing system parents without changing their attributes."""
    safe_parent(path)
    for ancestor in path.parents:
        if not ancestor.exists():
            continue
        before = ancestor.stat()
        if (not stat.S_ISDIR(before.st_mode) or before.st_uid != 0
                or stat.S_IMODE(before.st_mode) & 0o022):
            raise RuntimeError(f'Refusing unsafe system parent: {ancestor}; require a root-owned directory without group/world writes.')


def fingerprint(path):
    if not path.exists() and not path.is_symlink():
        return {'kind': 'missing'}
    st = path.lstat()
    attrs = {'uid': st.st_uid, 'gid': st.st_gid, 'mode': stat.S_IMODE(st.st_mode)}
    if stat.S_ISLNK(st.st_mode):
        return {'kind': 'symlink', 'target': os.readlink(path), **attrs}
    if not stat.S_ISREG(st.st_mode):
        raise RuntimeError(f'Refusing non-regular destination: {path}')
    return {'kind': 'file', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), **attrs}


def save(path, value):
    data = (json.dumps(value, indent=2) + '\n').encode()
    atomic_file(path, data, 0o600, 0, 0)


def atomic_file(path, data, mode=0o644, uid=0, gid=0):
    safe_system_parent(path)
    descriptor, temporary = tempfile.mkstemp(prefix='.onex3-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
            os.fchown(stream.fileno(), uid, gid)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def ensure_parent(path, state):
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    safe_system_parent(path)
    for directory in reversed(missing):
        directory.mkdir(mode=0o755)
        state['created_directories'].append(str(directory))


def payload(user):
    files = {}
    for name in ROOTFS_FILES:
        path = SOURCE / 'rootfs' / name
        if path.is_symlink():
            raise RuntimeError(f'Refusing a symlink in payload: {path}')
        files[Path('/') / name] = path.read_bytes()
    for name in ('onex3_tdp.py', 'onex3_tdp_hook.py'):
        files[DEST / name] = (SOURCE / name).read_bytes()
    config_path = Path('/etc/onex3-tdp.json')
    config = json.loads(files[config_path])
    config['session_user'] = user
    # Configuration expresses local policy. It does not probe or write hardware.
    if not (isinstance(config.get('min_w'), int) and not isinstance(config['min_w'], bool)
            and isinstance(config.get('max_w'), int) and not isinstance(config['max_w'], bool)
            and 1 <= config['min_w'] <= config['max_w'] <= 200):
        raise RuntimeError('Invalid configured TDP policy range.')
    files[config_path] = (json.dumps(config, indent=2) + '\n').encode()
    policy = Path('/etc/dbus-1/system.d/org.onex3.SteamOSManager.PowerControl.conf')
    files[policy] = files[policy].replace(b'<policy user="ONEX3_SESSION_USER">', f'<policy user="{user}">'.encode())
    return files


def check_prerequisites(user):
    if sys.platform != 'linux':
        raise RuntimeError('This fix requires the ONEXPLAYER 3 Linux host.')
    for executable in ('/usr/bin/python3', '/usr/bin/systemctl', '/usr/bin/runuser', '/usr/bin/env'):
        if not os.access(executable, os.X_OK):
            raise RuntimeError(f'Required executable missing: {executable}')
    if not Path('/run/systemd/system').is_dir():
        raise RuntimeError('A running systemd system manager is required.')
    if importlib.util.find_spec('dbus_next') is None:
        raise RuntimeError('Install python-dbus-next separately first.')
    if not Path('/usr/lib/steamos-manager').is_file():
        raise RuntimeError('Install the native steamos-manager package separately first.')
    spec = importlib.util.spec_from_file_location('onex3_tdp_source', SOURCE / 'onex3_tdp.py')
    provider = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(provider)
    provider.check_device()
    for path in payload(user or 'ONEX3_SESSION_USER'):
        safe_system_parent(path)
    print('TDP prerequisites found (read-only check; root install also verifies RAPL access).')


def validate_host(user):
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise RuntimeError('Run this on the ONEXPLAYER 3 Linux host as root.')
    check_prerequisites(user)
    if not user or not user.replace('_', '').replace('-', '').isalnum():
        raise RuntimeError('Unsupported session user name.')
    account = pwd.getpwnam(user)
    if account.pw_uid == 0 or not Path(f'/run/user/{account.pw_uid}/bus').exists():
        raise RuntimeError('The non-root session user must be logged in with a running user D-Bus.')
    run(['/usr/bin/python3', str(SOURCE / 'onex3_tdp.py'), 'status', '--config', str(SOURCE / 'rootfs/etc/onex3-tdp.json')])


def reload_managers(user):
    control(None, 'daemon-reload')
    control(None, 'reload', 'dbus')
    control(user, 'daemon-reload')


def verify_provider_stopped():
    result = control(None, 'show', PROVIDER, '--property=ActiveState',
                     '--property=Result', '--property=ExecMainStatus')
    values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    if (values.get('ActiveState') != 'inactive' or values.get('Result') != 'success'
            or values.get('ExecMainStatus') != '0'):
        raise RuntimeError(f'Provider cleanup was not successful ({values}); retained source and backups for hardware restoration review.')


def restore_enable(user, unit, before, applied, current, links_before, links_applied):
    if not applied or current['enabled'] != applied['enabled']:
        if applied and current['enabled'] != applied['enabled']:
            print(f'Preserved later enable-state change for {unit}: {current["enabled"]}')
        return []
    conflicts = []
    now = enable_links(user, unit)
    for name in sorted(set(links_before) | set(links_applied)):
        previous = links_before.get(name, {'kind': 'missing'})
        installed = links_applied.get(name, {'kind': 'missing'})
        current_link = now.get(name, {'kind': 'missing'})
        if current_link == previous:
            continue
        if current_link != installed:
            conflicts.append(name)
            print(f'Preserved later enable-link change: {name}')
            continue
        path = Path(name)
        if user is None:
            safe_system_parent(path)
        else:
            safe_parent(path)
        path.unlink(missing_ok=True)
        if previous['kind'] == 'symlink':
            path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            os.symlink(previous['target'], path)
            os.lchown(path, previous['uid'], previous['gid'])
    for name in set(now) - set(links_before) - set(links_applied):
        conflicts.append(name)
        print(f'Preserved later new enable link: {name}')
    return conflicts


def rollback(state_path):
    safe_system_parent(state_path)
    state = json.loads(state_path.read_text())
    user = state['session_user']
    # Capture administrator changes before the required provider stop.
    current = {key: service_state(who, unit, allow_protected=True) for key, who, unit in (
        ('provider', None, PROVIDER), ('manager', user, MANAGER))}
    if current['provider']['enabled'] != 'not-found':
        control(None, 'stop', PROVIDER)
        verify_provider_stopped()
    conflicts = []
    for key, who, unit in (('provider', None, PROVIDER), ('manager', user, MANAGER)):
        conflicts.extend(restore_enable(who, unit, state['services_before'][key],
            state['services_applied'].get(key), current[key],
            state['enable_links_before'][key], state['enable_links_applied'].get(key, {})))
    for name, entry in reversed(list(state['files'].items())):
        path = Path(name)
        safe_system_parent(path)
        now = fingerprint(path)
        if now == entry['before']:
            continue  # Already restored, or install failed before this file changed.
        if now != entry['applied']:
            conflicts.append(name)
            print(f'Preserved later file change: {name}')
            continue
        previous = entry['before']
        if previous['kind'] == 'missing':
            path.unlink(missing_ok=True)
        elif previous['kind'] == 'symlink':
            path.unlink(missing_ok=True)
            os.symlink(previous['target'], path)
            os.lchown(path, previous['uid'], previous['gid'])
        else:
            original = (state_path.parent / entry['backup']).read_bytes()
            if hashlib.sha256(original).hexdigest() != previous['sha256']:
                raise RuntimeError(f'Backup integrity check failed for {name}; left remaining files for review.')
            atomic_file(path, original,
                        previous['mode'], previous['uid'], previous['gid'])
    reload_managers(user)
    for key, who, unit in (('provider', None, PROVIDER), ('manager', user, MANAGER)):
        before = state['services_before'][key]
        applied = state['services_applied'].get(key)
        # Provider was stopped for restoration; resume its pre-install service
        # only if the saved unit was restored and no later service change exists.
        unit_file = '/etc/systemd/system/onex3-tdp.service' if key == 'provider' else None
        changed = applied and (current[key]['active'] != applied['active']
                               or current[key]['enabled'] != applied['enabled'])
        if conflicts or unit_file in conflicts or changed:
            print(f'Preserved later service change; left {unit} stopped/unchanged.')
        elif before['active'] == 'active':
            control(who, 'restart', unit)
        elif applied:
            control(who, 'stop', unit, check=False)
    for directory in reversed(state['created_directories']):
        try:
            Path(directory).rmdir()
        except OSError:
            pass
    state['phase'] = 'rollback_conflicts' if conflicts else 'rolled_back'
    state['rollback_conflicts'] = conflicts
    save(state_path, state)
    if not conflicts:
        (STATE_ROOT / 'active.json').unlink(missing_ok=True)
    print(f'Rollback record retained: {state_path}')
    return not conflicts


def install(user):
    validate_host(user)
    safe_system_parent(STATE_ROOT / 'active.json')
    active_path = STATE_ROOT / 'active.json'
    if active_path.exists():
        raise RuntimeError('A recorded installation already exists. Roll it back before reinstalling; its baseline will not be overwritten.')
    files = payload(user)
    if OLD_ACTIVATION.exists() or OLD_ACTIVATION.is_symlink():
        safe_system_parent(OLD_ACTIVATION)
        if OLD_ACTIVATION.is_symlink():
            raise RuntimeError('Old provider activation name is a symlink; resolve it before install.')
        contents = OLD_ACTIVATION.read_text()
        if 'Name=org.onex3.SteamOSManager.PowerControl' not in contents or str(DEST / 'onex3_tdp.py') not in contents:
            raise RuntimeError('Conflicting old provider-name activation file; review it before install.')
        files[OLD_ACTIVATION] = None
    for path in files:
        safe_system_parent(path)
    services = {key: service_state(who, unit) for key, who, unit in (
        ('provider', None, PROVIDER), ('manager', user, MANAGER))}
    identifier = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + f'-{os.getpid()}'
    directory = STATE_ROOT / identifier
    directory.mkdir(mode=0o700)
    state_path = directory / 'state.json'
    state = {'schema': 1, 'phase': 'prepared', 'session_user': user,
             'services_before': services, 'services_applied': {},
             'enable_links_before': {key: enable_links(who, unit) for key, who, unit in (
                 ('provider', None, PROVIDER), ('manager', user, MANAGER))},
             'enable_links_applied': {}, 'created_directories': [], 'files': {}}
    for index, (path, data) in enumerate(files.items()):
        safe_system_parent(path)
        before = fingerprint(path)
        entry = {'before': before, 'applied': {'kind': 'missing'} if data is None else {
            'kind': 'file', 'sha256': hashlib.sha256(data).hexdigest(), 'mode': 0o644, 'uid': 0, 'gid': 0}}
        if before['kind'] == 'file':
            entry['backup'] = f'backup-{index}'
            atomic_file(directory / entry['backup'], path.read_bytes(), 0o600)
        state['files'][str(path)] = entry
    save(state_path, state)
    save(active_path, {'state': str(state_path)})
    try:
        if services['provider']['enabled'] != 'not-found':
            control(None, 'stop', PROVIDER)
            verify_provider_stopped()
        for path, data in files.items():
            ensure_parent(path, state)
            save(state_path, state)
            if data is None:
                path.unlink(missing_ok=True)
            else:
                atomic_file(path, data)
        reload_managers(user)
        control(user, 'enable', MANAGER)
        state['services_applied']['manager'] = service_state(user, MANAGER)
        state['enable_links_applied']['manager'] = enable_links(user, MANAGER)
        save(state_path, state)
        control(user, 'restart', MANAGER)
        state['services_applied']['manager'] = service_state(user, MANAGER)
        save(state_path, state)
        control(None, 'enable', PROVIDER)
        state['services_applied']['provider'] = service_state(None, PROVIDER)
        state['enable_links_applied']['provider'] = enable_links(None, PROVIDER)
        save(state_path, state)
        control(None, 'start', PROVIDER)
        state['services_applied']['provider'] = service_state(None, PROVIDER)
        state['phase'] = 'installed'
        save(state_path, state)
    except Exception:
        print('Installation failed; restoring the recorded deployment baseline.', file=sys.stderr)
        # Capture completed enable/start operations even when a following
        # command failed, so rollback restores their pre-install states too.
        for key, who, unit in (('provider', None, PROVIDER), ('manager', user, MANAGER)):
            state['services_applied'][key] = service_state(who, unit)
            state['enable_links_applied'][key] = enable_links(who, unit)
        save(state_path, state)
        rollback(state_path)
        raise
    print(f'Installed. Deployment baseline: {state_path}')
    print('No TDP value was requested by this installer. Restart Steam after native D-Bus validation.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['install', 'rollback'])
    parser.add_argument('--session-user', default=os.environ.get('SUDO_USER'),
                        help='logged-in desktop user (default: SUDO_USER)')
    parser.add_argument('--check', action='store_true', help='read-only prerequisite check')
    args = parser.parse_args()
    if args.check:
        check_prerequisites(args.session_user)
        return
    if os.geteuid() != 0 or sys.platform != 'linux':
        parser.error('Run on the Linux device as root.')
    safe_system_parent(STATE_ROOT / 'lock')
    if not STATE_ROOT.exists():
        # Explicit modes avoid inheriting a permissive root umask for the
        # intermediate state directory. Existing directories are never fixed.
        ensure_parent(STATE_ROOT, {'created_directories': []})
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
            install(args.session_user)
        else:
            active = STATE_ROOT / 'active.json'
            if not active.exists():
                parser.error('No installation recorded by this tool; use the original deployment backup.')
            record = Path(json.loads(active.read_text())['state'])
            if record.parent.parent != STATE_ROOT or record.is_symlink():
                parser.error('Unsafe installation record.')
            if not rollback(record):
                raise SystemExit('Rollback preserved changed files; review conflicts in state.json before retrying.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error)) from error
