#!/usr/bin/env python3
"""Build a pinned, private Gamescope WSI layer. Does not activate or install globally."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
PROFILE = '3.16.25-event-queues-20261105'
LIBRARY = 'libVkLayer_FROG_gamescope_wsi_x86_64.so'
MANIFEST = 'VkLayer_FROG_gamescope_wsi.x86_64.json'
SOURCE_PATHS = {
    'layer/VkLayer_FROG_gamescope_wsi.cpp', 'layer/xcb_helpers.hpp',
    'layer/vulkan_operators.hpp', 'src/color_helpers.h', 'src/layer_defines.h',
    'src/messagey.h', 'protocol/gamescope-swapchain.xml', 'LICENSE',
    'vendor/vkroots/vkroots.h',
}
PACKAGES = ['x11', 'x11-xcb', 'xcb', 'xcb-composite', 'wayland-client', 'vulkan']


class BuildError(Exception):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify(data: bytes, expected: str, label: str) -> None:
    if digest(data) != expected:
        raise BuildError(f'SHA-256 mismatch: {label}; no output library was changed.')


def run(command: list[str], *, cwd: Path | None = None, capture: bool = False) -> str:
    print(shlex.join(command), flush=True)
    result = subprocess.run(command, cwd=cwd, check=True, text=True,
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout or ''


def source_input(item: dict, cache: Path, offline: bool) -> bytes:
    path = cache/item['path']
    if path.is_file():
        data = path.read_bytes()
        verify(data, item['sha256'], str(path))
        return data
    if offline:
        raise BuildError(f'Offline source missing: {item["path"]}')
    url = item['url']
    if not url.startswith('https://raw.githubusercontent.com/'):
        raise BuildError('Only pinned public GitHub raw-source URLs are accepted.')
    print(f'Download {item["path"]}', flush=True)
    request = urllib.request.Request(url, headers={'User-Agent':'OXP3-CACHY-private-WSI-builder'})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise BuildError(f'Oversized source: {item["path"]}')
    verify(data, item['sha256'], url)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.download-', delete=False) as tmp:
        temporary = Path(tmp.name)
        tmp.write(data)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return data


def output_is_owned(output: Path) -> None:
    if not output.exists() or not any(output.iterdir()):
        return
    marker = output/'build-info.json'
    try:
        owned = json.loads(marker.read_text()).get('profile') == PROFILE
    except (OSError, ValueError):
        owned = False
    if not owned:
        raise BuildError(f'Refusing to overwrite an unrecognized nonempty directory: {output}')
    known = {LIBRARY, MANIFEST, 'build-info.json'}
    if any(p.name not in known or p.is_symlink() for p in output.iterdir()):
        raise BuildError(f'Refusing an output directory containing unrelated files or symlinks: {output}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
        default=Path.home()/'.local/lib/oxp3-gamescope-wsi'/PROFILE)
    parser.add_argument('--cache', type=Path,
        default=Path(os.environ.get('XDG_CACHE_HOME') or Path.home()/'.cache')/'oxp3-fixes/gta-enhanced-hdr'/PROFILE)
    parser.add_argument('--offline', action='store_true', help='Require all pinned source files in the cache.')
    parser.add_argument('--prepare-only', action='store_true', help='Verify/download and patch sources, without compiling or publishing a layer.')
    args = parser.parse_args()
    metadata = json.loads((ROOT/'WSI-SOURCE.json').read_text())
    if metadata['profile'] != PROFILE or {i['path'] for i in metadata['files']} != SOURCE_PATHS:
        raise BuildError('Unexpected profile or source inventory.')
    patch_info = metadata['patch']
    if patch_info['path'] != 'patches/0001-private-wayland-event-queues.patch':
        raise BuildError('Unexpected patch path.')
    patch_path = ROOT/patch_info['path']
    patch = patch_path.read_bytes()
    verify(patch, patch_info['sha256'], str(patch_path))
    if not shutil.which('patch'):
        raise BuildError('Missing patch utility. Install build prerequisites first; this helper installs no packages.')
    if not args.prepare_only:
        if platform.system() != 'Linux' or platform.machine() != 'x86_64':
            raise BuildError('Compile on Linux x86_64. --prepare-only can verify inputs on other systems.')
        if os.geteuid() == 0:
            raise BuildError('Run this private userspace builder as your normal user, without sudo.')
        for tool in ('pkg-config', 'wayland-scanner'):
            if not shutil.which(tool):
                raise BuildError(f'Missing prerequisite: {tool}')
        run(['pkg-config', '--exists', *PACKAGES])
    cache = args.cache.expanduser().resolve()
    output = args.output.expanduser().absolute()
    if not args.prepare_only:
        if output.is_symlink():
            raise BuildError('Output directory must not be a symlink.')
        output_is_owned(output)
    inputs = {item['path']:source_input(item, cache/'downloads', args.offline) for item in metadata['files']}
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache, prefix='build-') as temporary:
        work = Path(temporary)
        source = work/'source'
        for rel, data in inputs.items():
            path = source/rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        run(['patch', '--batch', '--forward', '-p1', '-i', str(patch_path)], cwd=source)
        verify((source/'layer/VkLayer_FROG_gamescope_wsi.cpp').read_bytes(),
               patch_info['modified_layer_sha256'], 'patched layer')
        if args.prepare_only:
            print('Pinned sources and resulting patch verified; no layer compiled, published or activated.')
            return 0
        compile_flags = shlex.split(run(['pkg-config', '--cflags', *PACKAGES], capture=True))
        link_flags = shlex.split(run(['pkg-config', '--libs', *PACKAGES], capture=True))
        xml = source/'protocol/gamescope-swapchain.xml'
        run(['wayland-scanner', 'client-header', str(xml), str(work/'gamescope-swapchain-client-protocol.h')])
        run(['wayland-scanner', 'private-code', str(xml), str(work/'gamescope-swapchain-protocol.c')])
        flags = ['-O2', '-fPIC', '-D_GNU_SOURCE', '-I'+str(work), *compile_flags]
        cc = shlex.split(os.environ.get('CC') or 'cc')
        cxx = shlex.split(os.environ.get('CXX') or 'g++')
        run([*cc, *flags, '-c', str(work/'gamescope-swapchain-protocol.c'), '-o', str(work/'protocol.o')])
        library = work/LIBRARY
        run([*cxx, '-std=c++20', *flags, '-I'+str(source/'vendor/vkroots'),
             '-I'+str(source/'layer'), '-shared', '-pthread', '-Wl,--no-undefined',
             str(source/'layer/VkLayer_FROG_gamescope_wsi.cpp'), str(work/'protocol.o'),
             *link_flags, '-o', str(library)])
        dependencies = run(['ldd', str(library)], capture=True)
        if 'not found' in dependencies:
            raise BuildError('Built layer has unresolved dependencies; no output was published.')
        manifest = {'file_format_version':'1.0.0', 'layer':{
            'name':'VK_LAYER_FROG_gamescope_wsi_x86_64', 'type':'GLOBAL',
            'api_version':'1.3.221', 'implementation_version':'1',
            'description':f'Private OXP3 Gamescope WSI ({PROFILE})',
            'library_path':str(output/LIBRARY),
            'functions':{'vkNegotiateLoaderLayerInterfaceVersion':'vkNegotiateLoaderLayerInterfaceVersion'},
            'enable_environment':{'ENABLE_GAMESCOPE_WSI':'1'},
            'disable_environment':{'DISABLE_GAMESCOPE_WSI':'1'},
        }}
        (work/MANIFEST).write_text(json.dumps(manifest,indent=2)+'\n')
        info = {'profile':PROFILE, 'gamescope_commit':metadata['gamescope']['commit'],
                'vkroots_commit':metadata['vkroots']['commit'], 'patch_sha256':digest(patch),
                'library_sha256':digest(library.read_bytes()), 'activated':False}
        (work/'build-info.json').write_text(json.dumps(info,indent=2)+'\n')
        output_is_owned(output)
        output.mkdir(parents=True, exist_ok=True)
        # Stage on the destination filesystem, then replace complete files only.
        with tempfile.TemporaryDirectory(dir=output.parent, prefix='.publish-wsi-') as publish_dir:
            publish = Path(publish_dir)
            for name in (LIBRARY, MANIFEST, 'build-info.json'):
                shutil.copy2(work/name, publish/name)
            for name in (LIBRARY, MANIFEST, 'build-info.json'):
                os.replace(publish/name, output/name)
        print(f'Built private layer: {output}\nSHA-256: {info["library_sha256"]}\nNot activated; use the documented per-game launcher profile.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (BuildError, OSError, ValueError, KeyError, subprocess.CalledProcessError, urllib.error.URLError) as error:
        print(f'build-wsi-layer: {error}', file=sys.stderr)
        raise SystemExit(1)
