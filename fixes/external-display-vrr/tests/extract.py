#!/usr/bin/env python3
"""Extract the functions under test verbatim, never a rewritten implementation."""
import hashlib
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parent.parent
out = pathlib.Path(sys.argv[1])
functions = {
    "intel_dp.c": ["intel_dp_pcon_vrr_capable", "intel_dp_needs_as_sdp",
                   "intel_dp_compute_as_sdp", "intel_dp_as_sdp_pack",
                   "intel_dp_as_sdp_unpack"],
    "intel_vrr.c": ["intel_vrr_get_range", "intel_vrr_is_capable",
                    "intel_vrr_is_in_range"],
}

def extract(text, name):
    pattern = (r"(?m)^(?:static\s+)?(?:ssize_t|bool|int|void|"
               r"struct drm_monitor_range_info)\s+" + re.escape(name)
               + r"\s*\([^;]*?\)\s*\{")
    match = re.search(pattern, text)
    if not match:
        raise RuntimeError(f"Cannot find definition of {name}")
    start = match.start()
    pos = match.end()
    depth = 1
    while depth:
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
        pos += 1
    return text[start:pos]

with out.open("w") as dest:
    dest.write("/* Generated verbatim from the current source files. */\n")
    for filename, names in functions.items():
        path = root / "tests/fixtures" / filename
        source = path.read_text()
        print(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root)}")
        for name in names:
            dest.write(extract(source, name) + "\n\n")
    baseline = root / "tests/fixtures/baseline_intel_dp.c"
    source = baseline.read_text()
    for name in ["intel_dp_as_sdp_pack", "intel_dp_as_sdp_unpack"]:
        dest.write(extract(source, name).replace(name, "baseline_" + name) + "\n\n")
