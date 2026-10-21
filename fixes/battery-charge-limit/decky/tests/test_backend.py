import asyncio
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

spec = importlib.util.spec_from_file_location('charge_decky', Path(__file__).resolve().parents[1] / 'main.py')
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


class FakeBus:
    def __init__(self):
        self.mode = 'inhibit-charge-awake'
        self.modes = list(backend.MODES)
        self.limit = -1
        self.calls = []
        self.reject_set = False
        self.confirm_set = True

    async def __call__(self, *args):
        self.calls.append(args)
        assert args[1:3] == (backend.BUS, backend.OBJECT)
        if args[0] == 'set-property':
            assert args[3:6] == (backend.INTERFACE, 'Mode', 's')
            assert args[6] in backend.MODES
            if self.reject_set:
                raise RuntimeError('Access denied')
            if self.confirm_set:
                self.mode = args[6]
            return ''
        assert args[0] == 'get-property'
        if args[3:] == (backend.INTERFACE, 'Mode'):
            return json.dumps({'type': 's', 'data': [self.mode]})
        if args[3:] == (backend.INTERFACE, 'SupportedModes'):
            return json.dumps({'type': 'as', 'data': [self.modes]})
        assert args[3:] == (backend.LIMIT_INTERFACE, 'MaxChargeLevel')
        return json.dumps({'type': 'i', 'data': self.limit})


class BackendTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeBus()
        self.controls = backend.ChargeControls(self.fake)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        capacity = Path(temporary.name) / 'capacity'
        capacity.write_text('81\n')
        item = patch.object(backend, 'CAPACITY', capacity)
        item.start()
        self.addCleanup(item.stop)

    async def test_status_maps_signed_unlimited_and_preserves_awake_mode(self):
        result = await self.controls.get_status()
        self.assertTrue(result['ok'])
        self.assertEqual(result['limit'], 100)
        self.assertEqual(result['mode'], 'inhibit-charge-awake')
        self.assertEqual(result['percentage'], 81)
        self.assertTrue(all(call[0] == 'get-property' for call in self.fake.calls))

    async def test_ceiling_is_read_only_during_every_mode_change(self):
        self.fake.limit = 80
        for mode in backend.MODES:
            result = await self.controls.set_mode(mode)
            self.assertTrue(result['ok'])
            self.assertEqual(result['mode'], mode)
            self.assertEqual(result['limit'], 80)
        writes = [call for call in self.fake.calls if call[0] == 'set-property']
        self.assertEqual(len(writes), 3)
        self.assertTrue(all(call[3:6] == (backend.INTERFACE, 'Mode', 's') for call in writes))
        self.assertEqual(self.fake.limit, 80)

    async def test_invalid_inputs_never_start_a_command(self):
        for value in ('auto; reboot', '/usr/bin/id', '--help', 'AUTO', '', None, 1, [], {}):
            result = await self.controls.set_mode(value)
            self.assertFalse(result['ok'])
        self.assertEqual(self.fake.calls, [])

    async def test_mode_must_be_advertised_before_write(self):
        self.fake.modes = ['auto', 'inhibit-charge-awake']
        result = await self.controls.set_mode('inhibit-charge')
        self.assertFalse(result['ok'])
        self.assertFalse(any(call[0] == 'set-property' for call in self.fake.calls))

    async def test_unknown_advertised_mode_hides_controls(self):
        self.fake.modes.append('unknown-mode')
        result = await self.controls.get_status()
        self.assertFalse(result['ok'])
        self.assertEqual(result['supported_modes'], [])
        self.assertEqual(result['limit'], 100)

    async def test_access_failure_is_structured_without_retry_or_ceiling_write(self):
        self.fake.reject_set = True
        result = await self.controls.set_mode('auto')
        self.assertFalse(result['ok'])
        self.assertIn('Access denied', result['error'])
        self.assertEqual(sum(call[0] == 'set-property' for call in self.fake.calls), 1)
        self.assertEqual(self.fake.limit, -1)

    async def test_readback_mismatch_is_reported(self):
        self.fake.confirm_set = False
        result = await self.controls.set_mode('auto')
        self.assertFalse(result['ok'])
        self.assertIn('did not confirm', result['error'])

    async def test_plugin_lifecycle_has_no_hardware_calls(self):
        plugin = backend.Plugin()
        plugin.controls = self.controls
        await plugin._main()
        await plugin._unload()
        await plugin._uninstall()
        self.assertEqual(self.fake.calls, [])

    async def test_process_uses_fixed_executable_and_argument_vector(self):
        process = unittest.mock.Mock()
        process.returncode = 0
        process.communicate = AsyncMock(return_value=(b'{"type":"s","data":["auto"]}', b''))
        create = AsyncMock(return_value=process)
        with patch.object(asyncio, 'create_subprocess_exec', create):
            await backend.busctl('get-property', backend.BUS, backend.OBJECT, backend.INTERFACE, 'Mode')
        self.assertEqual(create.call_args.args,
            ('/usr/bin/busctl', '--system', '--json=short', '--timeout=5s',
             'get-property', backend.BUS, backend.OBJECT, backend.INTERFACE, 'Mode'))
        self.assertNotIn('shell', create.call_args.kwargs)

    def test_typed_busctl_json_forms(self):
        for value in (-1, 50, 100):
            self.assertEqual(backend.property_value(json.dumps({'type': 'i', 'data': [value]}), 'i'), value)
        self.assertEqual(backend.property_value('{"type":"s","data":"auto"}', 's'), 'auto')
        self.assertEqual(backend.property_value('{"type":"as","data":["auto"]}', 'as'), ['auto'])
        with self.assertRaises(ValueError):
            backend.property_value('{"type":"i","data":[true]}', 'i')
        with self.assertRaises(ValueError):
            backend.property_value('{"type":"s","data":["auto","inhibit-charge"]}', 's')


if __name__ == '__main__':
    unittest.main()
