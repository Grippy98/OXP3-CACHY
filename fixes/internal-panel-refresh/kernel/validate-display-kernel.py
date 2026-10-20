#!/usr/bin/env python3
"""Validate the locally staged cross-built payload; no target interaction."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


stage = Path(sys.argv[1]).resolve()
report_path = Path(sys.argv[2])
release = "7.2.9-onex3-display-test"
package = "linux-onex3-display-test"
modules_root = stage / "usr/lib/modules"
assert sorted(p.name for p in modules_root.iterdir()) == [release]
module_dir = modules_root / release
assert (module_dir / "pkgbase").read_text().strip() == package
assert sha256(module_dir / "config") == "80b1ece7b9185d75b7df202ac0dfbf544983e131be9ee98285fffed6dae2b72c"
config = (module_dir / "config").read_text()
subprocess.run([sys.executable, str(Path(__file__).with_name("require-inputplumber-kernel.py")),
                str(module_dir / "config"), str(module_dir)], check=True)
for option in ("CONFIG_DRM_XE=m", "CONFIG_DRM_XE_DISPLAY=y", "CONFIG_DRM_I915=m",
               "CONFIG_MODULE_SIG_ALL=y", "CONFIG_MODULE_COMPRESS_ZSTD=y",
               "CONFIG_DEBUG_INFO_BTF=y", "CONFIG_DEBUG_INFO_BTF_MODULES=y"):
    assert option in config
assert 'CONFIG_RUST=y' not in config
modules = sorted(module_dir.rglob("*.ko.zst"))
assert len(modules) == 281, len(modules)
assert (module_dir / "updates/dkms/hid-oxp.ko.zst").is_file()
vermagics, signers = set(), set()
display_btf = {}
for path in modules:
    data = subprocess.check_output(["zstd", "-dc", str(path)])
    assert data[:6] == b"\x7fELF\x02\x01", path
    assert struct.unpack_from("<H", data, 18)[0] == 62, path  # EM_X86_64
    shoff = struct.unpack_from("<Q", data, 40)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 58)
    str_header = shoff + shstrndx * shentsize
    str_offset, str_size = struct.unpack_from("<QQ", data, str_header + 24)
    string_table = data[str_offset:str_offset + str_size]
    sections = set()
    for index in range(shnum):
        name_offset = struct.unpack_from("<I", data, shoff + index * shentsize)[0]
        sections.add(string_table[name_offset:].split(b"\0", 1)[0].decode())
    assert ".debug_info" not in sections, path
    if path.name in ("xe.ko.zst", "i915.ko.zst"):
        assert ".BTF" in sections, path
        display_btf[path.name] = True
    vermagic = subprocess.check_output(["modinfo", "-F", "vermagic", str(path)], text=True).strip()
    assert vermagic.startswith(release + " "), (path, vermagic)
    signer = subprocess.check_output(["modinfo", "-F", "signer", str(path)], text=True).strip()
    assert signer, path
    vermagics.add(vermagic)
    signers.add(signer)
assert len(vermagics) == 1
assert len(signers) == 1
assert display_btf == {"i915.ko.zst": True, "xe.ko.zst": True}
for filename in ("modules.dep", "modules.dep.bin", "modules.alias", "modules.alias.bin",
                 "modules.builtin", "modules.builtin.modinfo", "modules.order", "System.map"):
    assert (module_dir / filename).is_file(), filename
assert (module_dir / "vmlinuz").stat().st_size > 1_000_000
assert not any(path.is_symlink() for path in stage.rglob("*"))
assert not any(path.name.endswith((".pem", ".key")) for path in stage.rglob("*"))
assert not (module_dir / "build").exists()
assert not (module_dir / "source").exists()
assert not (stage / "usr/bin").exists()
assert not (stage / "usr/include").exists()
pkginfo = (stage / ".PKGINFO").read_text()
for line in (f"pkgname = {package}", "pkgver = 7.2.9-3", "arch = x86_64"):
    assert line in pkginfo
report = {
    "status": "local payload validation passed; not installed or booted",
    "release": release,
    "package": package,
    "package_version": "7.2.9-3",
    "architecture": "x86_64",
    "module_count": len(modules),
    "all_modules_elf64_x86_64": True,
    "all_modules_signed": True,
    "all_modules_dwarf_debug_stripped": True,
    "display_module_btf_retained": display_btf,
    "module_vermagic": sorted(vermagics),
    "config_sha256": sha256(module_dir / "config"),
    "kernel_image_sha256": sha256(module_dir / "vmlinuz"),
    "kernel_image_bytes": (module_dir / "vmlinuz").stat().st_size,
    "kernel_headers_host_tools_private_keys_absent": True,
    "module_indexes_present": True,
    "controller_pr13_override_included": True,
    "inputplumber_uhid_uinput_transports_included": True,
    "inputplumber_steam_microsoft_hid_drivers_included": True,
    "controller_pr13_module_sha256": sha256(module_dir / "updates/dkms/hid-oxp.ko.zst"),
}
report_path.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
