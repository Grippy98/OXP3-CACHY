#!/usr/bin/env python3
"""Install or roll back only the OXP3 telemetry permission helper."""

import argparse
import datetime
import fcntl
import grp
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

SOURCE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('onex3_deployment', SOURCE.parent / 'tdp/deploy.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
STATE_ROOT = Path('/var/lib/onex3-fixes/metrics-install')
UNIT = 'onex3-metrics-permissions.service'
RULE = Path('/etc/udev/rules.d/90-onex3-metrics.rules')
HELPER = Path('/usr/local/lib/onex3-metrics/onex3_metrics_permissions.py')


def payload():
    return {
        HELPER: (SOURCE / 'onex3_metrics_permissions.py').read_bytes(),
        Path('/etc/systemd/system') / UNIT: (SOURCE / 'rootfs/etc/systemd/system' / UNIT).read_bytes(),
        RULE: (SOURCE / 'rootfs/etc/udev/rules.d/90-onex3-metrics.rules').read_bytes(),
    }


def check_prerequisites():
    if sys.platform != 'linux':
        raise RuntimeError('This fix requires the ONEXPLAYER 3 Linux host.')
    for name in ('/usr/bin/python3', '/usr/bin/systemctl', '/usr/bin/udevadm'):
        if not os.access(name, os.X_OK):
            raise RuntimeError(f'Required executable missing: {name}')
    if not Path('/run/systemd/system').is_dir():
        raise RuntimeError('A running systemd system manager is required.')
    grp.getgrnam('video')
    helper_spec = importlib.util.spec_from_file_location('onex3_metrics_source', SOURCE / 'onex3_metrics_permissions.py')
    helper = importlib.util.module_from_spec(helper_spec)
    helper_spec.loader.exec_module(helper)
    helper.check_device()
    if not helper.candidates():
        raise RuntimeError('No supported RAPL/PMT telemetry source was found.')
    for path in payload():
        shared.safe_system_parent(path)
    print('Metrics prerequisites and supported sensors found (read-only check).')


def rules_reload():
    shared.run(['/usr/bin/udevadm', 'control', '--reload-rules'])
    shared.run(['/usr/bin/udevadm', 'settle', '--timeout=30'])


def stopped():
    result = shared.control(None, 'show', UNIT, '--property=ActiveState', '--property=Result', '--property=ExecMainStatus')
    values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    if (values.get('ActiveState') != 'inactive' or values.get('Result') != 'success'
            or values.get('ExecMainStatus') != '0'):
        raise RuntimeError(f'Permission restoration failed: {values}; helper and backups retained.')


def restore_file(path, entry, directory):
    now = shared.fingerprint(path)
    if now == entry['before']:
        return True
    if now != entry['applied']:
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
            raise RuntimeError(f'Backup integrity check failed: {path}')
        shared.atomic_file(path, data, before['mode'], before['uid'], before['gid'])
    return True


def rollback(record):
    shared.safe_system_parent(record)
    state = json.loads(record.read_text())
    for name in state['files']:
        shared.safe_system_parent(Path(name))
    current = shared.service_state(None, UNIT, allow_protected=True)
    # Stop future udev invocations before allowing ExecStop to restore attrs.
    rule = state['files'][str(RULE)]
    now = shared.fingerprint(RULE)
    if now not in (rule['applied'], rule['before'], {'kind': 'missing'}):
        raise RuntimeError('Udev rule changed after installation; retain it for review before rollback.')
    if now['kind'] != 'missing':
        RULE.unlink()
    rules_reload()
    # This deliberate temporary deletion is part of our own rollback.
    rule_for_restore = dict(rule, applied={'kind': 'missing'})
    if current['enabled'] != 'not-found':
        shared.control(None, 'stop', UNIT)
        stopped()
    conflicts = shared.restore_enable(None, UNIT, state['service_before'], state.get('service_applied'),
                                     current, state['links_before'], state.get('links_applied', {}))
    for name, entry in reversed(list(state['files'].items())):
        path = Path(name)
        shared.safe_system_parent(path)
        if not restore_file(path, rule_for_restore if path == RULE else entry, record.parent):
            conflicts.append(name)
    shared.control(None, 'daemon-reload')
    rules_reload()
    before, applied = state['service_before'], state.get('service_applied')
    changed = applied and current != applied
    if not conflicts and not changed and before['active'] == 'active':
        shared.control(None, 'restart', UNIT)
    elif changed:
        print('Preserved later service state; permission service left stopped.')
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
    return not conflicts


def install():
    check_prerequisites()
    active = STATE_ROOT / 'active.json'
    if active.exists():
        raise RuntimeError('An installation is already recorded; roll it back before reinstalling.')
    files = payload()
    before = shared.service_state(None, UNIT)
    identifier = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + f'-{os.getpid()}'
    directory = STATE_ROOT / identifier
    directory.mkdir(mode=0o700)
    record = directory / 'state.json'
    state = {'schema': 1, 'phase': 'prepared', 'service_before': before, 'service_applied': None,
             'links_before': shared.enable_links(None, UNIT), 'links_applied': {},
             'created_directories': [], 'files': {}}
    for index, (path, data) in enumerate(files.items()):
        shared.safe_system_parent(path)
        previous = shared.fingerprint(path)
        entry = {'before': previous, 'applied': {'kind': 'file', 'sha256': hashlib.sha256(data).hexdigest(),
                 'uid': 0, 'gid': 0, 'mode': 0o644}}
        if previous['kind'] == 'file':
            entry['backup'] = f'backup-{index}'
            shared.atomic_file(directory / entry['backup'], path.read_bytes(), 0o600)
        state['files'][str(path)] = entry
    shared.save(record, state)
    shared.save(active, {'state': str(record)})
    try:
        if RULE.exists() or RULE.is_symlink():
            RULE.unlink()
            rules_reload()
        if before['enabled'] != 'not-found':
            shared.control(None, 'stop', UNIT)
            stopped()
        for path, data in files.items():
            shared.ensure_parent(path, state)
            shared.save(record, state)
            shared.atomic_file(path, data)
        shared.control(None, 'daemon-reload')
        rules_reload()
        shared.control(None, 'enable', UNIT)
        state['service_applied'] = shared.service_state(None, UNIT)
        state['links_applied'] = shared.enable_links(None, UNIT)
        shared.save(record, state)
        shared.control(None, 'start', UNIT)
        state['service_applied'] = shared.service_state(None, UNIT)
        if state['service_applied']['active'] != 'active':
            raise RuntimeError('Telemetry permission service did not become active.')
        state['phase'] = 'installed'
        shared.save(record, state)
    except Exception:
        print('Installation failed; restoring the recorded deployment baseline.', file=sys.stderr)
        state['service_applied'] = shared.service_state(None, UNIT)
        state['links_applied'] = shared.enable_links(None, UNIT)
        shared.save(record, state)
        rollback(record)
        raise
    print(f'Installed. Deployment baseline: {record}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['install', 'rollback'])
    parser.add_argument('--check', action='store_true', help='read-only prerequisite and sensor check')
    args = parser.parse_args()
    if args.check:
        check_prerequisites()
        return
    if sys.platform != 'linux' or os.geteuid() != 0:
        parser.error('Run on the Linux device as root.')
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
            install()
        else:
            active = STATE_ROOT / 'active.json'
            if not active.exists():
                parser.error('No installation recorded by this tool; use the original deployment backup.')
            record = Path(json.loads(active.read_text())['state'])
            if record.parent.parent != STATE_ROOT or record.is_symlink():
                parser.error('Unsafe installation record.')
            if not rollback(record):
                raise SystemExit('Rollback preserved later changes; inspect state.json before retrying.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error)) from error
