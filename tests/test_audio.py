"""Pulse protocol/state tests with a fake server; no pactl or audio device use."""
from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('audio_profile', ROOT / 'fixes/tv-audio-profile/audio-profile.py')
audio = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audio)
SPEAKERS = 'alsa_output.fixture.analog-stereo'
HEADPHONES = 'alsa_output.headset.analog-stereo'
HDMI = 'alsa_output.tv.hdmi-stereo'
PROFILE = 'output:hdmi-stereo'


def card(name='alsa_card.tv', index=12, available=True):
    return {'name': name, 'index': index, 'active_profile': {'name': 'off'},
            'profiles': {'off': {'available': True}, PROFILE: {'available': available}}}


class FakePulse:
    def __init__(self, delay=0):
        self.cards = [card()]
        self.sinks = [{'index': 5, 'name': SPEAKERS, 'card': 10},
                      {'index': 8, 'name': HEADPHONES, 'card': 11}]
        self.streams = [{'index': 100, 'sink': 5}, {'index': 200, 'sink': 8}]
        self.default = SPEAKERS
        self.commands = []
        self.delay = delay
        self.pending = None
        self.sink_reads = 0
        self.fail_once = None
        self.before_command = None

    def listing(self, kind):
        if kind == 'cards':
            return deepcopy(self.cards)
        if kind == 'sink-inputs':
            return deepcopy(self.streams)
        if kind != 'sinks':
            raise AssertionError(kind)
        self.sink_reads += 1
        if self.pending is not None:
            if self.pending == 0:
                self.sinks.append({'index': 30, 'name': HDMI, 'card': 12})
                self.pending = None
            else:
                self.pending -= 1
        return deepcopy(self.sinks)

    def command(self, *args):
        args = tuple(map(str, args))
        self.commands.append(args)
        if self.before_command:
            self.before_command(args)
        if args == self.fail_once:
            self.fail_once = None
            raise subprocess.CalledProcessError(1, ['pactl', *args])
        if args == ('get-default-sink',):
            return self.default
        if args[0] == 'set-card-profile':
            selected = next(c for c in self.cards if c['name'] == args[1])
            previous = audio.active_profile(selected)
            selected['active_profile'] = {'name': args[2]}
            if args[2] == PROFILE and previous != PROFILE:
                self.pending = self.delay
            elif args[2] == 'off':
                self.pending = None
                self.sinks = [s for s in self.sinks if s['name'] != HDMI]
            return ''
        if args[0] == 'set-default-sink':
            assert any(s['name'] == args[1] for s in self.sinks), args
            self.default = args[1]
            return ''
        if args[0] == 'move-sink-input':
            stream = next(s for s in self.streams if str(s['index']) == args[1])
            stream['sink'] = next(s['index'] for s in self.sinks if s['name'] == args[2])
            return ''
        raise AssertionError(args)


class AudioTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name) / 'preferences/state.json'
        self.pulse = FakePulse()
        self.fix = audio.AudioFix(self.pulse, self.state)
        self.stdout = redirect_stdout(io.StringIO())
        self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None, None, None)
        sleep = patch.object(audio.time, 'sleep')
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)

    def saved(self):
        return json.loads(self.state.read_text())

    def test_ambiguous_cards_require_an_explicit_card(self):
        cards = [card(), card('alsa_card.second', 15)]
        with self.assertRaisesRegex(ValueError, '--card'):
            audio.choose(cards)
        self.assertEqual(audio.choose(cards, '15')[0]['name'], 'alsa_card.second')

    def test_unavailable_profiles_and_boolean_json_values(self):
        for value in (False, 0, 'no'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                audio.choose([card(available=value)])
        selected = card()
        selected['profiles'] = [
            {'name': 'output:hdmi-stereo-unplugged', 'available': False},
            {'name': 'output:hdmi-stereo-unknown', 'available': 'unknown'},
            {'name': PROFILE, 'available': True},
        ]
        self.assertEqual(audio.choose([selected])[1], PROFILE)
        self.assertEqual(audio.active_profile(selected), 'off')
        selected['active_profile'] = PROFILE
        self.assertEqual(audio.active_profile(selected), PROFILE)

    def test_multiple_available_profiles_require_an_explicit_profile(self):
        selected = card()
        selected['profiles']['output:hdmi-stereo-extra1'] = {'available': 'yes'}
        with self.assertRaisesRegex(ValueError, '--profile'):
            audio.choose([selected])
        self.assertEqual(audio.choose([selected], profile_name=PROFILE)[1], PROFILE)

    def test_install_waits_for_async_sink_and_preserves_volume_and_mute(self):
        self.pulse.delay = 3
        self.fix.install()
        self.assertEqual(self.pulse.default, HDMI)
        self.assertEqual(audio.active_profile(self.pulse.cards[0]), PROFILE)
        self.assertGreaterEqual(self.sleep.call_count, 3)
        self.assertEqual(self.saved()['previous_default'], SPEAKERS)
        self.assertEqual(self.saved()['previous_profile'], 'off')
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)
        self.assertFalse(any('volume' in command[0] or 'mute' in command[0] for command in self.pulse.commands))

    def test_rollback_restores_profile_default_and_each_original_stream(self):
        self.fix.install(move_streams=True)
        self.assertEqual([s['sink'] for s in self.pulse.streams], [30, 30])
        self.fix.rollback()
        self.assertEqual(audio.active_profile(self.pulse.cards[0]), 'off')
        self.assertEqual(self.pulse.default, SPEAKERS)
        self.assertEqual([s['sink'] for s in self.pulse.streams], [5, 8])
        self.assertFalse(self.state.exists())
        self.assertTrue(self.state.with_name('last-rollback.json').is_file())

    def test_reapply_then_new_move_streams_snapshots_before_moving(self):
        self.fix.install()
        first = self.saved()
        self.fix.install()
        self.assertEqual(self.saved(), first)
        self.pulse.streams.append({'index': 300, 'sink': 8})
        expected = {'100': SPEAKERS, '200': HEADPHONES, '300': HEADPHONES}
        def require_durable_baseline(command):
            if command[0] == 'move-sink-input' and command[2] == HDMI:
                self.assertEqual(self.saved()['streams'], expected)
        self.pulse.before_command = require_durable_baseline
        self.fix.install(move_streams=True)
        self.assertEqual(self.saved()['streams'], expected)
        self.assertEqual(self.saved()['previous_profile'], 'off')
        self.assertEqual(self.saved()['previous_default'], SPEAKERS)
        self.fix.rollback()
        self.assertEqual([s['sink'] for s in self.pulse.streams], [5, 8, 8])

    def test_repeated_move_preserves_old_baselines_and_adds_new_streams(self):
        self.fix.install(move_streams=True)
        self.pulse.streams.append({'index': 300, 'sink': 8})
        self.fix.install(move_streams=True)
        self.assertEqual(self.saved()['streams'], {'100': SPEAKERS, '200': HEADPHONES, '300': HEADPHONES})
        self.fix.rollback()
        self.assertEqual([s['sink'] for s in self.pulse.streams], [5, 8, 8])

    def test_failure_after_partial_stream_moves_restores_the_complete_baseline(self):
        self.pulse.fail_once = ('move-sink-input', '200', HDMI)
        with self.assertRaises(subprocess.CalledProcessError):
            self.fix.install(move_streams=True)
        self.assertEqual(audio.active_profile(self.pulse.cards[0]), 'off')
        self.assertEqual(self.pulse.default, SPEAKERS)
        self.assertEqual([s['sink'] for s in self.pulse.streams], [5, 8])
        self.assertFalse(self.state.exists())

    def test_failure_setting_default_restores_profile_without_stream_moves(self):
        self.pulse.fail_once = ('set-default-sink', HDMI)
        with self.assertRaises(subprocess.CalledProcessError):
            self.fix.install()
        self.assertEqual(audio.active_profile(self.pulse.cards[0]), 'off')
        self.assertEqual(self.pulse.default, SPEAKERS)
        self.assertEqual([s['sink'] for s in self.pulse.streams], [5, 8])
        self.assertFalse(self.state.exists())

    def test_changed_external_preference_refuses_rollback_without_mutation(self):
        self.fix.install()
        self.pulse.default = HEADPHONES
        before = len(self.pulse.commands)
        with self.assertRaisesRegex(ValueError, 'Default output changed'):
            self.fix.rollback()
        self.assertEqual(self.pulse.commands[before:], [('get-default-sink',)])
        self.assertEqual(self.pulse.default, HEADPHONES)
        self.assertTrue(self.state.exists())

    def test_unknown_original_profile_refuses_changes_without_a_backup(self):
        self.pulse.cards[0]['active_profile'] = None
        with self.assertRaisesRegex(ValueError, 'Original card profile is unknown'):
            self.fix.install()
        self.assertEqual(self.pulse.commands, [])
        self.assertFalse(self.state.exists())

    def test_disconnected_card_retains_rollback_state_until_reconnected(self):
        self.fix.install()
        original = self.state.read_bytes()
        self.pulse.cards = []
        before = len(self.pulse.commands)
        with self.assertRaisesRegex(ValueError, 'Saved card is unavailable'):
            self.fix.rollback()
        self.assertEqual(self.state.read_bytes(), original)
        self.assertEqual(len(self.pulse.commands), before)
        self.pulse.cards = [card()]
        self.pulse.cards[0]['active_profile'] = PROFILE
        self.fix.rollback()
        self.assertEqual(self.pulse.default, SPEAKERS)
        self.assertFalse(self.state.exists())

    def test_rollback_handles_closed_streams_without_moving_new_streams(self):
        self.fix.install(move_streams=True)
        self.pulse.streams = [{'index': 200, 'sink': 30}, {'index': 300, 'sink': 8}]
        self.fix.rollback()
        self.assertEqual(self.pulse.streams, [{'index': 200, 'sink': 8}, {'index': 300, 'sink': 8}])

    def test_pactl_uses_a_vector_without_shell_interpolation(self):
        argument = 'card name; $(touch sentinel)'
        with patch.object(audio.subprocess, 'run', return_value=type('Result', (), {'stdout': 'ok\n'})()) as run:
            self.assertEqual(audio.Pulse().command('set-card-profile', argument, PROFILE), 'ok')
        self.assertEqual(run.call_args.args[0], ['pactl', 'set-card-profile', argument, PROFILE])
        self.assertNotIn('shell', run.call_args.kwargs)


if __name__ == '__main__':
    unittest.main()
