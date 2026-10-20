#!/usr/bin/env python3
"""Exercise the actual D-Bus API on a private bus and temporary fake sysfs.

Requires dbus-daemon and dbus-next. Does not contact the host's system bus.
"""

import asyncio
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

from dbus_next import Variant
from dbus_next.constants import MessageType
from dbus_next.aio import MessageBus
from dbus_next.errors import DBusError

sys.path.insert(0, str(Path(__file__).parent))
from test_rapl import RaplTests

spec = importlib.util.spec_from_file_location("onex3_tdp", Path(__file__).parents[1] / "onex3_tdp.py")
tdp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tdp)
hook_spec = importlib.util.spec_from_file_location("onex3_tdp_hook", Path(__file__).parents[1] / "onex3_tdp_hook.py")
hook = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook)


async def exercise(address, fixture):
    real_backend = tdp.RaplBackend
    captured = []

    def fake_backend(low, high):
        backend = real_backend(low, high, fixture.root)
        captured.append(backend)
        return backend

    tdp.RaplBackend = fake_backend
    tdp.manager_active = lambda user: True
    os.environ["DBUS_SYSTEM_BUS_ADDRESS"] = address
    server = asyncio.create_task(tdp.serve({"min_w": 2, "max_w": 40, "session_user": "unused"}))
    client = await MessageBus(bus_address=address).connect()
    try:
        for _ in range(100):
            if server.done():
                server.result()
            try:
                introspection = await client.introspect(tdp.BUS_NAME, tdp.OBJECT_PATH)
                break
            except DBusError:
                await asyncio.sleep(0.01)
        else:
            raise AssertionError("Provider did not own its private-bus name")
        obj = client.get_proxy_object(tdp.BUS_NAME, tdp.OBJECT_PATH, introspection)
        ping = await hook.call(client, tdp.BUS_NAME, "/", "org.freedesktop.DBus.Peer", "Ping")
        assert ping.message_type == MessageType.METHOD_RETURN
        await hook.start_provider(client)
        properties = obj.get_interface("org.freedesktop.DBus.Properties")
        before = await properties.call_get_all(tdp.TDP_INTERFACE)
        assert {k: v.value for k, v in before.items()} == {"TdpLimit": 25, "TdpLimitMin": 2, "TdpLimitMax": 40}
        await properties.call_set(tdp.TDP_INTERFACE, "TdpLimit", Variant("u", 17))
        assert (await properties.call_get(tdp.TDP_INTERFACE, "TdpLimit")).value == 17
        assert all(value == 17_000_000 for value in captured[0].snapshot().values())
        try:
            await properties.call_set(tdp.TDP_INTERFACE, "TdpLimit", Variant("u", 41))
        except DBusError as error:
            assert error.type == "org.onex3.PowerControl.Error"
        else:
            raise AssertionError("An out-of-range request was accepted")
        assert all(value == 17_000_000 for value in captured[0].snapshot().values())
        remote = await properties.call_get(tdp.REMOTE_INTERFACE, "RemoteInterfaces")
        assert remote.value == [tdp.TDP_INTERFACE]
        await hook.stop_provider(client)
        await asyncio.wait_for(server, timeout=3)
        assert captured[0].snapshot() == fixture.original
        assert not await hook.has_owner(client)
        assert not await hook.has_owner(client, tdp.ACTIVATION_NAME)
        await hook.stop_provider(client)  # Missing owner must not activate anything.
        # Start another fresh provider and exercise the independent SIGTERM path.
        server = asyncio.create_task(tdp.serve({"min_w": 2, "max_w": 40, "session_user": "unused"}))
        for _ in range(100):
            if await hook.has_owner(client):
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("Second provider did not start")
        second = client.get_proxy_object(tdp.BUS_NAME, tdp.OBJECT_PATH, introspection).get_interface("org.freedesktop.DBus.Properties")
        await second.call_set(tdp.TDP_INTERFACE, "TdpLimit", Variant("u", 12))
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(server, timeout=3)
        assert captured[1].snapshot() == fixture.original
        print("PASS: real D-Bus ABI, Ping('/'), hook Pause/name withdrawal/exact restore, missing-owner no activation, fresh restart and SIGTERM restore")
    finally:
        client.disconnect()
        if not server.done():
            os.kill(os.getpid(), signal.SIGTERM)
            await asyncio.wait_for(server, timeout=3)


def main():
    fixture = RaplTests(methodName="test_names_dual_domain_readback_and_exact_restore")
    fixture.setUp()
    try:
        with tempfile.TemporaryDirectory(prefix="onex3-dbus-", dir="/tmp") as private:
            daemon = subprocess.Popen(
                ["dbus-daemon", "--session", "--nofork", "--print-address=1", f"--address=unix:path={private}/bus"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                address = daemon.stdout.readline().strip()
                if not address:
                    raise RuntimeError("Private D-Bus daemon did not start")
                asyncio.run(exercise(address, fixture))
            finally:
                daemon.terminate()
                daemon.wait(timeout=3)
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    main()
