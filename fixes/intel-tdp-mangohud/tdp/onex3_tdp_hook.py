#!/usr/bin/env python3
"""Order this local TDP remote around SteamOS Manager user-service starts."""

import argparse
import asyncio
import time

from dbus_next import Message
from dbus_next.aio import MessageBus
from dbus_next.constants import BusType, MessageFlag, MessageType

BUS_NAME = "org.onex3.SteamOSManager.PowerControl"
ACTIVATION_NAME = "org.onex3.PowerControlActivator"
OBJECT_PATH = "/org/onex3/SteamOSManager/PowerControl"


async def call(bus, destination, path, interface, member, signature="", body=None, auto_start=False):
    reply = await asyncio.wait_for(
        bus.call(Message(
            destination=destination, path=path, interface=interface, member=member,
            signature=signature, body=body or [],
            flags=MessageFlag.NONE if auto_start else MessageFlag.NO_AUTOSTART,
        )), timeout=5,
    )
    return reply


async def has_owner(bus, name=BUS_NAME):
    reply = await call(
        bus, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
        "NameHasOwner", "s", [name],
    )
    if reply.message_type == MessageType.ERROR:
        raise RuntimeError(f"Cannot query provider owner: {reply.error_name}: {reply.body}")
    return bool(reply.body[0])


async def stop_provider(bus):
    # The owner query does not activate the provider. NO_AUTO_START also closes
    # the race where a provider disappears between this query and the Pause.
    provider_owned = await has_owner(bus)
    activation_owned = await has_owner(bus, ACTIVATION_NAME)
    if not provider_owned and not activation_owned:
        return
    destination = BUS_NAME if provider_owned else ACTIVATION_NAME
    reply = await call(bus, destination, OBJECT_PATH, "org.onex3.PowerControl1", "Pause")
    if reply.message_type == MessageType.ERROR and (
        await has_owner(bus) or await has_owner(bus, ACTIVATION_NAME)
    ):
        raise RuntimeError(f"Cannot pause provider: {reply.error_name}: {reply.body}")
    deadline = time.monotonic() + 10
    while await has_owner(bus) or await has_owner(bus, ACTIVATION_NAME):
        if time.monotonic() >= deadline:
            raise RuntimeError("Provider did not withdraw its name after Pause")
        await asyncio.sleep(0.05)


async def start_provider(bus):
    # This runs in ExecStartPost after READY=1. A method call with auto-start
    # uses the root-owned system-bus activation file, without sudo/polkit.
    deadline = time.monotonic() + 20
    while True:
        try:
            reply = await call(
                bus, ACTIVATION_NAME, "/", "org.freedesktop.DBus.Peer", "Ping", auto_start=True,
            )
            if reply.message_type != MessageType.ERROR:
                return
            error = f"{reply.error_name}: {reply.body}"
        except asyncio.TimeoutError:
            error = "Activation timed out"
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Cannot activate TDP provider: {error}")
        await asyncio.sleep(0.1)


async def hook(command):
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    try:
        if command == "stop":
            await stop_provider(bus)
        else:
            await start_provider(bus)
    finally:
        bus.disconnect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["stop", "start"])
    args = parser.parse_args()
    asyncio.run(hook(args.command))


if __name__ == "__main__":
    main()
