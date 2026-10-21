"""Unprivileged Decky adapter for the OXP3 provider's independent charge modes."""

import asyncio
import json
from pathlib import Path

BUSCTL = '/usr/bin/busctl'
BUS = 'org.onex3.SteamOSManager.ChargeLimit'
OBJECT = '/org/onex3/SteamOSManager/ChargeLimit'
INTERFACE = 'org.onex3.ChargeBehaviour1'
LIMIT_INTERFACE = 'com.steampowered.SteamOSManager1.BatteryChargeLimit1'
CAPACITY = Path('/sys/class/power_supply/BAT0/capacity')
MODES = ('auto', 'inhibit-charge-awake', 'inhibit-charge')


async def busctl(*arguments):
    process = await asyncio.create_subprocess_exec(
        BUSCTL, '--system', '--json=short', '--timeout=5s', *arguments,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=7)
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        raise RuntimeError('The charge-control provider did not answer in time.') from None
    if process.returncode:
        detail = stderr.decode(errors='replace').strip()[:300]
        raise RuntimeError(detail or 'The charge-control provider is unavailable.')
    return stdout.decode()


def property_value(output, signature):
    document = json.loads(output)
    if not isinstance(document, dict) or document.get('type') != signature:
        raise ValueError('Unexpected charge-control property signature.')
    value = document.get('data')
    # busctl represents the message body as a list; older serializers may
    # expose a single property's value directly. Accept only these typed forms.
    if isinstance(value, list) and len(value) == 1:
        if signature != 'as' or isinstance(value[0], list):
            value = value[0]
    if signature == 's' and isinstance(value, str):
        return value
    if signature == 'i' and type(value) is int:
        return value
    if signature == 'as' and isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    raise ValueError('Unexpected charge-control property data.')


def percentage():
    try:
        value = int(CAPACITY.read_text().strip())
        return value if 0 <= value <= 100 else None
    except (OSError, ValueError):
        return None


class ChargeControls:
    def __init__(self, runner=busctl):
        self.runner = runner
        self.lock = asyncio.Lock()

    async def get_property(self, interface, name, signature):
        output = await self.runner('get-property', BUS, OBJECT, interface, name)
        return property_value(output, signature)

    async def supported_modes(self):
        modes = await self.get_property(INTERFACE, 'SupportedModes', 'as')
        if not modes or any(mode not in MODES for mode in modes) or len(set(modes)) != len(modes):
            raise ValueError('The provider did not advertise valid charge modes.')
        return modes

    async def status(self):
        mode, modes, limit = await asyncio.gather(
            self.get_property(INTERFACE, 'Mode', 's'), self.supported_modes(),
            self.get_property(LIMIT_INTERFACE, 'MaxChargeLevel', 'i'),
            return_exceptions=True)
        result = {'ok': False, 'mode': None, 'supported_modes': [],
                  'limit': None, 'percentage': percentage(), 'error': None}
        if not isinstance(limit, Exception):
            if limit == -1:
                result['limit'] = 100
            elif 50 <= limit <= 100:
                result['limit'] = limit
        if isinstance(mode, Exception) or isinstance(modes, Exception):
            error = mode if isinstance(mode, Exception) else modes
            result['error'] = str(error)
        elif mode not in MODES or mode not in modes:
            result['error'] = 'The current charge mode was not advertised by the provider.'
        else:
            result.update(ok=True, mode=mode, supported_modes=modes)
        return result

    async def get_status(self):
        async with self.lock:
            return await self.status()

    async def set_mode(self, mode):
        # Validate before any subprocess; this RPC accepts no executable,
        # service, property, path, signature or command supplied by the caller.
        if not isinstance(mode, str) or mode not in MODES:
            return {'ok': False, 'error': 'Unsupported charge mode.'}
        async with self.lock:
            try:
                if mode not in await self.supported_modes():
                    return {'ok': False, 'error': 'This mode is not supported by the device.'}
                await self.runner('set-property', BUS, OBJECT, INTERFACE, 'Mode', 's', mode)
                result = await self.status()
                if result['ok'] and result['mode'] != mode:
                    result.update(ok=False, error='The provider did not confirm the requested mode.')
                return result
            except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
                return {'ok': False, 'error': str(error)}


class Plugin:
    def __init__(self):
        self.controls = ChargeControls()

    async def _main(self):
        pass

    async def _unload(self):
        pass

    async def _uninstall(self):
        pass

    async def get_status(self):
        return await self.controls.get_status()

    async def set_mode(self, mode):
        return await self.controls.set_mode(mode)
