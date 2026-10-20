"""Deployment rollback tests on temporary files and a fake service manager."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('onex3_deploy', Path(__file__).parents[1] / 'deploy.py')
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='.deploy-test-', dir=deploy.SOURCE)
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.state_root = self.root / 'state'
        self.state_root.mkdir()
        self.unit_root = self.root / 'units'
        self.unit_root.mkdir()
        self.provider_file = self.unit_root / deploy.PROVIDER
        self.manager_file = self.unit_root / deploy.MANAGER
        self.manager_file.write_text('stock manager\n')
        self.replaced = self.root / 'configuration'
        self.replaced.write_text('stock settings\n')
        self.replaced.chmod(0o600)
        self.new = self.root / 'new/source.py'
        self.link_root = self.root / 'links'
        self.link_root.mkdir()
        self.manager_link = self.link_root / 'custom.target.wants' / deploy.MANAGER
        self.manager_link.parent.mkdir()
        self.manager_link.symlink_to(self.manager_file)
        self.actives = {deploy.PROVIDER: 'inactive', deploy.MANAGER: 'active'}
        self.attrs = {}
        self.fail_restart = False
        self.stop_result = 'success'
        original_fingerprint = deploy.fingerprint
        original_atomic = deploy.atomic_file

        def fingerprint(path):
            result = original_fingerprint(path)
            result.update(self.attrs.get(str(path), {}))
            return result

        def atomic(path, data, mode=0o644, uid=0, gid=0):
            with mock.patch.object(deploy.os, 'fchown', return_value=None):
                original_atomic(path, data, mode, uid, gid)
            self.attrs[str(path)] = {'uid': uid, 'gid': gid}

        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(mock.patch.object(deploy, 'STATE_ROOT', self.state_root))
        self.patches.enter_context(mock.patch.object(deploy, 'OLD_ACTIVATION', self.root / 'old-activation'))
        self.patches.enter_context(mock.patch.object(deploy, 'validate_host'))
        # These service/filesystem fixtures intentionally live in a non-root
        # Mac workspace. Root-parent metadata is tested separately below.
        self.patches.enter_context(mock.patch.object(deploy, 'safe_system_parent', side_effect=deploy.safe_parent))
        self.patches.enter_context(mock.patch.object(deploy, 'payload', return_value={
            self.provider_file: b'local provider\n', self.replaced: b'local settings\n', self.new: b'local source\n'}))
        self.patches.enter_context(mock.patch.object(deploy, 'fingerprint', fingerprint))
        self.patches.enter_context(mock.patch.object(deploy, 'atomic_file', atomic))
        self.patches.enter_context(mock.patch.object(deploy, 'service_state', self.service_state))
        self.patches.enter_context(mock.patch.object(deploy, 'enable_links', self.enable_links))
        self.patches.enter_context(mock.patch.object(deploy, 'control', self.control))
        self.patches.enter_context(mock.patch.object(deploy.os, 'lchown', return_value=None))
        self.patches.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.patches.enter_context(contextlib.redirect_stderr(io.StringIO()))

    def enable_links(self, user, unit):
        return {str(path): deploy.fingerprint(path) for path in self.link_root.rglob(unit) if path.is_symlink()}

    def service_state(self, user, unit, **kwargs):
        file = self.provider_file if unit == deploy.PROVIDER else self.manager_file
        enabled = 'not-found' if not file.exists() else ('enabled' if self.enable_links(user, unit) else 'disabled')
        return {'enabled': enabled, 'active': self.actives[unit]}

    def control(self, user, *args, **kwargs):
        command = args[0]
        unit = args[-1]
        if command == 'enable':
            link = self.link_root / 'normal.target.wants' / unit
            link.parent.mkdir(exist_ok=True)
            link.symlink_to(self.provider_file if unit == deploy.PROVIDER else self.manager_file)
        elif command == 'stop':
            self.actives[unit] = 'inactive'
        elif command in {'start', 'restart'}:
            if self.fail_restart and unit == deploy.MANAGER:
                self.fail_restart = False
                raise RuntimeError('injected manager restart error')
            self.actives[unit] = 'active'
            if unit == deploy.MANAGER and self.provider_file.exists():
                self.actives[deploy.PROVIDER] = 'active'  # ExecStartPost activation.
        elif command == 'is-active':
            return subprocess.CompletedProcess(args, 0, self.actives[unit] + '\n', '')
        elif command == 'show':
            return subprocess.CompletedProcess(args, 0,
                f'ActiveState={self.actives[deploy.PROVIDER]}\nResult={self.stop_result}\nExecMainStatus={0 if self.stop_result == "success" else 1}\n', '')
        return subprocess.CompletedProcess(args, 0, '', '')

    def record(self):
        return Path(json.loads((self.state_root / 'active.json').read_text())['state'])

    def test_install_and_rollback_restore_file_metadata_exact_enable_links_and_running_states(self):
        original = deploy.fingerprint(self.replaced)
        deploy.install('test-user')
        record = self.record()
        self.assertEqual(self.replaced.read_text(), 'local settings\n')
        self.assertEqual(deploy.fingerprint(self.new)['uid'], 0)
        self.assertTrue(deploy.rollback(record))
        self.assertEqual(self.replaced.read_text(), 'stock settings\n')
        self.assertEqual(deploy.fingerprint(self.replaced), original)
        self.assertFalse(self.new.exists())
        self.assertFalse(self.provider_file.exists())
        self.assertTrue(self.manager_link.is_symlink())
        self.assertEqual(set(self.enable_links('test-user', deploy.MANAGER)), {str(self.manager_link)})
        self.assertEqual(self.actives, {deploy.PROVIDER: 'inactive', deploy.MANAGER: 'active'})
        self.assertFalse((self.state_root / 'active.json').exists())
        self.assertTrue(record.exists())  # Retain all original backups.

    def test_rollback_preserves_later_file_and_new_enable_link_changes(self):
        deploy.install('test-user')
        self.replaced.write_text('administrator settings\n')
        new_link = self.link_root / 'later.target.wants' / deploy.MANAGER
        new_link.parent.mkdir()
        new_link.symlink_to(self.manager_file)
        record = self.record()
        self.assertFalse(deploy.rollback(record))
        self.assertEqual(self.replaced.read_text(), 'administrator settings\n')
        self.assertTrue(new_link.is_symlink())
        state = json.loads(record.read_text())
        self.assertIn(str(self.replaced), state['rollback_conflicts'])
        self.assertIn(str(new_link), state['rollback_conflicts'])
        self.assertTrue((self.state_root / 'active.json').exists())

    def test_install_failure_restores_preexisting_files_and_enable_links(self):
        self.fail_restart = True
        with self.assertRaisesRegex(RuntimeError, 'injected manager restart'):
            deploy.install('test-user')
        self.assertEqual(self.replaced.read_text(), 'stock settings\n')
        self.assertFalse(self.provider_file.exists())
        self.assertFalse(self.new.exists())
        self.assertEqual(set(self.enable_links('test-user', deploy.MANAGER)), {str(self.manager_link)})
        self.assertFalse((self.state_root / 'active.json').exists())

    def test_reinstall_never_overwrites_original_snapshot(self):
        deploy.install('test-user')
        record = self.record()
        contents = record.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            deploy.install('test-user')
        self.assertEqual(record.read_bytes(), contents)

    def test_failed_provider_cleanup_refuses_file_and_enable_link_removal(self):
        deploy.install('test-user')
        record = self.record()
        self.stop_result = 'exit-code'
        with self.assertRaisesRegex(RuntimeError, 'cleanup was not successful'):
            deploy.rollback(record)
        self.assertEqual(self.replaced.read_text(), 'local settings\n')
        self.assertTrue(self.new.exists())
        self.assertTrue(self.provider_file.exists())
        self.assertTrue((self.state_root / 'active.json').exists())
        self.assertTrue(self.enable_links(None, deploy.PROVIDER))

    def test_later_symlinked_parent_is_refused_before_file_mutation(self):
        deploy.install('test-user')
        record = self.record()
        parent = self.new.parent
        moved = self.root / 'moved'
        parent.rename(moved)
        parent.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, 'symlinked parent'):
            deploy.rollback(record)
        self.assertEqual((moved / self.new.name).read_text(), 'local source\n')


class PayloadTests(unittest.TestCase):
    def test_exact_payload_and_current_policy_are_configuration_only(self):
        files = deploy.payload('test-user')
        self.assertEqual(len(files), 8)
        config = json.loads(files[Path('/etc/onex3-tdp.json')])
        self.assertEqual(config, {'min_w': 8, 'max_w': 40, 'session_user': 'test-user'})
        policy = files[Path('/etc/dbus-1/system.d/org.onex3.SteamOSManager.PowerControl.conf')]
        self.assertIn(b'<policy user="test-user">', policy)
        self.assertNotIn(b'<policy user="ONEX3_SESSION_USER">', policy)


class SystemParentTests(unittest.TestCase):
    @contextlib.contextmanager
    def parents(self, unsafe=None, uid=0, mode=0o755):
        def attrs(path, **kwargs):
            return SimpleNamespace(st_uid=uid if path == unsafe else 0,
                                   st_mode=stat.S_IFDIR | (mode if path == unsafe else 0o755))
        with mock.patch.object(Path, 'is_symlink', return_value=False), \
                mock.patch.object(Path, 'exists', return_value=True), \
                mock.patch.object(Path, 'stat', attrs):
            yield

    def test_existing_foreign_owned_system_parent_is_rejected_before_file_write(self):
        path = Path('/etc/onex3/source.py')
        with self.parents(path.parent, uid=1000), mock.patch.object(deploy.tempfile, 'mkstemp') as create:
            with self.assertRaisesRegex(RuntimeError, 'root-owned directory'):
                deploy.atomic_file(path, b'payload')
            create.assert_not_called()

    def test_existing_group_or_world_writable_system_ancestor_is_rejected_before_write(self):
        for mode in (0o775, 0o777, 0o757):
            with self.subTest(mode=oct(mode)), self.parents(Path('/usr'), mode=mode), \
                    mock.patch.object(deploy.tempfile, 'mkstemp') as create:
                with self.assertRaisesRegex(RuntimeError, 'group/world writes'):
                    deploy.atomic_file(Path('/usr/local/lib/onex3/source.py'), b'payload')
                create.assert_not_called()

    def test_existing_unsafe_system_state_ancestor_is_rejected_without_repair(self):
        with self.parents(Path('/var/lib'), uid=1000), \
                mock.patch.object(deploy.os, 'chown') as owner, \
                mock.patch.object(deploy.os, 'chmod') as mode:
            with self.assertRaisesRegex(RuntimeError, 'unsafe system parent'):
                deploy.safe_system_parent(Path('/var/lib/onex3-fixes/tdp-install/lock'))
            owner.assert_not_called()
            mode.assert_not_called()

    def test_root_owned_safe_system_parents_are_accepted(self):
        with self.parents():
            deploy.safe_system_parent(Path('/etc/onex3/source.py'))
            deploy.safe_system_parent(Path('/usr/local/lib/onex3/source.py'))
            deploy.safe_system_parent(Path('/var/lib/onex3-fixes/tdp-install/lock'))

    def test_user_enable_link_parent_keeps_distinct_symlink_only_contract(self):
        path = Path('/home/test-user/.config/systemd/user/graphical-session.target.wants/steamos-manager.service')
        with self.parents(path.parent, uid=1000):
            deploy.safe_parent(path)
            with self.assertRaisesRegex(RuntimeError, 'root-owned directory'):
                deploy.safe_system_parent(path)


if __name__ == '__main__':
    unittest.main()
