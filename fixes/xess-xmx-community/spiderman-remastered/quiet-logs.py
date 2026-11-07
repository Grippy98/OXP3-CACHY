#!/usr/bin/env python3
"""Quiet OptiScaler logs before Spider-Man starts; preserve other INI contents."""
from pathlib import Path
import os
import re
import stat
import sys
import tempfile


def quiet(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError('Expected a regular OptiScaler.ini; restore the per-game setup first.')
    for comm in Path('/proc').glob('[0-9]*/comm'):
        try:
            name = comm.read_text().strip().casefold()
        except OSError:
            continue
        if name == 'spider-man.exe':
            raise ValueError('Spider-Man is already running; close it before starting another copy.')
    with path.open(encoding='utf-8-sig', newline='') as stream:
        text = stream.read()
    values = {'logtofile': 'false', 'logtoconsole': 'false', 'loglevel': '3'}
    seen = set()
    active = False
    lines = []
    for line in text.splitlines(keepends=True):
        section = re.match(r'^\s*\[([^]]+)\]\s*(?:[;#].*)?$', line.rstrip('\r\n'))
        if section:
            active = section.group(1).strip().casefold() == 'log'
        match = re.match(r'^(\s*([^=;#]+?)\s*=\s*)([^;#\r\n]*)(.*)$', line.rstrip('\r\n')) if active else None
        if match and match.group(2).strip().casefold() in values:
            key = match.group(2).strip().casefold()
            ending = line[len(line.rstrip('\r\n')):]
            line = match.group(1) + values[key] + match.group(4) + ending
            seen.add(key)
        lines.append(line)
    if seen != set(values):
        raise ValueError('Expected LogToFile, LogToConsole and LogLevel under [Log]. Review this INI version.')
    output = ''.join(lines)
    if output == text:
        return
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='', dir=path.parent,
                                         prefix='.oxp3-spider-log-', delete=False) as stream:
            name = Path(stream.name)
            stream.write(output)
        name.chmod(stat.S_IMODE(path.stat().st_mode))
        os.replace(name, path)
    finally:
        if name is not None:
            name.unlink(missing_ok=True)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: quiet-logs.py /path/to/OptiScaler.ini')
    try:
        quiet(Path(sys.argv[1]))
    except (OSError, ValueError) as error:
        raise SystemExit(f'spiderman-xefg: {error}')
