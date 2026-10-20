#!/usr/bin/env python3
"""A RAPL-only SteamOS Manager TDP remote for ONEXPLAYER 3.

No EC commands, frequency policy, thermal-profile changes, or sensor emulation.
"""

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import pwd
import signal
import subprocess

BUS_NAME = "org.onex3.SteamOSManager.PowerControl"
ACTIVATION_NAME = "org.onex3.PowerControlActivator"
OBJECT_PATH = "/org/onex3/SteamOSManager/PowerControl"
TDP_INTERFACE = "com.steampowered.SteamOSManager1.TdpLimit1"
REMOTE_INTERFACE = "com.steampowered.SteamOSManager1.RemoteInterface1"
MICROWATTS = 1_000_000
READBACK_TOLERANCE_UW = 125_000
LOG = logging.getLogger("onex3-tdp")


class RaplError(RuntimeError):
    pass


def read_number(path):
    return int(path.read_text().strip())


def check_device(dmi_root=Path("/sys/class/dmi/id")):
    def normalized(name):
        return "".join(c for c in (dmi_root / name).read_text().upper() if c.isalnum())

    if normalized("sys_vendor") != "ONENETBOOK" or normalized("product_name") != "ONEXPLAYER3":
        raise RaplError("This TDP provider is restricted to ONE-NETBOOK ONEXPLAYER 3")


class RaplBackend:
    def __init__(self, min_w, max_w, powercap_root=Path("/sys/class/powercap")):
        if type(min_w) is not int or type(max_w) is not int or not 1 <= min_w <= max_w:
            raise RaplError("Invalid configured TDP range")
        self.min_w = int(min_w)
        self.max_w = int(max_w)
        self.powercap_root = Path(powercap_root)
        self.constraints = self._discover_constraints()
        self.baseline = self.snapshot()
        self.last_applied = None
        self.has_requests = False

    def _discover_constraints(self):
        constraints = []
        found_types = set()
        for zone in sorted(self.powercap_root.glob("intel-rapl*:*")):
            # Only top-level package zones; never core, DRAM, psys or uncore.
            if zone.name.count(":") != 1 or not zone.is_dir():
                continue
            try:
                name = (zone / "name").read_text().strip()
            except OSError:
                continue
            control_type = zone.name.split(":", 1)[0]
            if name != "package-0" or control_type not in {"intel-rapl", "intel-rapl-mmio"}:
                continue
            if control_type in found_types:
                raise RaplError(f"Multiple package-0 zones in one control type: {control_type}")
            if read_number(zone / "enabled") != 1:
                raise RaplError(f"RAPL package controls are disabled: {zone}")
            named = {}
            for name_file in sorted(zone.glob("constraint_*_name")):
                constraint_name = name_file.read_text().strip()
                if constraint_name not in {"long_term", "short_term"}:
                    continue
                if constraint_name in named:
                    raise RaplError(f"Duplicate {constraint_name} constraint: {zone}")
                path = zone / name_file.name.replace("_name", "_power_limit_uw")
                if not path.is_file():
                    raise RaplError(f"Missing RAPL control: {path}")
                read_number(path)
                named[constraint_name] = path
            if set(named) != {"long_term", "short_term"}:
                raise RaplError(f"Both long_term and short_term constraints are required: {zone}")
            found_types.add(control_type)
            for kind in ("long_term", "short_term"):
                constraints.append((control_type, kind, named[kind]))
        if found_types != {"intel-rapl", "intel-rapl-mmio"}:
            raise RaplError("Both MSR and MMIO package-0 RAPL domains are required")
        return constraints

    def snapshot(self):
        return {str(path): read_number(path) for _, _, path in self.constraints}

    def status(self):
        actual = self.snapshot()
        return {
            "min_w": self.min_w,
            "max_w": self.max_w,
            "sustained_limit_w": self.read_limit_w(),
            "constraints_uw": actual,
            "policy": "PL1 and PL2 equal requested watts in both package domains",
        }

    def read_limit_w(self):
        minimum = min(read_number(path) for _, kind, path in self.constraints if kind == "long_term")
        return (minimum + MICROWATTS // 2) // MICROWATTS

    def _write(self, path, value):
        path.write_text(str(value))

    def _verify(self, path, value):
        actual = read_number(path)
        if abs(actual - value) > READBACK_TOLERANCE_UW:
            raise RaplError(f"RAPL readback mismatch: {path}: requested {value}, read {actual}")
        return actual

    def _transaction(self, desired):
        before = self.snapshot()
        touched = []
        try:
            for _, _, path in self.constraints:
                key = str(path)
                if before[key] == desired[key]:
                    continue
                # Include the attempted file: a failed write may have changed it.
                touched.append(path)
                self._write(path, desired[key])
                self._verify(path, desired[key])
            for _, _, path in self.constraints:
                self._verify(path, desired[str(path)])
            return self.snapshot()
        except Exception as original_error:
            failures = []
            for path in reversed(touched):
                try:
                    self._write(path, before[str(path)])
                    self._verify(path, before[str(path)])
                except Exception as rollback_error:
                    failures.append(f"{path}: {rollback_error}")
            if failures:
                raise RaplError(
                    f"TDP change failed ({original_error}); rollback failed: {'; '.join(failures)}"
                ) from original_error
            raise RaplError(f"TDP change failed; previous values restored: {original_error}") from original_error

    def set_limit_w(self, watts):
        if isinstance(watts, bool) or not isinstance(watts, int) or not self.min_w <= watts <= self.max_w:
            raise RaplError(f"TDP must be an integer between {self.min_w} and {self.max_w} W")
        desired = {str(path): watts * MICROWATTS for _, _, path in self.constraints}
        self.has_requests = True
        actual = self._transaction(desired)
        self.last_applied = actual
        LOG.info("TDP request %d W; actual package constraints %s", watts, json.dumps(actual))
        minimum = min(actual[str(path)] for _, kind, path in self.constraints if kind == "long_term")
        return (minimum + MICROWATTS // 2) // MICROWATTS

    def restore(self):
        if not self.has_requests:
            return
        restored = self._transaction(self.baseline)
        self.last_applied = None
        self.has_requests = False
        LOG.info("Restored original package limits: %s", json.dumps(restored))


def manager_active(user):
    uid = pwd.getpwnam(user).pw_uid
    result = subprocess.run(
        [
            "/usr/bin/runuser", "-u", user, "--", "/usr/bin/env",
            f"XDG_RUNTIME_DIR=/run/user/{uid}",
            f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus",
            "/usr/bin/systemctl", "--user", "show", "steamos-manager.service",
            "--property=ActiveState", "--property=SubState", "--property=Type",
        ],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=5, check=False,
    )
    if result.returncode != 0:
        return False
    state = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    return state.get("ActiveState") == "active" or (
        state.get("ActiveState") == "activating"
        and state.get("SubState") == "start-post"
        and state.get("Type") in {"notify", "notify-reload"}
    )


async def serve(config):
    # Keep hardware-only tools/tests independent of the optional D-Bus dependency.
    from dbus_next.aio import MessageBus
    from dbus_next.constants import BusType, PropertyAccess, RequestNameReply
    from dbus_next.errors import DBusError
    from dbus_next.service import ServiceInterface, dbus_property, method

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    # Advertise only after the notify daemon has sent READY=1. ExecStartPost
    # itself activates this provider, so start-post is also a ready state.
    while not stop.is_set():
        if await asyncio.to_thread(manager_active, config["session_user"]):
            break
        try:
            await asyncio.wait_for(stop.wait(), timeout=1)
        except asyncio.TimeoutError:
            pass
    if stop.is_set():
        return

    # Snapshot as the provider becomes available, after any startup firmware or
    # power-profile changes, rather than when the service began waiting.
    backend = RaplBackend(config["min_w"], config["max_w"])
    LOG.info("Captured original package constraints: %s", json.dumps(backend.baseline))

    class TdpInterface(ServiceInterface):
        def __init__(self):
            super().__init__(TDP_INTERFACE)

        @dbus_property(access=PropertyAccess.READWRITE)
        def TdpLimit(self) -> "u":
            return backend.read_limit_w()

        @TdpLimit.setter
        def TdpLimit(self, value: "u"):
            try:
                actual = backend.set_limit_w(value)
            except (RaplError, OSError, ValueError) as error:
                raise DBusError("org.onex3.PowerControl.Error", str(error)) from error
            self.emit_properties_changed({"TdpLimit": actual})

        @dbus_property(access=PropertyAccess.READ)
        def TdpLimitMin(self) -> "u":
            return backend.min_w

        @dbus_property(access=PropertyAccess.READ)
        def TdpLimitMax(self) -> "u":
            return backend.max_w

    class RemoteInterface(ServiceInterface):
        def __init__(self):
            super().__init__(REMOTE_INTERFACE)

        @dbus_property(access=PropertyAccess.READ)
        def RemoteInterfaces(self) -> "as":
            return [TDP_INTERFACE]

    class LifecycleInterface(ServiceInterface):
        def __init__(self):
            super().__init__("org.onex3.PowerControl1")

        @method()
        async def Pause(self):
            try:
                backend.restore()
            except (RaplError, OSError, ValueError) as error:
                raise DBusError("org.onex3.PowerControl.Error", str(error)) from error
            # Finish hardware restoration before withdrawing the advertised
            # name. The hook waits for this withdrawal before manager startup.
            await bus.release_name(BUS_NAME)
            await bus.release_name(ACTIVATION_NAME)
            stop.set()

    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    bus.export(OBJECT_PATH, TdpInterface())
    bus.export(OBJECT_PATH, RemoteInterface())
    bus.export(OBJECT_PATH, LifecycleInterface())
    reply = await bus.request_name(BUS_NAME)
    if reply != RequestNameReply.PRIMARY_OWNER:
        bus.disconnect()
        raise RaplError("Another process already owns the TDP provider name")
    activation_reply = await bus.request_name(ACTIVATION_NAME)
    if activation_reply != RequestNameReply.PRIMARY_OWNER:
        await bus.release_name(BUS_NAME)
        bus.disconnect()
        raise RaplError("Another process already owns the TDP activation name")
    LOG.info("RAPL TDP remote active, range %d–%d W", backend.min_w, backend.max_w)
    try:
        stopping = asyncio.create_task(stop.wait())
        disconnected = asyncio.create_task(bus.wait_for_disconnect())
        done, pending = await asyncio.wait({stopping, disconnected}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            task.result()
    finally:
        try:
            backend.restore()
        finally:
            if bus.connected:
                await bus.release_name(BUS_NAME)
                await bus.release_name(ACTIVATION_NAME)
            bus.disconnect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["serve", "status"])
    parser.add_argument("--config", default="/etc/onex3-tdp.json")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    if os.geteuid() != 0:
        parser.error("Run as root; RAPL write permissions remain private")
    check_device()
    config = json.loads(Path(args.config).read_text())
    if args.command == "status":
        print(json.dumps(RaplBackend(config["min_w"], config["max_w"]).status(), indent=2))
    else:
        asyncio.run(serve(config))


if __name__ == "__main__":
    main()
