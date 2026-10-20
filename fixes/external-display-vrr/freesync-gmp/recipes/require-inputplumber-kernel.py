#!/usr/bin/env python3
"""Reject an experimental kernel that cannot provide InputPlumber targets."""
from pathlib import Path
import sys

config_path = Path(sys.argv[1])
options = {}
for line in config_path.read_text().splitlines():
    if line.startswith("CONFIG_") and "=" in line:
        key, value = line.split("=", 1)
        options[key] = value

required = {
    "CONFIG_UHID": "m",
    "CONFIG_INPUT_UINPUT": "m",
    "CONFIG_HID": "y",
    "CONFIG_HID_GENERIC": "y",
    "CONFIG_HID_MICROSOFT": "m",
    "CONFIG_HID_STEAM": "m",
}
for key, value in required.items():
    if options.get(key) != value:
        raise SystemExit(f"InputPlumber kernel prerequisite missing: {key}={value}")

if len(sys.argv) > 2:
    module_dir = Path(sys.argv[2])
    for relative in (
        "kernel/drivers/hid/uhid.ko.zst",
        "kernel/drivers/input/misc/uinput.ko.zst",
        "kernel/drivers/hid/hid-microsoft.ko.zst",
        "kernel/drivers/hid/hid-steam.ko.zst",
    ):
        if not (module_dir / relative).is_file():
            raise SystemExit(f"InputPlumber kernel payload missing: {relative}")

print("InputPlumber kernel prerequisites passed")
