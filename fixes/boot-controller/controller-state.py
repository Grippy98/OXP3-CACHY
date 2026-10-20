#!/usr/bin/env python3
"""Configuration and firmware helpers for OXP3 Limine deployment."""

from pathlib import Path
import json
import os
import re
import sys
import tempfile


CUSTOM_PATH = r'\EFI\limine-oxp3-controller\BOOTX64.EFI'
STOCK_PATH = r'\EFI\limine\limine_x64.efi'
GAMEPAD = re.compile(r'^[ \t]*gamepad[ \t]*:[ \t]*(.*?)[ \t]*$', re.I)


def atomic_write(path, text):
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def find_stock(snapshot, partuuid):
    matches = []
    pattern = re.escape(STOCK_PATH.casefold()) + r'(?=$|[)\s])'
    for line in Path(snapshot).read_text().splitlines():
        match = re.match(r'^Boot([0-9a-f]{4})\*\s+', line, re.I)
        normalized = line.replace('/', '\\').casefold()
        if match and partuuid.casefold() in normalized and re.search(pattern, normalized):
            matches.append(match[1].upper())
    if len(matches) != 1:
        raise SystemExit('Expected one active stock Limine firmware entry on this ESP; inspect efibootmgr -v.')
    print(matches[0])


def boot_plan(mode, snapshot, custom, stock, partuuid):
    text = Path(snapshot).read_text()
    entries = {}
    for line in text.splitlines():
        match = re.match(r'^Boot([0-9a-f]{4})(\*)?\s+(.*)', line, re.I)
        if match:
            entries[match[1].upper()] = (match[3], bool(match[2]))
    for entry, loader in ((custom, CUSTOM_PATH), (stock, STOCK_PATH)):
        description, active = entries.get(entry, ('', False))
        line = description.replace('/', '\\').casefold()
        pattern = re.escape(loader.casefold()) + r'(?=$|[)\s])'
        if not re.search(pattern, line) or partuuid.casefold() not in line:
            raise SystemExit(f'Boot{entry} does not reference its expected loader on this ESP.')
        if not active and (mode == 'promote' or entry == stock):
            raise SystemExit(f'Boot{entry} is inactive; leaving its state unchanged.')
    order_match = re.search(r'(?m)^BootOrder:\s*([0-9a-f,]+)\s*$', text, re.I)
    if not order_match:
        raise SystemExit('Cannot read the current BootOrder.')
    order = order_match[1].upper().split(',')
    if len(order) != len(set(order)) or stock not in order:
        raise SystemExit('The stock entry must be present in an unambiguous BootOrder.')
    if mode == 'promote':
        current = re.search(r'(?m)^BootCurrent:\s*([0-9a-f]{4})\s*$', text, re.I)
        if not current or current[1].upper() != custom:
            raise SystemExit('Boot the experimental loader and verify its controller before promotion.')
        if re.search(r'(?m)^BootNext:', text):
            raise SystemExit('A pending BootNext exists; leave it intact and resolve it before promotion.')
        desired = [custom] + [entry for entry in order if entry != custom]
    else:
        desired = [stock] + [entry for entry in order if entry not in (stock, custom)] + [custom]
    print(','.join(order))
    print(','.join(desired))


def split_config(text):
    lines = text.splitlines(keepends=True)
    first_entry = next((index for index, line in enumerate(lines) if line.lstrip().startswith('/')), len(lines))
    return lines[:first_entry], lines[first_entry:]


def enable_config(config, manifest):
    text = Path(config).read_text()
    lines, entries = split_config(text)
    if any(GAMEPAD.match(line.rstrip('\r\n')) for line in entries):
        raise SystemExit('A gamepad setting occurs after a menu entry; leaving it intact for review.')
    timeouts = [re.match(r'^[ \t]*timeout[ \t]*:[ \t]*(.*?)[ \t]*$', line.rstrip('\r\n'), re.I)
                for line in lines if re.match(r'^[ \t]*timeout[ \t]*:', line, re.I)]
    if len(timeouts) != 1 or not (timeouts[0][1].casefold() == 'no' or
                                  (timeouts[0][1].isdigit() and int(timeouts[0][1]) > 0)):
        raise SystemExit('A single global nonzero timeout (or no) is required; no timeout change is made.')
    if not entries:
        raise SystemExit('No menu entries were found.')
    original = [line for line in lines if GAMEPAD.match(line.rstrip('\r\n'))]
    Path(manifest).write_text(json.dumps({'original_gamepad_lines': original}, indent=2) + '\n')
    kept = [line for line in lines if not GAMEPAD.match(line.rstrip('\r\n'))]
    atomic_write(config, 'gamepad: yes\n' + ''.join(kept + entries))


def restore_config(config, manifest):
    original = json.loads(Path(manifest).read_text())['original_gamepad_lines']
    lines, entries = split_config(Path(config).read_text())
    active = [line for line in lines if GAMEPAD.match(line.rstrip('\r\n'))]
    if len(active) != 1 or GAMEPAD.match(active[0].rstrip('\r\n'))[1].casefold() != 'yes':
        print('The gamepad setting was subsequently changed; leaving that setting intact.', file=sys.stderr)
        return
    kept = [line for line in lines if not GAMEPAD.match(line.rstrip('\r\n'))]
    atomic_write(config, ''.join(line if line.endswith(('\n', '\r')) else line + '\n' for line in original) + ''.join(kept + entries))


if __name__ == '__main__':
    command, *args = sys.argv[1:]
    if command == 'find-stock':
        find_stock(*args)
    elif command == 'boot-plan':
        boot_plan(*args)
    elif command == 'enable-config':
        enable_config(*args)
    elif command == 'restore-config':
        restore_config(*args)
    else:
        raise SystemExit('Unknown helper operation.')
