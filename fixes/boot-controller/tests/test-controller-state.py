#!/usr/bin/env python3
"""Run isolated configuration/firmware-plan checks without accessing firmware."""

from pathlib import Path
import contextlib
import importlib.util
import io
import sys
import tempfile


helper = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('controller-state.py')
if not helper.is_file():
    helper = Path(__file__).resolve().parent.parent / 'controller-state.py'
spec = importlib.util.spec_from_file_location('controller_state', helper)
state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(state)
passed = 0


def check(condition):
    global passed
    assert condition
    passed += 1


def rejected(call):
    global passed
    try:
        call()
    except SystemExit:
        passed += 1
    else:
        raise AssertionError('Expected a refusal')


body = '/CachyOS\n//linux-cachyos-deckify\nprotocol: linux\npath: boot():/vmlinuz\ncmdline: root=UUID=keep-this\n'
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    config = root / 'limine.conf'
    manifest = root / 'settings.json'
    original = 'timeout: 5\ninterface_branding: My theme\ndefault_entry: CachyOS/linux-cachyos-deckify\n' + body
    config.write_text(original)
    state.enable_config(config, manifest)
    check(config.read_text() == 'gamepad: yes\n' + original)
    config.write_text(config.read_text() + '//new-kernel\npath: boot():/new-kernel\n')
    state.restore_config(config, manifest)
    check(config.read_text() == original + '//new-kernel\npath: boot():/new-kernel\n')
    config.write_text('gamepad: no\n' + original)
    state.enable_config(config, manifest)
    state.restore_config(config, manifest)
    check(config.read_text() == 'gamepad: no\n' + original)
    config.write_text('gamepad: no\nGAMEPAD: yes\n' + original)
    state.enable_config(config, manifest)
    check(config.read_text().count('gamepad: yes') == 1)
    state.restore_config(config, manifest)
    check(config.read_text() == 'gamepad: no\nGAMEPAD: yes\n' + original)
    config.write_text(original.replace('timeout: 5', 'timeout: 0'))
    rejected(lambda: state.enable_config(config, manifest))
    config.write_text(original + 'gamepad: no\n')
    rejected(lambda: state.enable_config(config, manifest))
    check(config.read_text() == original + 'gamepad: no\n')
    config.write_text(original)
    state.enable_config(config, manifest)
    changed = config.read_text().replace('gamepad: yes', 'gamepad: no')
    config.write_text(changed)
    with contextlib.redirect_stderr(io.StringIO()):
        state.restore_config(config, manifest)
    check(config.read_text() == changed)

    uuid = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
    snapshot = root / 'efibootmgr.txt'
    text = f'BootCurrent: 0005\nBootOrder: 0003,0001,0002\nBoot0003* Limine HD(6,GPT,{uuid},0,0)/\\EFI\\limine\\limine_x64.efi\nBoot0005* ONEXPLAYER 3 controller test HD(6,GPT,{uuid},0,0)/\\EFI\\limine-oxp3-controller\\BOOTX64.EFI\n'
    snapshot.write_text(text)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        state.boot_plan('promote', snapshot, '0005', '0003', uuid)
    check(output.getvalue().splitlines() == ['0003,0001,0002', '0005,0003,0001,0002'])
    snapshot.write_text(text.replace('BootOrder: 0003,0001,0002', 'BootOrder: 0005,0003,0001,0002,0006'))
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        state.boot_plan('rollback', snapshot, '0005', '0003', uuid)
    check(output.getvalue().splitlines()[1] == '0003,0001,0002,0006,0005')
    for changed in [text.replace('Boot0005*', 'Boot0005'), text.replace('Boot0003*', 'Boot0003'), text.replace('BootCurrent: 0005', 'BootCurrent: 0003'), text + 'BootNext: 0001\n', text.replace('BOOTX64.EFI', 'BOOTX64.EFI.bak'), text.replace(uuid, 'ffffffff-bbbb-cccc-dddd-eeeeeeeeeeee')]:
        snapshot.write_text(changed)
        rejected(lambda: state.boot_plan('promote', snapshot, '0005', '0003', uuid))
    snapshot.write_text(text.replace('/\\EFI\\limine-oxp3-controller\\BOOTX64.EFI', '/File(\\EFI\\limine-oxp3-controller\\BOOTX64.EFI)'))
    with contextlib.redirect_stdout(io.StringIO()):
        state.boot_plan('promote', snapshot, '0005', '0003', uuid)
    passed += 1

    config.write_text(original.replace('timeout: 5\n', '') + 'timeout: 5\n')
    rejected(lambda: state.enable_config(config, manifest))
    config.write_text('timeout: 5\n' + original)
    rejected(lambda: state.enable_config(config, manifest))
    snapshot.write_text(text.replace('Boot0005*', 'Boot0005'))
    with contextlib.redirect_stdout(io.StringIO()):
        state.boot_plan('rollback', snapshot, '0005', '0003', uuid)
    passed += 1

    portable = 'timeout: 9\ndefault_entry: Linux/current\n/Linux\n//current\nprotocol: linux\npath: boot():/vmlinuz\n'
    for timeout in ('9', 'no'):
        original_portable = portable.replace('timeout: 9', 'timeout: ' + timeout)
        config.write_text(original_portable)
        state.enable_config(config, manifest)
        check(config.read_text() == 'gamepad: yes\n' + original_portable)
        state.restore_config(config, manifest)
        check(config.read_text() == original_portable)
    dynamic = text.replace('0003', '00A8')
    snapshot.write_text(dynamic)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        state.find_stock(snapshot, uuid)
    check(output.getvalue().strip() == '00A8')
    for changed in (dynamic.replace('Boot00A8*', 'Boot00A8'),
                    dynamic + f'Boot00B9* duplicate HD(6,GPT,{uuid},0,0)/File(\\EFI\\limine\\limine_x64.efi)\n',
                    dynamic.replace('limine_x64.efi', 'limine_x64.efi.bak')):
        snapshot.write_text(changed)
        rejected(lambda: state.find_stock(snapshot, uuid))

print(f'{passed} isolated config and firmware-plan checks passed; no EFI or device commands ran.')
