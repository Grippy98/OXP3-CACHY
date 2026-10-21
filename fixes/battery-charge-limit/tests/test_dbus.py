#!/usr/bin/env python3
"""Real D-Bus ABI tests on an isolated private bus and synthetic battery.

Included in unittest discovery; skipped when dbus-next/dbus-daemon is missing.
No connection to the host system bus or real sysfs is made.
"""

import asyncio
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_provider import BatteryFixture, provider

HAVE_DBUS = importlib.util.find_spec("dbus_next") is not None and shutil.which("dbus-daemon") is not None
if HAVE_DBUS:
    from dbus_next import Variant
    from dbus_next.aio import MessageBus
    from dbus_next.errors import DBusError


@unittest.skipUnless(HAVE_DBUS, "dbus-next and dbus-daemon are needed for private-bus integration tests")
class DBusTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="onex3-charge-", dir="/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.fixture = BatteryFixture(Path(self.temporary.name) / "sysroot")
        self.daemon = subprocess.Popen([
            "dbus-daemon", "--session", "--nofork", "--print-address=1",
            f"--address=unix:path={self.temporary.name}/bus",
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.stop_daemon)
        self.address = self.daemon.stdout.readline().strip()
        if not self.address:
            self.fail(f"Private D-Bus daemon did not start: {self.daemon.stderr.read()}")
        self.client = await MessageBus(bus_address=self.address).connect()
        self.stop = asyncio.Event()
        self.server = None
        self.addAsyncCleanup(self.stop_server)

    def stop_daemon(self):
        self.daemon.terminate()
        self.daemon.communicate(timeout=3)

    async def stop_server(self):
        self.stop.set()
        if self.server is not None:
            await asyncio.wait_for(asyncio.gather(self.server, return_exceptions=True), 3)
        self.client.disconnect()
        await self.client.wait_for_disconnect()

    async def start_server(self):
        self.server = asyncio.create_task(provider.serve(self.fixture.backend(), bus_address=self.address, stop_event=self.stop, poll_interval=0.02))
        for _ in range(100):
            if self.server.done():
                self.server.result()
            try:
                self.introspection = await self.client.introspect(provider.BUS_NAME, provider.OBJECT_PATH)
                break
            except DBusError:
                await asyncio.sleep(0.01)
        else:
            self.fail("The provider did not acquire its private-bus name")
        obj = self.client.get_proxy_object(provider.BUS_NAME, provider.OBJECT_PATH, self.introspection)
        return obj.get_interface("org.freedesktop.DBus.Properties")

    async def test_signed_steam_abi_reset_and_passive_lifecycle(self):
        before = self.fixture.threshold.stat().st_mtime_ns
        bypass_before = self.fixture.behaviour.stat().st_mtime_ns
        props = await self.start_server()
        self.assertEqual(self.fixture.threshold.stat().st_mtime_ns, before)
        values = await props.call_get_all(provider.CHARGE_INTERFACE)
        self.assertEqual({key: (value.signature, value.value) for key, value in values.items()}, {
            "MaxChargeLevel": ("i", 80), "SuggestedMinimumLimit": ("i", 50),
        })
        remote = await props.call_get(provider.REMOTE_INTERFACE, "RemoteInterfaces")
        self.assertEqual((remote.signature, remote.value), ("as", [provider.CHARGE_INTERFACE]))
        xml = self.introspection.to_xml()
        properties = xml.find(f"interface[@name='{provider.CHARGE_INTERFACE}']").findall("property")
        self.assertEqual({p.attrib["name"]: (p.attrib["type"], p.attrib["access"]) for p in properties}, {
            "MaxChargeLevel": ("i", "readwrite"), "SuggestedMinimumLimit": ("i", "read"),
        })
        changes = []
        props.on_properties_changed(lambda interface, changed, invalidated: changes.append((interface, changed, invalidated)))
        await props.call_set(provider.CHARGE_INTERFACE, "MaxChargeLevel", Variant("i", 73))
        self.assertEqual(self.fixture.threshold.read_text(), "73\n")
        await props.call_set(provider.CHARGE_INTERFACE, "MaxChargeLevel", Variant("i", -1))
        self.assertEqual(self.fixture.threshold.read_text(), "100\n")
        self.assertEqual((await props.call_get(provider.CHARGE_INTERFACE, "MaxChargeLevel")).value, -1)
        await props.call_set(provider.CHARGE_INTERFACE, "MaxChargeLevel", Variant("i", 80))
        await asyncio.sleep(0.03)
        self.assertTrue(any(interface == provider.CHARGE_INTERFACE and changed.get("MaxChargeLevel", Variant("i", 0)).value == -1 for interface, changed, _ in changes))
        for invalid in (0, 49, 101, -2):
            with self.subTest(invalid=invalid), self.assertRaises(DBusError) as caught:
                await props.call_set(provider.CHARGE_INTERFACE, "MaxChargeLevel", Variant("i", invalid))
            self.assertEqual(caught.exception.type, provider.ERROR_NAME)
            self.assertEqual(self.fixture.threshold.read_text(), "80\n")
        with self.assertLogs(level="ERROR"), self.assertRaises(DBusError):
            await props.call_set(provider.CHARGE_INTERFACE, "SuggestedMinimumLimit", Variant("i", 10))
        before_stop = self.fixture.threshold.stat().st_mtime_ns
        self.stop.set()
        await asyncio.wait_for(self.server, 3)
        self.assertEqual(self.fixture.threshold.read_text(), "80\n")
        self.assertEqual(self.fixture.threshold.stat().st_mtime_ns, before_stop)
        self.assertEqual(self.fixture.behaviour.stat().st_mtime_ns, bypass_before)
        self.assertEqual(self.fixture.behaviour_writes, [])

    async def test_behaviour_abi_is_explicit_and_independent_of_ceiling(self):
        before = self.fixture.behaviour.stat().st_mtime_ns
        props = await self.start_server()
        self.assertEqual(self.fixture.behaviour.stat().st_mtime_ns, before)
        values = await props.call_get_all(provider.BEHAVIOUR_INTERFACE)
        self.assertEqual({key: (value.signature, value.value) for key, value in values.items()}, {
            "Mode": ("s", "inhibit-charge-awake"),
            "SupportedModes": ("as", ["auto", "inhibit-charge", "inhibit-charge-awake"]),
        })
        properties = self.introspection.to_xml().find(f"interface[@name='{provider.BEHAVIOUR_INTERFACE}']").findall("property")
        self.assertEqual({p.attrib["name"]: (p.attrib["type"], p.attrib["access"]) for p in properties}, {
            "Mode": ("s", "readwrite"), "SupportedModes": ("as", "read"),
        })
        self.assertEqual((await props.call_get(provider.REMOTE_INTERFACE, "RemoteInterfaces")).value, [provider.CHARGE_INTERFACE])
        await props.call_set(provider.CHARGE_INTERFACE, "MaxChargeLevel", Variant("i", -1))
        self.assertEqual((await props.call_get(provider.BEHAVIOUR_INTERFACE, "Mode")).value, "inhibit-charge-awake")
        self.assertEqual(self.fixture.behaviour_writes, [])
        ceiling_before = self.fixture.threshold.stat().st_mtime_ns
        changes = []
        props.on_properties_changed(lambda interface, changed, invalidated: changes.append((interface, changed)))
        for mode in ("inhibit-charge", "auto"):
            await props.call_set(provider.BEHAVIOUR_INTERFACE, "Mode", Variant("s", mode))
            self.assertEqual((await props.call_get(provider.BEHAVIOUR_INTERFACE, "Mode")).value, mode)
            self.assertEqual(self.fixture.threshold.read_text(), "100\n")
            self.assertEqual(self.fixture.threshold.stat().st_mtime_ns, ceiling_before)
        self.assertEqual(self.fixture.behaviour_writes, ["inhibit-charge\n", "auto\n"])
        await asyncio.sleep(0.03)
        self.assertTrue(any(interface == provider.BEHAVIOUR_INTERFACE and changed.get("Mode", Variant("s", "")).value == "auto" for interface, changed in changes))
        for invalid in ("", "force-discharge", "[auto]", "auto\n", "auto;reboot"):
            with self.subTest(invalid=invalid), self.assertRaises(DBusError) as caught:
                await props.call_set(provider.BEHAVIOUR_INTERFACE, "Mode", Variant("s", invalid))
            self.assertEqual(caught.exception.type, provider.ERROR_NAME)
        with self.assertLogs(level="ERROR"), self.assertRaises(DBusError):
            await props.call_set(provider.BEHAVIOUR_INTERFACE, "SupportedModes", Variant("as", ["auto"]))
        bypass_before_stop = self.fixture.behaviour.stat().st_mtime_ns
        self.stop.set()
        await asyncio.wait_for(self.server, 3)
        self.assertEqual(self.fixture.behaviour.stat().st_mtime_ns, bypass_before_stop)
        self.assertEqual(self.fixture.threshold.stat().st_mtime_ns, ceiling_before)
        self.assertEqual(self.fixture.behaviour_writes, ["inhibit-charge\n", "auto\n"])

    async def test_missing_behaviour_omits_only_optional_interface(self):
        self.fixture.behaviour.unlink()
        props = await self.start_server()
        self.assertNotIn(provider.BEHAVIOUR_INTERFACE, [interface.name for interface in self.introspection.interfaces])
        self.assertEqual((await props.call_get(provider.CHARGE_INTERFACE, "MaxChargeLevel")).value, 80)
        self.assertEqual((await props.call_get(provider.REMOTE_INTERFACE, "RemoteInterfaces")).value, [provider.CHARGE_INTERFACE])
        self.assertFalse(self.fixture.behaviour.exists())

    async def test_external_behaviour_change_and_disappearance_preserve_ceiling(self):
        props = await self.start_server()
        changed = asyncio.Event()

        def on_changed(interface, values, invalidated):
            if interface == provider.BEHAVIOUR_INTERFACE and values.get("Mode", Variant("s", "")).value == "inhibit-charge":
                changed.set()

        props.on_properties_changed(on_changed)
        self.fixture.set_kernel_mode("inhibit-charge")
        before = self.fixture.behaviour.stat().st_mtime_ns
        await asyncio.wait_for(changed.wait(), 2)
        self.assertEqual(self.fixture.behaviour.stat().st_mtime_ns, before)
        self.assertEqual(self.fixture.behaviour_writes, [])
        self.fixture.behaviour.unlink()
        for _ in range(100):
            introspection = await self.client.introspect(provider.BUS_NAME, provider.OBJECT_PATH)
            if provider.BEHAVIOUR_INTERFACE not in [interface.name for interface in introspection.interfaces]:
                break
            await asyncio.sleep(0.01)
        else:
            self.fail("Unsupported bypass interface was not withdrawn")
        self.assertEqual((await props.call_get(provider.CHARGE_INTERFACE, "MaxChargeLevel")).value, 80)
        self.assertFalse(self.server.done())
        self.assertEqual(self.fixture.threshold.read_text(), "80\n")
        self.assertFalse(self.fixture.behaviour.exists())

    async def test_external_change_notified_without_background_write(self):
        props = await self.start_server()
        changed = asyncio.Event()

        def on_changed(interface, values, invalidated):
            if interface == provider.CHARGE_INTERFACE and values.get("MaxChargeLevel", Variant("i", 0)).value == 65:
                changed.set()

        props.on_properties_changed(on_changed)
        self.fixture.threshold.write_text("65\n")
        before = self.fixture.threshold.stat().st_mtime_ns
        await asyncio.wait_for(changed.wait(), 2)
        self.assertEqual((await props.call_get(provider.CHARGE_INTERFACE, "MaxChargeLevel")).value, 65)
        self.assertEqual(self.fixture.threshold.stat().st_mtime_ns, before)

    async def test_duplicate_service_is_rejected_without_reset_or_queue(self):
        await self.start_server()
        with self.assertRaisesRegex(provider.ChargeLimitError, "already owns"):
            await provider.serve(self.fixture.backend(), bus_address=self.address, stop_event=asyncio.Event())
        self.assertEqual(self.fixture.threshold.read_text(), "80\n")
        self.stop.set()
        await asyncio.wait_for(self.server, 3)
        bus = self.client.get_proxy_object("org.freedesktop.DBus", "/org/freedesktop/DBus", await self.client.introspect("org.freedesktop.DBus", "/org/freedesktop/DBus")).get_interface("org.freedesktop.DBus")
        self.assertFalse(await bus.call_name_has_owner(provider.BUS_NAME))

    async def test_missing_threshold_withdraws_support(self):
        await self.start_server()
        self.fixture.threshold.unlink()
        with self.assertRaises(FileNotFoundError):
            await asyncio.wait_for(self.server, 2)
        bus = self.client.get_proxy_object("org.freedesktop.DBus", "/org/freedesktop/DBus", await self.client.introspect("org.freedesktop.DBus", "/org/freedesktop/DBus")).get_interface("org.freedesktop.DBus")
        self.assertFalse(await bus.call_name_has_owner(provider.BUS_NAME))
        self.assertFalse(self.fixture.threshold.exists())


if __name__ == "__main__":
    unittest.main()
