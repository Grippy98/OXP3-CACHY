#!/usr/bin/env python3
"""Expose the OXP3's standard battery charge threshold to SteamOS Manager.

Starting and stopping this provider only reads the existing firmware setting.
Only an explicit MaxChargeLevel D-Bus property write changes the threshold.
"""

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import signal
import stat
import sys


BUS_NAME = "org.onex3.SteamOSManager.ChargeLimit"
OBJECT_PATH = "/org/onex3/SteamOSManager/ChargeLimit"
CHARGE_INTERFACE = "com.steampowered.SteamOSManager1.BatteryChargeLimit1"
REMOTE_INTERFACE = "com.steampowered.SteamOSManager1.RemoteInterface1"
ERROR_NAME = "org.onex3.ChargeLimit.Error"
MINIMUM_LIMIT = 50
ATTRIBUTE = "charge_control_end_threshold"
ACPI_BATTERY_PATHS = (
    "sys/bus/platform/drivers/acpi-battery/PNP0C0A:00/firmware_node",
    "sys/bus/acpi/drivers/battery/PNP0C0A:00",
)
LOG = logging.getLogger("onex3-charge-limit")


class ChargeLimitError(RuntimeError):
    """The exact supported battery or its validated threshold is unavailable."""


class ChargeLimitBackend:
    def __init__(self, system_root=Path("/")):
        # A different root exists solely for synthetic sysfs tests, not the CLI.
        self.root = Path(system_root).resolve(strict=True)
        self.battery = self._find_battery()
        self.read_raw()

    def _find_battery(self):
        vendor = (self.root / "sys/class/dmi/id/sys_vendor").read_text().strip()
        product = (self.root / "sys/class/dmi/id/product_name").read_text().strip()
        if (vendor, product) != ("ONE-NETBOOK", "ONEXPLAYER 3"):
            raise ChargeLimitError("Only ONE-NETBOOK ONEXPLAYER 3 is supported")
        battery = (self.root / "sys/class/power_supply/BAT0").resolve(strict=True)
        if battery.name != "BAT0" or battery.parent.name != "power_supply":
            raise ChargeLimitError("BAT0 is not the expected ACPI battery")
        bases = []
        for relative in ACPI_BATTERY_PATHS:
            try:
                bases.append((self.root / relative).resolve(strict=True))
            except FileNotFoundError:
                pass
        if battery.parent.parent not in bases:
            raise ChargeLimitError("BAT0 is not bound to the supported ACPI battery")
        if (battery / "type").read_text().strip() != "Battery":
            raise ChargeLimitError("BAT0 is not a battery power supply")
        threshold = battery / ATTRIBUTE
        if threshold.is_symlink() or threshold.resolve(strict=True) != threshold:
            raise ChargeLimitError("Battery threshold must be the battery's own sysfs property")
        if not threshold.is_file():
            raise ChargeLimitError("The standard battery charge threshold is unavailable")
        return battery

    def _threshold(self):
        if self._find_battery() != self.battery:
            raise ChargeLimitError("The ACPI battery changed while the provider was running")
        return self.battery / ATTRIBUTE

    def _open_threshold(self, flags):
        path = self._threshold()
        descriptor = os.open(path, flags | os.O_NOFOLLOW | os.O_CLOEXEC)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise ChargeLimitError("Battery threshold is not a regular sysfs property")
        return descriptor

    def read_raw(self):
        with os.fdopen(self._open_threshold(os.O_RDONLY), "r", encoding="ascii") as source:
            text = source.read(32).strip()
        try:
            value = int(text)
        except ValueError as error:
            raise ChargeLimitError("The battery threshold is not an integer") from error
        if not MINIMUM_LIMIT <= value <= 100:
            raise ChargeLimitError("The battery threshold is outside the supported 50–100% range")
        return value

    def read_limit(self):
        value = self.read_raw()
        return -1 if value == 100 else value

    def set_limit(self, level):
        if type(level) is not int or (level != -1 and not MINIMUM_LIMIT <= level <= 100):
            raise ChargeLimitError("MaxChargeLevel must be -1 (unlimited) or an integer from 50 to 100")
        target = 100 if level == -1 else level
        if self.read_raw() != target:
            # Never pass SteamOS Manager's generic reset value 0 to this firmware.
            # This is the sole write path, called only for an explicit API request.
            with os.fdopen(self._open_threshold(os.O_WRONLY | os.O_TRUNC), "w", encoding="ascii") as destination:
                destination.write(f"{target}\n")
            if self.read_raw() != target:
                raise ChargeLimitError("The battery did not confirm the requested charge threshold")
        return -1 if target == 100 else target

    def status(self):
        raw = self.read_raw()
        return {
            "supported": True,
            "battery": "BAT0",
            "raw_threshold_percent": raw,
            "max_charge_level": -1 if raw == 100 else raw,
            "suggested_minimum_limit": MINIMUM_LIMIT,
        }


async def serve(backend=None, *, bus_address=None, stop_event=None, poll_interval=2):
    # Read-only diagnostics and backend tests need no D-Bus Python dependency.
    from dbus_next.aio import MessageBus
    from dbus_next.constants import BusType, NameFlag, PropertyAccess, RequestNameReply
    from dbus_next.errors import DBusError
    from dbus_next.service import ServiceInterface, dbus_property

    backend = backend if backend is not None else ChargeLimitBackend()
    last_level = backend.read_limit()
    stop = stop_event if stop_event is not None else asyncio.Event()
    loop = asyncio.get_running_loop()
    signals = []
    if stop_event is None:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
            signals.append(sig)

    class ChargeInterface(ServiceInterface):
        def __init__(self):
            super().__init__(CHARGE_INTERFACE)

        @dbus_property(access=PropertyAccess.READWRITE)
        def MaxChargeLevel(self) -> "i":
            try:
                return backend.read_limit()
            except (ChargeLimitError, OSError, ValueError) as error:
                raise DBusError(ERROR_NAME, str(error)) from error

        @MaxChargeLevel.setter
        def MaxChargeLevel(self, value: "i"):
            nonlocal last_level
            try:
                last_level = backend.set_limit(value)
            except (ChargeLimitError, OSError, ValueError) as error:
                raise DBusError(ERROR_NAME, str(error)) from error
            self.emit_properties_changed({"MaxChargeLevel": last_level})

        @dbus_property(access=PropertyAccess.READ)
        def SuggestedMinimumLimit(self) -> "i":
            return MINIMUM_LIMIT

    class RemoteInterface(ServiceInterface):
        def __init__(self):
            super().__init__(REMOTE_INTERFACE)

        @dbus_property(access=PropertyAccess.READ)
        def RemoteInterfaces(self) -> "as":
            return [CHARGE_INTERFACE]

    bus = None
    owned = False
    tasks = []
    try:
        bus = await (MessageBus(bus_address=bus_address) if bus_address else MessageBus(bus_type=BusType.SYSTEM)).connect()
        charge = ChargeInterface()
        bus.export(OBJECT_PATH, charge)
        bus.export(OBJECT_PATH, RemoteInterface())
        reply = await bus.request_name(BUS_NAME, NameFlag.DO_NOT_QUEUE)
        if reply != RequestNameReply.PRIMARY_OWNER:
            raise ChargeLimitError("Another process already owns the charge-limit provider name")
        owned = True
        LOG.info("Battery charge remote active; existing firmware threshold preserved")

        async def watch_threshold():
            nonlocal last_level
            while True:
                await asyncio.sleep(poll_interval)
                # Reflect changes made by KDE or firmware without writing them back.
                actual = backend.read_limit()
                if actual != last_level:
                    last_level = actual
                    charge.emit_properties_changed({"MaxChargeLevel": actual})

        tasks = [asyncio.create_task(stop.wait()), asyncio.create_task(bus.wait_for_disconnect()), asyncio.create_task(watch_threshold())]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if bus is not None:
            if owned and bus.connected:
                await bus.release_name(BUS_NAME)
            bus.disconnect()
        for sig in signals:
            loop.remove_signal_handler(sig)
        # No restore, reset, save or resume writes: firmware owns persistence.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("serve", "status", "check"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    try:
        backend = ChargeLimitBackend()
        if args.command == "serve":
            if os.geteuid() != 0:
                parser.error("The system-bus provider must run as root; sysfs permissions stay private")
            asyncio.run(serve(backend))
        else:
            print(json.dumps(backend.status(), indent=2))
    except (ChargeLimitError, OSError, ValueError, ImportError) as error:
        print(f"onex3-charge-limit: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
