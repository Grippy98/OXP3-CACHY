#!/usr/bin/env python3
"""Test the saved experimental patch against extracted DRM code with mock I2C.

This does not edit the downloaded kernel source, build a kernel, or touch a
device. The C harness uses the actual source functions, not a rewrite.
"""

from pathlib import Path
import difflib
import os
import re
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / "cachyos-src/upstream/drivers/gpu/drm/drm_edid.c"
PATCH = ROOT / "edid-segment-reset-retry.patch"


def extract_function(source: str, name: str) -> str:
    # These two source functions have ordinary brace bodies and no braces in
    # string literals. Keep their implementation exactly as downloaded.
    start = re.search(r"(?:static int\n|int )" + name + r"\(", source)
    assert start, name
    brace = source.index("{", start.start())
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start.start():end]


def main() -> None:
    source = SOURCE.read_text()
    anchor = "\t\tret = i2c_transfer(adapter, &msgs[3 - xfers], xfers);\n"
    assert source.count(anchor) == 1
    addition = """
		/*
		 * A base block with no matching header bytes may have come
		 * from a stale non-zero segment pointer. Retry with an
		 * explicit segment zero, while preserving the two-message
		 * path for normal reads and potentially repairable headers.
		 */
		if (block == 0 && len >= EDID_LENGTH && xfers == 2 &&
		    ret == xfers && drm_edid_header_is_valid(buf) == 0)
			xfers = 3;
"""
    candidate = source.replace(anchor, anchor + addition)
    patch = "".join(difflib.unified_diff(
        source.splitlines(keepends=True), candidate.splitlines(keepends=True),
        fromfile="a/drivers/gpu/drm/drm_edid.c",
        tofile="b/drivers/gpu/drm/drm_edid.c"))
    assert PATCH.read_text() == patch, "Saved patch differs from the reviewed candidate"

    # Confirm the saved patch applies to an untouched temporary copy of the
    # exact downloaded source. No git checkout or original file is modified.
    with tempfile.TemporaryDirectory(prefix="edid-patch-check-") as td:
        target = Path(td) / "drivers/gpu/drm/drm_edid.c"
        target.parent.mkdir(parents=True)
        target.write_text(source)
        subprocess.run(["git", "apply", "--check", str(PATCH)], cwd=td,
                       check=True)
        subprocess.run(["git", "apply", str(PATCH)], cwd=td, check=True)
        assert target.read_text() == candidate

    header_array = re.search(
        r"static const u8 edid_header\[\] = \{.*?\n\};", source, re.S).group()
    header_function = extract_function(source, "drm_edid_header_is_valid")
    original = extract_function(source, "drm_do_probe_ddc_edid").replace(
        "drm_do_probe_ddc_edid(", "original_drm_do_probe_ddc_edid(", 1)
    modified = extract_function(candidate, "drm_do_probe_ddc_edid")
    # Synthetic test blocks: valid base header versus a retained nonzero segment.
    # No display serials or captured EDID payloads are distributed or required.
    base = bytearray(128)
    base[:8] = bytes.fromhex("00ffffffffffff00")
    base[127] = -sum(base) % 256
    stale = bytearray([0x70, 0x12, 0x79, 0x22] + [0x11] * 123 + [0])
    stale[127] = -sum(stale) % 256
    fixtures = []
    for name, data in (("synthetic_base", base), ("synthetic_block2", stale)):
        rows = [", ".join(f"0x{v:02x}" for v in data[i:i + 16])
                for i in range(0, len(data), 16)]
        fixtures.append("static const u8 " + name + "[EDID_LENGTH] = {\n\t"
                        + ",\n\t".join(rows) + "\n};\n")
    with tempfile.TemporaryDirectory(prefix="edid-host-test-") as td:
        work = Path(td)
        (work / "extracted_functions.inc").write_text(
            source[:source.index("*/") + 2] + "\n"
            + header_array + "\n\n" + header_function + "\n\n"
            + original + "\n\n" + modified + "\n")
        (work / "synthetic_fixtures.inc").write_text("\n".join(fixtures))
        (work / "test.c").write_text((HERE / "test_edid_segment_retry.c").read_text())
        cc = os.environ.get("CC", "clang")
        exe = work / "test-edid-segment-retry"
        subprocess.run([
            cc, "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-Wno-sign-compare", "-Wno-unused-parameter", "-g",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
            str(work / "test.c"), "-o", str(exe),
        ], check=True)
        subprocess.run([str(exe)], check=True)
    print("Saved patch applies exactly; source and repository were not modified.")


if __name__ == "__main__":
    main()
