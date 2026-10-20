"""Permission deployment transactions; fake services and temporary files only."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('onex3_metrics_deploy', Path(__file__).parents[1] / 'deploy.py')
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)
shared = deploy.shared


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(dir=deploy.SOURCE)
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.state = self.root / 'state'
        self.state.mkdir()
        self.rule = self.root / 'rules/local.rules'
        self.rule.parent.mkdir()
        self.rule.write_text('old rule\n')
        self.helper = self.root / 'helper.py'
        self.helper.write_text('old helper\n')
        self.helper.chmod(0o600)
        self.unit = self.root / deploy.UNIT
        self.link = self.root / 'unit.wants' / deploy.UNIT
        self.link.parent.mkdir()
        self.active = 'inactive'
        self.events = []
        self.fail_start = False
        self.stop_result = 'success'
        self.attrs = {}
        actual_fingerprint = shared.fingerprint
        actual_atomic = shared.atomic_file

        def fingerprint(path):
            result = actual_fingerprint(path)
            if result['kind'] != 'missing':
                result.update(self.attrs.get(str(path), {}))
            return result

        def atomic(path, data, mode=0o644, uid=0, gid=0):
            with mock.patch.object(os, 'fchown'):
                actual_atomic(path, data, mode, uid, gid)
            self.attrs[str(path)] = {'uid': uid, 'gid': gid}

        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        for target, name, value in (
            (deploy, 'STATE_ROOT', self.state), (deploy, 'RULE', self.rule),
            (deploy, 'check_prerequisites', mock.Mock()),
            (deploy, 'payload', lambda: {self.helper: b'new helper\n', self.unit: b'unit\n', self.rule: b'new rule\n'}),
            (deploy, 'rules_reload', lambda: self.events.append('rules-settled')),
            (shared, 'safe_system_parent', shared.safe_parent),
            (shared, 'atomic_file', atomic), (shared, 'fingerprint', fingerprint),
            (shared, 'service_state', self.service_state),
            (shared, 'enable_links', lambda *args: {str(self.link): fingerprint(self.link)} if self.link.is_symlink() else {}),
            (shared, 'control', self.control),
        ):
            self.stack.enter_context(mock.patch.object(target, name, value))
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stack.enter_context(contextlib.redirect_stderr(io.StringIO()))

    def service_state(self, *args, **kwargs):
        return {'active': self.active, 'enabled': 'enabled' if self.link.is_symlink() else 'disabled'}

    def control(self, user, *args, **kwargs):
        command = args[0]
        self.events.append(command)
        if command == 'enable':
            self.link.symlink_to(self.unit)
        elif command == 'stop':
            self.active = 'inactive'
        elif command in ('start', 'restart'):
            if self.fail_start:
                self.fail_start = False
                raise RuntimeError('injected start failure')
            self.active = 'active'
        return subprocess.CompletedProcess(args, 0,
            f'ActiveState={self.active}\nResult={self.stop_result}\nExecMainStatus={0 if self.stop_result == "success" else 1}\n', '')

    def record(self):
        return Path(json.loads((self.state / 'active.json').read_text())['state'])

    def test_install_rollback_restores_files_metadata_enable_link_and_service_state(self):
        before = shared.fingerprint(self.helper)
        deploy.install()
        record = self.record()
        self.assertEqual(self.helper.read_text(), 'new helper\n')
        self.assertTrue(self.link.is_symlink())
        self.assertTrue(deploy.rollback(record))
        self.assertEqual(self.helper.read_text(), 'old helper\n')
        self.assertEqual(shared.fingerprint(self.helper), before)
        self.assertEqual(self.rule.read_text(), 'old rule\n')
        self.assertFalse(self.unit.exists())
        self.assertFalse(self.link.is_symlink())
        self.assertEqual(self.active, 'inactive')
        self.assertFalse((self.state / 'active.json').exists())
        self.assertTrue(record.exists())

    def test_start_failure_restores_preexisting_files_and_links(self):
        self.fail_start = True
        with self.assertRaisesRegex(RuntimeError, 'start failure'):
            deploy.install()
        self.assertEqual(self.helper.read_text(), 'old helper\n')
        self.assertEqual(self.rule.read_text(), 'old rule\n')
        self.assertFalse(self.link.is_symlink())
        self.assertFalse((self.state / 'active.json').exists())

    def test_queued_udev_events_are_settled_before_service_stop(self):
        deploy.install()
        record = self.record()
        self.events.clear()
        deploy.rollback(record)
        self.assertLess(self.events.index('rules-settled'), self.events.index('stop'))

    def test_changed_udev_rule_blocks_before_any_rollback_mutation(self):
        deploy.install()
        self.rule.write_text('administrator rule\n')
        self.events.clear()
        with self.assertRaisesRegex(RuntimeError, 'Udev rule changed'):
            deploy.rollback(self.record())
        self.assertEqual(self.events, [])
        self.assertEqual(self.helper.read_text(), 'new helper\n')

    def test_later_helper_change_is_retained_as_conflict(self):
        deploy.install()
        record = self.record()
        self.helper.write_text('administrator helper\n')
        self.assertFalse(deploy.rollback(record))
        self.assertEqual(self.helper.read_text(), 'administrator helper\n')
        self.assertTrue((self.state / 'active.json').exists())

    def test_reinstall_does_not_overwrite_original_baseline(self):
        deploy.install()
        record = self.record()
        before = record.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'already recorded'):
            deploy.install()
        self.assertEqual(record.read_bytes(), before)

    def test_symlinked_destination_parent_is_refused_before_mutation(self):
        deploy.install()
        record = self.record()
        moved = self.root / 'moved-rules'
        self.rule.parent.rename(moved)
        self.rule.parent.symlink_to(moved, target_is_directory=True)
        self.events.clear()
        with self.assertRaisesRegex(RuntimeError, 'symlinked parent'):
            deploy.rollback(record)
        self.assertEqual(self.events, [])
        self.assertEqual((moved / self.rule.name).read_text(), 'new rule\n')

    def test_failed_stop_retains_executable_and_backups(self):
        deploy.install()
        record = self.record()
        self.stop_result = 'exit-code'
        with self.assertRaisesRegex(RuntimeError, 'Permission restoration failed'):
            deploy.rollback(record)
        self.assertEqual(self.helper.read_text(), 'new helper\n')
        self.assertTrue(record.exists())


if __name__ == '__main__':
    unittest.main()
