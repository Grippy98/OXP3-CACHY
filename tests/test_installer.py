"""Dispatcher regressions. Subprocesses, accounts and platform reads are mocked."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('collection_installer', ROOT / 'scripts/installer.py')
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)
USER = SimpleNamespace(pw_name='player', pw_uid=1001, pw_dir='/home/player')


class Terminal(io.StringIO):
    def isatty(self):
        return True


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.items = installer.catalog()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(redirect_stdout(io.StringIO()))
        self.stack.enter_context(redirect_stderr(io.StringIO()))
        self.stack.enter_context(patch.dict(os.environ, {}, clear=True))

    def runtime(self, uid=1001):
        self.stack.enter_context(patch.object(installer, 'platform_error', return_value=None))
        self.stack.enter_context(patch.object(installer.os, 'geteuid', return_value=uid))
        self.stack.enter_context(patch.object(installer.os, 'getuid', return_value=uid))
        self.stack.enter_context(patch.object(installer.pwd, 'getpwuid', return_value=USER))
        self.stack.enter_context(patch.object(installer.pwd, 'getpwnam', return_value=USER))
        self.stack.enter_context(patch.object(installer.shutil, 'which', return_value='/mock/tool'))
        return self.stack.enter_context(patch.object(installer.subprocess, 'run', return_value=SimpleNamespace(returncode=17)))

    def test_arguments_are_forwarded_as_individual_values_without_a_shell(self):
        run = self.runtime()
        extra = ['/tmp/EFI image; $(touch sentinel).efi', 'a' * 64]
        self.assertEqual(installer.execute(self.items['boot-controller'], 'install', extra), 17)
        args, kwargs = run.call_args
        self.assertEqual(args[0][:4], ['sudo', '--', '/usr/bin/env', 'OXP3_SESSION_USER=player'])
        self.assertEqual(args[0][-2:], extra)
        self.assertEqual(kwargs['cwd'], ROOT)
        self.assertNotIn('shell', kwargs)
        self.assertFalse(kwargs['check'])
        self.assertEqual(extra, ['/tmp/EFI image; $(touch sentinel).efi', 'a' * 64])

    def test_checks_never_escalate(self):
        run = self.runtime()
        installer.execute(self.items['controllers'], 'check')
        self.assertEqual(run.call_args.args[0], ['bash', str(ROOT / 'fixes/oxp3-controller/install.sh'), '--check'])

    def test_root_runs_session_fixes_as_the_original_user(self):
        run = self.runtime(uid=0)
        with patch.dict(os.environ, {'SUDO_USER': 'player'}):
            installer.execute(self.items['tv-audio'], 'install', ['--move-streams'])
        command = run.call_args.args[0]
        self.assertEqual(command[:5], ['runuser', '-u', 'player', '--', '/usr/bin/env'])
        self.assertIn('HOME=/home/player', command)
        self.assertIn('XDG_RUNTIME_DIR=/run/user/1001', command)
        self.assertIn('DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus', command)
        self.assertEqual(command[-1], '--move-streams')
        self.assertEqual(run.call_args.kwargs['env']['OXP3_SESSION_USER'], 'player')

    def test_root_without_a_session_user_refuses_session_install(self):
        run = self.runtime(uid=0)
        with self.assertRaises(ValueError):
            installer.execute(self.items['tv-audio'], 'install')
        run.assert_not_called()

    def test_both_explicit_session_user_forms_are_consumed_by_dispatcher(self):
        run = self.runtime(uid=0)
        for option in (['--session-user', 'player'], ['--session-user=player']):
            with self.subTest(option=option):
                installer.execute(self.items['tv-audio'], 'install', option + ['--move-streams'])
                command = run.call_args.args[0]
                self.assertEqual(command[:3], ['runuser', '-u', 'player'])
                self.assertEqual(command[-3:], [str(ROOT / 'fixes/tv-audio-profile/audio-profile.py'), 'install', '--move-streams'])
                self.assertFalse(any(arg.startswith('--session-user') for arg in command))

    def test_incomplete_session_user_option_refuses_before_subprocess(self):
        run = self.runtime()
        for option in (['--session-user'], ['--session-user='], ['--session-user', '--move-streams']):
            with self.subTest(option=option), self.assertRaises(ValueError):
                installer.execute(self.items['tv-audio'], 'install', option)
        run.assert_not_called()

    def test_tdp_receives_exactly_one_resolved_session_user(self):
        run = self.runtime()
        for option in ([], ['--session-user', 'player'], ['--session-user=player']):
            with self.subTest(option=option):
                installer.execute(self.items['tdp'], 'install', option)
                command = run.call_args.args[0]
                self.assertEqual(command.count('--session-user'), 1)
                index = command.index('--session-user')
                self.assertEqual(command[index + 1], 'player')
                self.assertNotIn('--session-user=player', command)

    def test_boot_install_stages_and_rollback_promotion_is_separate(self):
        item = self.items['boot-controller']
        install = installer.native_command(item, 'install', ['/tmp/image.efi'])
        self.assertEqual(install, ['bash', str(ROOT / 'fixes/boot-controller/install.sh'), '/tmp/image.efi'])
        self.assertEqual(installer.native_command(item, 'rollback', []),
                         ['bash', str(ROOT / 'fixes/boot-controller/rollback-default.sh')])
        self.assertEqual(installer.native_command(item, 'rollback', ['--remove']),
                         ['bash', str(ROOT / 'fixes/boot-controller/rollback-experimental.sh')])
        self.assertNotIn('promote-default.sh', ' '.join(install))
        self.assertNotIn('reboot', ' '.join(install))

    def test_docs_and_manual_checks_do_not_require_a_supported_host(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'guide.md').write_text('Offline instructions')
            item = dict(self.items['mangohud'], docs='guide.md')
            with patch.object(installer, 'ROOT', root), patch.object(installer, 'platform_error', side_effect=AssertionError('hardware read')):
                self.assertEqual(installer.execute(item, 'docs'), 0)
                self.assertEqual(installer.execute(item, 'check'), 0)
                self.assertEqual(installer.execute(item, 'install'), 2)

    def test_unsupported_platform_is_refused_before_subprocess(self):
        with patch.object(installer.sys, 'platform', 'darwin'), patch.object(installer.subprocess, 'run') as run:
            self.assertEqual(installer.execute(self.items['controllers'], 'install'), 1)
            run.assert_not_called()

    def test_platform_identification_rejects_other_cpu_or_distribution(self):
        readings = {'/sys/class/dmi/id/product_name': 'ONEXPLAYER 3', '/proc/cpuinfo': 'vendor_id: GenuineIntel', '/etc/os-release': 'ID=cachyos'}
        with patch.object(installer.sys, 'platform', 'linux'), patch.object(installer.Path, 'read_text', autospec=True, side_effect=lambda path: readings[str(path)]), patch.object(installer.shutil, 'which', return_value='/usr/bin/pacman'):
            self.assertIsNone(installer.platform_error())
            readings['/proc/cpuinfo'] = 'vendor_id: AuthenticAMD'
            self.assertIn('Intel', installer.platform_error())
            readings['/proc/cpuinfo'] = 'vendor_id: GenuineIntel'
            readings['/etc/os-release'] = 'ID=debian'
            self.assertIn('CachyOS/Arch', installer.platform_error())

    def test_menu_deduplicates_multiple_picks_and_skips_manual_install(self):
        items = {key: self.items[key] for key in ('controllers', 'boot-controller', 'mangohud')}
        with patch.object(installer.sys, 'stdin', Terminal()), patch.object(installer.sys, 'stdout', Terminal()), patch('builtins.input', side_effect=['1 3 1', 'i', '', 'q']), patch.object(installer, 'guided_arguments', return_value=[]) as guided, patch.object(installer, 'execute', return_value=0) as execute:
            self.assertEqual(installer.menu(items), 0)
        execute.assert_called_once_with(items['controllers'], 'install', [])
        guided.assert_called_once_with(items['controllers'], 'install')

    def test_menu_opens_docs_for_multiple_picks_including_manual(self):
        items = {key: self.items[key] for key in ('controllers', 'mangohud')}
        with patch.object(installer.sys, 'stdin', Terminal()), patch.object(installer.sys, 'stdout', Terminal()), patch('builtins.input', side_effect=['1 2', 'd', '', 'q']), patch.object(installer, 'execute', return_value=0) as execute:
            self.assertEqual(installer.menu(items), 0)
        self.assertEqual([(c.args[0]['id'], c.args[1]) for c in execute.call_args_list], [('controllers', 'docs'), ('mangohud', 'docs')])

    def test_menu_blank_boot_image_cancels_without_installing(self):
        items = {'boot-controller': self.items['boot-controller']}
        with patch.object(installer.sys, 'stdin', Terminal()), patch.object(installer.sys, 'stdout', Terminal()), patch('builtins.input', side_effect=['1', 'i', '', '', 'q']), patch.object(installer, 'execute') as execute:
            self.assertEqual(installer.menu(items), 0)
        execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
