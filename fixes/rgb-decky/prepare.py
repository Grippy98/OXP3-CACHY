#!/usr/bin/env python3
"""Prepare a pinned HueSync ZIP with native-only OXP3 control and updates disabled."""

import argparse
import ast
import hashlib
import io
from pathlib import Path, PurePosixPath
import stat
import urllib.request
import zipfile

URL = 'https://github.com/HHHHanasak1/HueSync/releases/download/20261014/huesync-oxp3.zip'
SHA256 = '6164fa7bea9e605f9689b6977a13b5b5904b49780bc269b821054e98bd7481d5'
REPOSITORY = Path(__file__).resolve().parents[2]


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Pinned source does not match the expected integration point')
    return text.replace(before, after, 1)


def guarded_files(files):
    name = 'HueSync/py_modules/devices/onexplayer.py'
    text = files[name].decode().replace('\r\n', '\n')
    text = replace_once(text,
        '        if self._config and self._config.x2 and oxp3_native_leds.available():\n',
        '        if self._config and self._config.x2:\n'
        '            if not oxp3_native_leds.available():\n'
        '                raise RuntimeError("OXP3 native LED interfaces are unavailable; raw HID fallback is disabled")\n')
    ast.parse(text)
    files[name] = text.encode()
    name = 'HueSync/main.py'
    text = files[name].decode().replace('\r\n', '\n')
    text = replace_once(text,
        '    async def update_latest(self):\n'
        '        logger.info("Updating latest")\n'
        '        try:\n'
        '            return update.update_latest()\n'
        '        except Exception as e:\n'
        '            logger.error(e, exc_info=True)\n'
        '            return False\n',
        '    async def update_latest(self):\n'
        '        logger.warning("OXP3-CACHY: install a reviewed OXP3 release to update HueSync")\n'
        '        return False\n')
    text = replace_once(text,
        '    async def get_latest_version(self):\n'
        '        try:\n'
        '            return update.get_latest_version()\n'
        '        except Exception as e:\n'
        '            logger.error(e, exc_info=True)\n'
        '            return ""\n',
        '    async def get_latest_version(self):\n'
        '        return await self.get_version()\n')
    ast.parse(text)
    files[name] = text.encode()
    files['HueSync/OXP3-CACHY.txt'] = (
        'Based on HHHHanasak1/HueSync release 20261014, commit '
        'e05aa394f8e3a339b0f6e0c54e0ed23b955e7e84.\n'
        'OXP3-CACHY integration: require native OXP3 LED interfaces; disable the\n'
        'upstream replacement updater and its update notification. Original LICENSE retained.\n'
        'Rebuild/update using fixes/rgb-decky/prepare.py in Grippy98/OXP3-CACHY.\n').encode()
    return files


def prepare(data, output):
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError('Release SHA256 mismatch; no output written')
    files = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 32 * 1024 * 1024:
            raise ValueError('Unexpected archive size')
        for item in archive.infolist():
            path = PurePosixPath(item.filename)
            if path.is_absolute() or '..' in path.parts or path.parts[0] != 'HueSync':
                raise ValueError('Unexpected archive member')
            if stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Archive symlinks are unsupported')
            if not item.is_dir():
                if item.filename in files:
                    raise ValueError('Duplicate archive member')
                files[item.filename] = archive.read(item)
    files = guarded_files(files)
    for required in ('HueSync/LICENSE', 'HueSync/plugin.json', 'HueSync/dist/index.js'):
        if required not in files:
            raise ValueError(f'Missing release input: {required}')
    with output.open('xb') as destination:
        with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='new absolute ZIP path outside this repository')
    parser.add_argument('--archive', type=Path, help='optional existing release ZIP, verified against the same SHA256')
    args = parser.parse_args()
    output = args.output
    if not output.is_absolute() or output.exists() or output.is_symlink():
        parser.error('Choose a new absolute ZIP filename')
    if REPOSITORY == output.resolve() or REPOSITORY in output.resolve().parents:
        parser.error('Keep generated archives outside the source repository')
    if args.archive:
        data = args.archive.read_bytes()
    else:
        with urllib.request.urlopen(URL, timeout=30) as response:
            data = response.read(2 * 1024 * 1024)
    prepare(data, output)
    print(f'Prepared {output}; source SHA256 verified, native-only OXP3 control, replacement updater disabled')


if __name__ == '__main__':
    main()
