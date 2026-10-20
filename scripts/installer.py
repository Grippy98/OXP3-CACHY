#!/usr/bin/env python3
"""Menu and argument-safe dispatcher; device changes live in per-fix adapters."""
from __future__ import annotations

import json
import os
from pathlib import Path
import pwd
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def catalog():
    return {item['id']: item for item in json.loads((ROOT / 'fixes.json').read_text())}


def platform_error():
    if sys.platform != 'linux':
        return 'Installation targets the Intel ONEXPLAYER 3 running CachyOS/Arch Linux.'
    try:
        model = Path('/sys/class/dmi/id/product_name').read_text().strip()
        cpu = Path('/proc/cpuinfo').read_text()
        release = Path('/etc/os-release').read_text()
    except OSError as exc:
        return f'Cannot verify this platform: {exc}'
    if model.upper() != 'ONEXPLAYER 3' or 'GenuineIntel' not in cpu:
        return 'This installer supports the Intel ONEXPLAYER 3 only.'
    if not any(value in release.lower() for value in ('cachyos', 'arch')) or not shutil.which('pacman'):
        return 'CachyOS/Arch and pacman are required.'
    return None


def session_options(args):
    remaining, requested = [], None
    iterator = iter(args)
    for argument in iterator:
        if argument == '--session-user':
            requested = next(iterator, '')
            if not requested or requested.startswith('-'):
                raise ValueError('--session-user requires a username')
        elif argument.startswith('--session-user='):
            requested = argument.partition('=')[2]
            if not requested:
                raise ValueError('--session-user requires a username')
        else:
            remaining.append(argument)
    return remaining, requested


def session_user(args):
    name = os.environ.get('OXP3_SESSION_USER') or os.environ.get('SUDO_USER')
    _, requested = session_options(args)
    name = requested or name
    if not name and os.geteuid() != 0:
        name = pwd.getpwuid(os.getuid()).pw_name
    if not name:
        return None
    account = pwd.getpwnam(name)
    if account.pw_uid == 0:
        raise ValueError('A normal Gaming Mode session user is required')
    return account


def native_command(item, action, extra):
    if action not in item:
        raise ValueError(f"{item['id']} is manual/read-only. Read {item['docs']}")
    command = list(item[action])
    for index, argument in enumerate(command):
        if argument.startswith('fixes/'):
            command[index] = str(ROOT / argument)
    if item['id'] == 'boot-controller' and action == 'rollback' and '--remove' in extra:
        command = ['bash', str(ROOT / 'fixes/boot-controller/rollback-experimental.sh')]
        extra = [arg for arg in extra if arg != '--remove']
    return command + list(extra)


def execute(item, action, extra=()):
    if action == 'docs':
        print((ROOT / item['docs']).read_text())
        return 0
    if item['mode'] == 'manual':
        print(f"{item['title']}: {item['status']}\nRead {item['docs']}")
        return 0 if action == 'check' else 2
    error = platform_error()
    if error:
        print(error, file=sys.stderr)
        return 1
    native_args, _ = session_options(extra)
    command = native_command(item, action, native_args)
    account = session_user(extra)
    if action != 'check' and item.get('needs_user') and not account:
        raise ValueError('Run from the Gaming Mode user, or provide OXP3_SESSION_USER')
    if item['id'] == 'tdp' and action in ('install', 'check') and account:
        command += ['--session-user', account.pw_name]
    environment = os.environ.copy()
    if account:
        environment['OXP3_SESSION_USER'] = account.pw_name
    if action != 'check' and item['mode'] == 'system' and os.geteuid() != 0:
        if not shutil.which('sudo'):
            raise ValueError('sudo is required for system fixes')
        command = ['sudo', '--', '/usr/bin/env']
        if account:
            command.append('OXP3_SESSION_USER=' + account.pw_name)
        command += native_command(item, action, native_args)
        if item['id'] == 'tdp' and action == 'install' and account:
            command += ['--session-user', account.pw_name]
    elif item['mode'] == 'user' and os.geteuid() == 0:
        if not account:
            raise ValueError('Run user fixes from a normal logged-in user shell')
        command = ['runuser', '-u', account.pw_name, '--', '/usr/bin/env',
                   'HOME=' + account.pw_dir, 'XDG_RUNTIME_DIR=/run/user/' + str(account.pw_uid),
                   'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/' + str(account.pw_uid) + '/bus'] + command
    print('$ ' + shlex.join(command), flush=True)
    return subprocess.run(command, cwd=ROOT, env=environment, check=False).returncode


def guided_arguments(item, action):
    ident = item['id']
    if action == 'install':
        if ident == 'boot-controller':
            path = input('Built BOOTX64.EFI path (blank cancels): ').strip()
            return [os.path.expanduser(path)] if path else None
        if ident == 'display-edid':
            connector = input('TV connector [DP-1]: ').strip() or 'DP-1'
            print('Capture only while the TV is on and its full modes are detected correctly.')
            path = input('Existing EDID file, or blank to capture this TV: ').strip()
            return ['--connector', connector] + (['--edid', os.path.expanduser(path)] if path else ['--capture'])
        if ident == 'tv-audio':
            card = input('Audio card name (blank auto-selects if unambiguous): ').strip()
            args = ['--card', card] if card else []
            profile = input('HDMI profile name (blank auto-selects if unambiguous): ').strip()
            if profile:
                args += ['--profile', profile]
            if input('Also move current application audio to the TV? [y/N]: ').strip().lower() == 'y':
                args.append('--move-streams')
            return args
    elif action == 'rollback':
        if ident == 'controllers':
            path = input('Controller backup directory printed during installation: ').strip()
            return [os.path.expanduser(path)] if path else None
        if ident == 'boot-controller':
            print('Default: restore stock boot order, keeping the custom EFI file.')
            if input('Remove the staged EFI instead? (restore stock first if promoted) [y/N]: ').strip().lower() == 'y':
                return ['--remove']
    return []


def menu(items):
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print('The menu requires a terminal. Use ./install.sh list or ./install.sh --help.')
        return 2
    ordered = list(items.values())
    while True:
        print('\nOXP3-CACHY - choose fixes\n')
        for number, item in enumerate(ordered, 1):
            print(f" {number:2}. {item['title']} [{item['status']}]")
        answer = input('\nNumbers separated by spaces; c = check all; q = quit: ').strip().lower()
        if answer in ('q', 'quit', 'exit'):
            return 0
        if answer == 'c':
            for item in ordered:
                print('\n' + item['title'])
                execute(item, 'check')
            continue
        try:
            indexes = [int(value) - 1 for value in answer.split()]
            if not indexes or any(index < 0 or index >= len(ordered) for index in indexes):
                raise ValueError
            selected = [ordered[index] for index in dict.fromkeys(indexes)]
        except ValueError:
            print('Choose listed numbers, c or q.')
            continue
        for item in selected:
            print(f"\n{item['title']}: {item['description']}")
        action = input('\n[c]heck, [i]nstall, [r]ollback, [d]ocs, [b]ack: ').strip().lower()
        action = {'c': 'check', 'i': 'install', 'r': 'rollback', 'd': 'docs'}.get(action)
        if not action:
            continue
        for item in selected:
            if action in ('install', 'rollback') and item['mode'] == 'manual':
                print(f"\n{item['id']}: manual only; read {item['docs']}")
                continue
            args = guided_arguments(item, action)
            if args is None:
                print('Cancelled this fix.')
                continue
            try:
                status = execute(item, action, args)
                print(f"{item['id']}: {'completed' if status == 0 else 'needs attention (exit ' + str(status) + ')'}")
            except (ValueError, OSError, KeyError) as exc:
                print(f"{item['id']}: {exc}", file=sys.stderr)
        input('\nPress Enter to return to the menu. ')


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    items = catalog()
    if not args:
        return menu(items) if sys.stdin.isatty() else help_text(items)
    action = args.pop(0)
    if action in ('--help', '-h', 'help'):
        return help_text(items)
    if action == 'menu':
        return menu(items)
    if action == 'list':
        for item in items.values():
            print(f"{item['id']:18} {item['title']} [{item['status']}]")
        return 0
    if action == 'check' and not args:
        return int(any([execute(item, action) != 0 for item in items.values()]))
    if action not in ('check', 'install', 'rollback', 'docs') or not args:
        return help_text(items, 2)
    ident = args.pop(0)
    if ident not in items:
        print(f'Unknown fix: {ident}', file=sys.stderr)
        return 2
    return execute(items[ident], action, args)


def help_text(items, status=0):
    print('Usage: ./install.sh [menu|list|check [FIX]|install FIX [ARGS...]|rollback FIX [ARGS...]|docs FIX]')
    print('Run without arguments in a terminal for the multi-select menu. Nothing installs by default.')
    print('System changes use sudo; session fixes use the original user. No automatic reboot or boot promotion.')
    print('Fix IDs: ' + ', '.join(items))
    return status


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
    except (KeyboardInterrupt, EOFError):
        print('\nCancelled.')
        raise SystemExit(130)
