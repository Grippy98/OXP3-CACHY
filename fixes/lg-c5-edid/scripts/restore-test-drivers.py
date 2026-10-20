#!/usr/bin/env python3
"""Keep the original kernel's USB-C and hotplug input support in the test."""
import pathlib
import re
import subprocess
import sys

if len(sys.argv) != 2:
    sys.exit('Usage (from prepared kernel tree): restore-test-drivers.py ORIGINAL_CONFIG')
original = pathlib.Path(sys.argv[1]).read_text()
for symbol, value in re.findall(r'^CONFIG_((?:TYPEC|UCSI|BT_HCIBTUSB|JOYSTICK_XPAD)[A-Z0-9_]*|USB_ROLE_SWITCH)=(m|y)$', original, re.M):
    subprocess.run(['scripts/config', '--module' if value == 'm' else '--enable', symbol], check=True)

for symbol in ('BT_HIDP', 'HID_MICROSOFT', 'HID_SONY', 'HID_STEAM',
               'HID_APPLE', 'USB_NET_CDC_NCM', 'USB_NET_AX8817X',
               'USB_NET_AX88179_178A', 'USB_XHCI_PCI_RENESAS'):
    value = re.search(r'^CONFIG_' + symbol + r'=(m|y)$', original, re.M)
    if value:
        subprocess.run(['scripts/config', '--module' if value[1] == 'm' else '--enable', symbol], check=True)
