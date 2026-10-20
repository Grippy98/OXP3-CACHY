#!/usr/bin/env python3
"""Isolated regression checks; never reads or writes an actual EFI partition."""

from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
HELPER = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / 'controller-state.py'
UUID = '11111111-2222-3333-4444-555555555555'
ROOT = 'timeout: 5\ninterface_branding: Existing theme\ndefault_entry: CachyOS/linux-cachyos-deckify\n'
ENTRIES = '/+CachyOS\n//linux-cachyos-deckify\nprotocol: linux\npath: boot():/old-kernel\ncmdline: root=UUID=fixture rw drm.edid_firmware=DP-1:edid/lg-c5.bin\n'
NEW_ENTRY = '\n//newer-kernel\nprotocol: linux\npath: boot():/new-kernel\ncmdline: root=UUID=fixture rw\n'


def call(*args, success=True):
    result = subprocess.run([sys.executable, str(HELPER), *map(str, args)], capture_output=True, text=True)
    assert (result.returncode == 0) == success, (args, result.returncode, result.stdout, result.stderr)
    return result


def snapshot(path, order='0003,2001,0005,0000', current='0005', extra='', active=True, uuid=UUID):
    marker = '*' if active else ''
    path.write_text(f'BootCurrent: {current}\nBootOrder: {order}\n{extra}'
                    f'Boot0003* Limine HD(6,GPT,{UUID},0x800,0x100000)/File(\\EFI\\limine\\limine_x64.efi)\n'
                    f'Boot0005{marker} Controller HD(6,GPT,{uuid},0x800,0x100000)/File(\\EFI\\limine-oxp3-controller\\BOOTX64.EFI)\n')


def main():
    passed = []
    with tempfile.TemporaryDirectory(prefix='oxp3-persistence-test-') as temporary:
        base = Path(temporary)
        config, manifest, state = base / 'limine.conf', base / 'setting.json', base / 'efi.txt'

        config.write_text(ROOT + ENTRIES)
        call('enable-config', config, manifest)
        assert config.read_text() == 'gamepad: yes\n' + ROOT + ENTRIES
        config.write_text(config.read_text() + NEW_ENTRY)
        call('restore-config', config, manifest)
        assert config.read_text() == ROOT + ENTRIES + NEW_ENTRY
        passed.append('enable and rollback preserve theme, original kernel flags, and newly generated kernel entries')

        config.write_text('gamepad: no\n' + ROOT + ENTRIES)
        call('enable-config', config, manifest)
        assert config.read_text() == 'gamepad: yes\n' + ROOT + ENTRIES
        call('restore-config', config, manifest)
        assert config.read_text() == 'gamepad: no\n' + ROOT + ENTRIES
        call('enable-config', config, manifest)
        config.write_text(config.read_text().replace('gamepad: yes', 'gamepad: no'))
        before = config.read_bytes()
        call('restore-config', config, manifest)
        assert config.read_bytes() == before
        passed.append('rollback restores original global option and preserves a subsequent user change')

        for invalid in [ROOT.replace('timeout: 5\n', '') + ENTRIES + 'timeout: 5\n',
                        ROOT.replace('timeout: 5', 'timeout: 0') + ENTRIES,
                        ROOT + ENTRIES + 'gamepad: no\n']:
            config.write_text(invalid)
            call('enable-config', config, manifest, success=False)
            assert config.read_text() == invalid
        passed.append('missing global countdown, instant autoboot, and entry-local gamepad settings are rejected without mutation')

        snapshot(state)
        result = call('boot-plan', 'promote', state, '0005', '0003', UUID)
        assert result.stdout.splitlines() == ['0003,2001,0005,0000', '0005,0003,2001,0000']
        snapshot(state, order='0005,0003,2001,0000')
        assert call('boot-plan', 'promote', state, '0005', '0003', UUID).stdout.splitlines()[1] == '0005,0003,2001,0000'
        snapshot(state, order='0005,2001,0003,0000,0007')
        assert call('boot-plan', 'rollback', state, '0005', '0003', UUID).stdout.splitlines()[1] == '0003,2001,0000,0007,0005'
        passed.append('promotion deduplicates custom entry and rollback preserves unrelated current firmware entries')

        for options in [dict(active=False), dict(current='0003'), dict(extra='BootNext: 2001\n'),
                        dict(uuid='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'), dict(order='0003,0005,0003')]:
            snapshot(state, **options)
            call('boot-plan', 'promote', state, '0005', '0003', UUID, success=False)
        passed.append('inactive entry, untested BootCurrent, pending BootNext, wrong ESP, and duplicate BootOrder are rejected')

    result = {
        'status': 'passed',
        'scope': 'Isolated actual helper config transformations and BootOrder planning; no device actions or firmware writes.',
        'helper_sha256': hashlib.sha256(HELPER.read_bytes()).hexdigest(),
        'groups': passed,
    }
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
