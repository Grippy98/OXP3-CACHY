#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate the archived and tested YAMLs against InputPlumber 0.81.0 schemas.

Requires PyYAML and jsonschema in the Python environment running this script.
This script reads local files only and never modifies the Linux device.
"""
import json
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent
SCHEMAS = ROOT / "reference-v0.81.0/rootfs/usr/share/inputplumber/schema"
CASES = (
    ("pr660/rootfs/usr/share/inputplumber/devices/50-onexplayer_3.yaml", "composite_device_v1.json"),
    ("pr660/rootfs/usr/share/inputplumber/capability_maps/onexplayer_type9.yaml", "capability_map_v1.json"),
    ("local-config/etc/inputplumber/devices.d/50-onexplayer_3.yaml", "composite_device_v1.json"),
    ("local-config/etc/inputplumber/capability_maps.d/onexplayer_type9.yaml", "capability_map_v1.json"),
)
for filename, schema_name in CASES:
    schema = json.loads((SCHEMAS / schema_name).read_text())
    jsonschema.validate(yaml.safe_load((ROOT / filename).read_text()), schema)
    print(f"PASS {filename}")
