#!/usr/bin/env python3
"""Package a built plugin into a new private ZIP; no deployment or device writes."""
import argparse
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
FILES = ('main.py', 'plugin.json', 'package.json', 'dist/index.js')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='new absolute ZIP path outside this fix folder')
    output = parser.parse_args().output
    if not output.is_absolute() or output.exists() or output.is_symlink():
        parser.error('Choose a new absolute output filename.')
    if ROOT == output.parent.resolve() or ROOT in output.resolve().parents:
        parser.error('Keep generated archives outside this source folder.')
    for name in FILES:
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            parser.error(f'Missing regular build input: {name}. Run pnpm build first.')
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(ROOT / name, f'OXP3-Charge-Controls/{name}')
    print(output)


if __name__ == '__main__':
    main()
