#!/usr/bin/env python3
"""Check separate-name activation and restart on a private D-Bus daemon."""

import asyncio
import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

from dbus_next import Variant
from dbus_next.aio import MessageBus
from dbus_next.constants import MessageType

sys.path.insert(0, str(Path(__file__).parent))
from test_rapl import RaplTests

source = Path(__file__).resolve().parents[1]
hook_spec = importlib.util.spec_from_file_location("onex3_tdp_hook", source / "onex3_tdp_hook.py")
hook = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook)


async def exercise(address, fixture, marker):
    client = await asyncio.wait_for(MessageBus(bus_address=address).connect(), timeout=5)
    try:
        # This is the native manager's early probe, including auto-start. The
        # actual TDP provider name deliberately has no activation registration.
        reply = await hook.call(
            client, hook.BUS_NAME, "/", "org.freedesktop.DBus.Peer", "Ping", auto_start=True,
        )
        assert reply.message_type == MessageType.ERROR
        assert reply.error_name == "org.freedesktop.DBus.Error.ServiceUnknown"
        assert not marker.exists()
        await hook.stop_provider(client)
        assert not marker.exists()
        for watts in (17, 12):
            await hook.start_provider(client)
            assert await hook.has_owner(client)
            assert await hook.has_owner(client, hook.ACTIVATION_NAME)
            introspection = await client.introspect(hook.BUS_NAME, hook.OBJECT_PATH)
            obj = client.get_proxy_object(hook.BUS_NAME, hook.OBJECT_PATH, introspection)
            props = obj.get_interface("org.freedesktop.DBus.Properties")
            iface = "com.steampowered.SteamOSManager1.TdpLimit1"
            await props.call_set(iface, "TdpLimit", Variant("u", watts))
            current = {p: int(Path(p).read_text()) for p in fixture.original}
            assert all(value == watts * 1_000_000 for value in current.values())
            await hook.stop_provider(client)
            current = {p: int(Path(p).read_text()) for p in fixture.original}
            assert current == fixture.original
            assert not await hook.has_owner(client)
            assert not await hook.has_owner(client, hook.ACTIVATION_NAME)
        assert len(marker.read_text().splitlines()) == 2
        print("PASS: native early provider Ping cannot activate; distinct post-start activation works; two fresh process restarts restore original limits")
    finally:
        client.disconnect()


def main():
    fixture = RaplTests(methodName="test_names_dual_domain_readback_and_exact_restore")
    fixture.setUp()
    try:
        with tempfile.TemporaryDirectory(prefix="onex3-activate-", dir="/tmp") as private_dir:
            private = Path(private_dir)
            services = private / "services"
            services.mkdir()
            marker = private / "starts"
            child = private / "fake_provider.py"
            child.write_text(f"""import asyncio, importlib.util, os
from pathlib import Path
s=importlib.util.spec_from_file_location('onex3_tdp',{str(source / 'onex3_tdp.py')!r})
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
real=m.RaplBackend
m.RaplBackend=lambda low,high:real(low,high,Path({str(fixture.root)!r}))
m.manager_active=lambda user:True
os.environ['DBUS_SYSTEM_BUS_ADDRESS']=os.environ['DBUS_STARTER_ADDRESS']
with open({str(marker)!r},'a') as f:f.write(str(os.getpid())+'\\n')
asyncio.run(m.serve({{'min_w':2,'max_w':40,'session_user':'unused'}}))
""")
            activation = services / f"{hook.ACTIVATION_NAME}.service"
            activation.write_text(
                "[D-BUS Service]\n" + f"Name={hook.ACTIVATION_NAME}\n" +
                "Exec=" + shlex.join([sys.executable, str(child)]) + "\n"
            )
            config = private / "bus.conf"
            config.write_text(f"""<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN" "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig><type>session</type><listen>unix:path={private}/bus</listen><auth>EXTERNAL</auth>
<policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy>
<servicedir>{services}</servicedir></busconfig>
""")
            daemon = subprocess.Popen(
                ["dbus-daemon", f"--config-file={config}", "--nofork", "--print-address=1"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                address = daemon.stdout.readline().strip()
                if not address:
                    raise RuntimeError("Private bus failed to start")
                asyncio.run(exercise(address, fixture, marker))
            finally:
                daemon.terminate()
                daemon.wait(timeout=3)
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    main()
