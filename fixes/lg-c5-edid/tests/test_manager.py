#!/usr/bin/env python3
"""Synthetic EDID validation and file/initramfs transaction regression checks."""
import argparse
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('manager', Path(__file__).parents[1] / 'workaround/manage-edid.py')
manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manager)


def edid():
    data = bytearray(256)
    data[:8] = bytes.fromhex('00ffffffffffff00')
    data[8:10] = bytes.fromhex('1e6d')  # GSM
    data[54:59] = b'\0\0\0\xfc\0'
    data[59:72] = b'LG TV TEST\n  '
    data[126] = 1
    data[127] = -sum(data[:127]) % 256
    data[128] = 0x02
    data[255] = -sum(data[128:255]) % 256
    return bytes(data)


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        self.root = root
        self.state = root / 'state'
        self.state.mkdir()
        for name, value in [('ROOT', root), ('OWNER_UID', os.geteuid()), ('STATE', self.state), ('MANIFEST', self.state / 'installed.json'), ('LIVE', root / 'live')]:
            context = patch.object(manager, name, value)
            context.start()
            self.addCleanup(context.stop)
        context = patch.object(manager, 'check', lambda: None)
        context.start()
        self.addCleanup(context.stop)
        self.input = root / 'my.edid'
        self.input.write_bytes(edid())
        self.args = argparse.Namespace(connector='DP-1', capture=False, edid=self.input)

    def test_valid_complete_lg_tv(self):
        self.assertEqual(manager.validate_edid(edid()), 'LG TV TEST')

    def test_reject_header_checksum_count_and_generic(self):
        for index in [0, 9, 126, 200]:
            data = bytearray(edid())
            data[index] ^= 1
            with self.assertRaises(ValueError):
                manager.validate_edid(bytes(data))
        data = bytearray(edid())
        data[8:10] = b'\x00\x00'
        data[127] = -sum(data[:127]) % 256
        with self.assertRaises(ValueError):
            manager.validate_edid(bytes(data))

    def test_install_and_rollback_restore_previous_files_and_rebuild_twice(self):
        previous = self.root / 'etc/limine-entry-tool.d/20-oxp3-lg-edid.conf'
        previous.parent.mkdir(parents=True)
        previous.write_bytes(b'original\n')
        with patch.object(manager, 'rebuild') as rebuild:
            manager.install(self.args)
            self.assertIn('drm.edid_firmware=DP-1:', previous.read_text())
            manager.rollback()
        self.assertEqual(rebuild.call_count, 2)
        self.assertEqual(previous.read_bytes(), b'original\n')
        self.assertFalse(manager.MANIFEST.exists())
        self.assertFalse((self.root / 'usr/lib/firmware/edid/oxp3-lg-c5-DP-1.bin').exists())

    def test_failed_rebuild_restores_config_and_attempts_recovery_rebuild(self):
        with patch.object(manager, 'rebuild', side_effect=[RuntimeError('failure'), None]) as rebuild:
            with self.assertRaises(RuntimeError):
                manager.install(self.args)
        self.assertEqual(rebuild.call_count, 2)
        self.assertFalse(manager.MANIFEST.exists())
        self.assertFalse((self.root / 'etc/limine-entry-tool.d/20-oxp3-lg-edid.conf').exists())

    def test_edited_file_is_preserved(self):
        with patch.object(manager, 'rebuild'):
            manager.install(self.args)
            target = self.root / 'etc/limine-entry-tool.d/20-oxp3-lg-edid.conf'
            target.write_text('user edit')
            with self.assertRaises(RuntimeError):
                manager.rollback()
        self.assertEqual(target.read_text(), 'user edit')

    def test_symlinked_managed_parent_is_rejected(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.root / 'etc').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            manager.install(self.args)
        self.assertFalse(list(outside.iterdir()))

    def test_writable_managed_parent_is_rejected(self):
        (self.root / 'etc').mkdir(mode=0o777)
        (self.root / 'etc').chmod(0o777)
        with self.assertRaises(RuntimeError):
            manager.install(self.args)

    def test_existing_override_is_rejected_before_mutation(self):
        manager.LIVE.write_text('DP-1:edid/already.bin')
        with self.assertRaises(RuntimeError):
            manager.install(self.args)
        self.assertFalse(manager.MANIFEST.exists())


if __name__ == '__main__':
    unittest.main()
