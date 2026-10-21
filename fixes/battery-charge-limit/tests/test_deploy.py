"""Deployment state/rollback fixtures; no kernel module or service is executed."""

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('charge_deploy', Path(__file__).resolve().parents[1] / 'deploy.py')
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.release = '7.2.9-fixture'
        self.state = self.root / 'state'
        self.state.mkdir()
        self.modules = self.root / 'modules'
        self.module_state = self.root / 'loaded-oxpec'
        self.threshold = self.root / 'threshold'
        self.module = self.root / 'candidate.ko'
        self.module.write_bytes(b'fixture module; never executed')
        self.override = self.modules / self.release / 'updates/oxp3-charge-limit/oxpec.ko'
        self.compressed = self.override.with_suffix('.ko.zst')
        self.conf = self.root / 'system/provider.conf'
        self.conf.parent.mkdir()
        self.conf.write_bytes(b'original local policy')
        self.conf.chmod(0o640)
        self.unrelated = self.root / 'system/onex3-tdp.toml'
        self.unrelated.write_bytes(b'unrelated TDP settings')
        self.files = {self.conf: b'new provider policy', self.override: self.module.read_bytes(),
                      self.compressed: None}
        self.service = {'enabled': 'disabled', 'active': 'inactive'}
        self.commands = []
        self.fail_start = False
        self.fail_copy = False
        self.virtual_owners = {}
        self.real_fingerprint = deploy.shared.fingerprint
        for target, value in ((deploy, 'STATE_ROOT'), (deploy, 'MODULE_ROOT'),
                              (deploy, 'MODULE_STATE'), (deploy, 'THRESHOLD')):
            replacements = {'STATE_ROOT': self.state, 'MODULE_ROOT': self.modules,
                            'MODULE_STATE': self.module_state, 'THRESHOLD': self.threshold}
            mock = patch.object(target, value, replacements[value])
            mock.start()
            self.addCleanup(mock.stop)
        patches = [
            patch.object(deploy, 'check_host', return_value=self.release),
            patch.object(deploy, 'payload', side_effect=lambda *_: self.files),
            patch.object(deploy.shared, 'safe_system_parent'),
            patch.object(deploy.shared, 'atomic_file', side_effect=self.atomic_file),
            patch.object(deploy.shared, 'fingerprint', side_effect=self.fingerprint),
            patch.object(deploy.shared, 'run', side_effect=self.fake_run),
            patch.object(deploy.shared, 'control', side_effect=self.control),
            patch.object(deploy.shared, 'service_state', side_effect=lambda *_a, **_kw: dict(self.service)),
            patch.object(deploy.shared, 'enable_links', return_value={}),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def atomic_file(self, path, data, mode=0o644, uid=0, gid=0):
        if self.fail_copy and path == self.override:
            self.fail_copy = False
            raise OSError('injected module-copy failure')
        path.write_bytes(data)
        path.chmod(mode)
        self.virtual_owners[path] = (uid, gid)

    def fingerprint(self, path):
        value = self.real_fingerprint(path)
        if value['kind'] == 'file' and path in self.virtual_owners:
            value['uid'], value['gid'] = self.virtual_owners[path]
        return value

    def fake_run(self, args, *, check=True):
        self.commands.append(list(args))
        output, code = '', 0
        if args[:3] == ['/usr/bin/modinfo', '-F', 'name']:
            output = 'oxpec\n'
        elif args[:3] == ['/usr/bin/modinfo', '-F', 'vermagic']:
            output = self.release + ' SMP preempt mod_unload\n'
        elif args[:3] == ['/usr/bin/modinfo', '-n', 'oxpec']:
            output, code = (str(self.override) + '\n', 0) if self.override.exists() else ('', 1)
        elif args == ['/usr/bin/modprobe', 'oxpec']:
            self.module_state.mkdir(exist_ok=True)
            # Model the preexisting firmware setting becoming readable after load.
            self.threshold.write_text('80\n')
        if check and code:
            raise RuntimeError('unexpected fixture command failure')
        return subprocess.CompletedProcess(args, code, stdout=output, stderr='')

    def control(self, user, *args, check=True):
        self.commands.append(['systemctl', str(user), *args])
        if args[0] == 'enable':
            self.service['enabled'] = 'enabled'
        elif args[0] == 'start':
            if self.fail_start:
                self.fail_start = False
                raise RuntimeError('injected provider-start failure')
            self.service['active'] = 'active'
        elif args[0] == 'stop':
            self.service['active'] = 'inactive'
        return subprocess.CompletedProcess(args, 0, stdout='', stderr='')

    def record(self):
        import json
        return Path(json.loads((self.state / 'active.json').read_text())['state'])

    def test_install_and_rollback_restore_module_and_local_files(self):
        self.compressed.parent.mkdir(parents=True)
        self.compressed.write_bytes(b'previous compressed override')
        deploy.install('fixture-user', self.module)
        self.assertEqual(self.conf.read_bytes(), b'new provider policy')
        self.assertEqual(self.override.read_bytes(), self.module.read_bytes())
        self.assertFalse(self.compressed.exists())
        self.assertEqual(self.threshold.read_text(), '80\n')
        self.assertTrue(deploy.rollback(self.record()))
        self.assertEqual(self.conf.read_bytes(), b'original local policy')
        self.assertEqual(self.conf.stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.compressed.read_bytes(), b'previous compressed override')
        self.assertFalse(self.override.exists())
        self.assertEqual(self.unrelated.read_bytes(), b'unrelated TDP settings')
        self.assertEqual(self.threshold.read_text(), '80\n')
        self.assertTrue(self.module_state.exists())  # No automatic unload.

    def test_later_admin_change_is_retained_and_record_stays_active(self):
        deploy.install('fixture-user', self.module)
        self.conf.write_bytes(b'later administrator policy')
        self.assertFalse(deploy.rollback(self.record()))
        self.assertEqual(self.conf.read_bytes(), b'later administrator policy')
        self.assertTrue((self.state / 'active.json').exists())
        self.assertEqual(self.threshold.read_text(), '80\n')

    def test_provider_start_failure_restores_disk_baseline(self):
        self.fail_start = True
        with self.assertRaisesRegex(RuntimeError, 'provider-start'):
            deploy.install('fixture-user', self.module)
        self.assertEqual(self.conf.read_bytes(), b'original local policy')
        self.assertFalse(self.override.exists())
        self.assertFalse((self.state / 'active.json').exists())
        self.assertEqual(self.threshold.read_text(), '80\n')

    def test_partial_copy_failure_restores_preceding_file_without_loading(self):
        self.fail_copy = True
        with self.assertRaisesRegex(OSError, 'module-copy'):
            deploy.install('fixture-user', self.module)
        self.assertEqual(self.conf.read_bytes(), b'original local policy')
        self.assertFalse(self.override.exists())
        self.assertFalse(self.module_state.exists())
        self.assertFalse(self.threshold.exists())

    def test_check_never_writes_deployment_state_or_loads(self):
        deploy.install('fixture-user', self.module, check=True)
        self.assertEqual(list(self.state.iterdir()), [])
        self.assertFalse(self.override.exists())
        self.assertFalse(self.module_state.exists())
        self.assertEqual(self.conf.read_bytes(), b'original local policy')

    def test_wrong_kernel_is_refused_before_any_install_write(self):
        real_run = self.fake_run
        def mismatched(args, **kwargs):
            result = real_run(args, **kwargs)
            if args[:3] == ['/usr/bin/modinfo', '-F', 'vermagic']:
                result.stdout = '7.2.9-other-build SMP\n'
            return result
        with patch.object(deploy.shared, 'run', side_effect=mismatched):
            with self.assertRaisesRegex(RuntimeError, 'vermagic mismatch'):
                deploy.install('fixture-user', self.module)
        self.assertEqual(list(self.state.iterdir()), [])
        self.assertFalse(self.override.exists())


if __name__ == '__main__':
    unittest.main()
