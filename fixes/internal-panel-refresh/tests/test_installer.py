#!/usr/bin/env python3
"""Verify profile replacement/rollback and preservation of user edits."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('manager', Path(__file__).parents[1] / 'profile/manage-profile.py')
manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manager)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.target = self.root / 'config/gamescope/scripts/onexplayer3-sdc-refresh.lua'
        context = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root / 'config'), 'XDG_STATE_HOME': str(self.root / 'state')})
        context.start()
        self.addCleanup(context.stop)
        context = patch.object(manager.os, 'geteuid', return_value=1000)
        context.start()
        self.addCleanup(context.stop)

    def action(self, action):
        with patch.object(manager.sys, 'argv', ['manage-profile.py', action]):
            manager.main()

    def test_install_idempotence_and_remove(self):
        self.action('install')
        self.assertTrue(self.target.exists())
        self.action('install')
        self.action('rollback')
        self.assertFalse(self.target.exists())

    def test_restore_previous_user_profile(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_text('previous profile')
        self.action('install')
        self.action('rollback')
        self.assertEqual(self.target.read_text(), 'previous profile')

    def test_failure_before_target_replace_can_restore_previous_content_and_mode(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_text('original private profile')
        self.target.chmod(0o600)
        original_atomic = manager.atomic
        def fail_target(path, data, mode=0o644):
            if path == self.target:
                raise OSError('simulated target replacement failure')
            return original_atomic(path, data, mode)
        with patch.object(manager, 'atomic', side_effect=fail_target):
            with self.assertRaises(OSError):
                self.action('install')
        self.action('rollback')
        self.assertEqual(self.target.read_text(), 'original private profile')
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)

    def test_preserve_postinstall_edit(self):
        self.action('install')
        self.target.write_text('user edit')
        with self.assertRaises(RuntimeError):
            self.action('rollback')
        self.assertEqual(self.target.read_text(), 'user edit')


if __name__ == '__main__':
    unittest.main()
