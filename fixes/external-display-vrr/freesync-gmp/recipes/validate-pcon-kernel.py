#!/usr/bin/env python3
"""Validate the locally staged cross-built payload; no target interaction."""
import hashlib
import json
import re
from pathlib import Path
import struct
import subprocess
import sys
import tempfile


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


stage = Path(sys.argv[1]).resolve()
report_path = Path(sys.argv[2])
evidence = Path(sys.argv[3]).resolve()
assert (evidence / "build.exit").read_text().strip() == "0"
release = "7.2.9-onex3-pcon-vrr-test"
package = "linux-onex3-pcon-vrr-test"
modules_root = stage / "usr/lib/modules"
assert sorted(p.name for p in modules_root.iterdir()) == [release]
module_dir = modules_root / release
assert (module_dir / "pkgbase").read_text().strip() == package
assert (module_dir / "config").read_bytes() == (evidence / "pcon-kernel.config").read_bytes()
config = (module_dir / "config").read_text()
subprocess.run([sys.executable, str(Path(__file__).parent / "require-inputplumber-kernel.py"),
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
display_parameters = {}
for name in ("i915", "xe"):
    path = next(path for path in modules if path.name == name + ".ko.zst")
    parameters = subprocess.check_output(["modinfo", "-F", "parm", str(path)], text=True)
    types = subprocess.check_output(["modinfo", "-F", "parmtype", str(path)], text=True)
    assert "enable_dc_balance:bool" in types
    assert "enable_dc_balance:Enable VRR DC balance" in parameters
    assert "Default: 0 (disabled)" in parameters
    assert "enable_pcon_vrr:int" in types
    assert "enable_pcon_vrr:Experimental SST HDMI PCON VRR" in parameters
    assert "Default: 0" in parameters
    assert "pcon_freesync_sdp:bool" in types
    freesync_description = next(line for line in parameters.splitlines()
                                if line.startswith("pcon_freesync_sdp:"))
    assert "Experimental FreeSync SDP via GMP" in freesync_description
    assert "Default: false" in freesync_description
    display_parameters[name] = {"dc_balance_type": "bool", "dc_balance_documented_default": False,
                                "pcon_vrr_type": "int", "pcon_vrr_documented_default": 0,
                                "pcon_freesync_sdp_type": "bool", "pcon_freesync_sdp_documented_default": False}
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
dependency_checks = {}
with tempfile.TemporaryDirectory(prefix="onex3-pcon-vrr-module-check-") as temporary:
    # kmod expects lib/modules. The actual package uses Arch's usr/lib layout.
    dependency_root = Path(temporary)
    (dependency_root / "lib").symlink_to(stage / "usr/lib", target_is_directory=True)
    for name in ("xe", "i915", "uhid", "uinput", "hid-oxp", "hid-steam", "hid-microsoft",
                 "char-major-10-239", "char-major-10-223", "devname:uhid", "devname:uinput"):
        output = subprocess.check_output(
            ["modprobe", "-d", temporary, "-S", release, "--show-depends", name], text=True)
        dependencies = []
        for line in output.splitlines():
            if line.startswith("insmod "):
                path = Path(line.split()[1])
                assert path.is_file(), (name, path)
                dependencies.append(str(path.relative_to(dependency_root / "lib/modules")))
        assert dependencies, name
        if name == "hid-oxp":
            assert dependencies[-1] == release + "/updates/dkms/hid-oxp.ko.zst"
        dependency_checks[name] = dependencies
device_names = (module_dir / "modules.devname").read_text()
assert "uhid uhid c10:239" in device_names
assert "uinput uinput c10:223" in device_names
pkginfo = (stage / ".PKGINFO").read_text()
for line in (f"pkgname = {package}", "pkgver = 7.2.9-3", "arch = x86_64"):
    assert line in pkginfo
patch_path = evidence / "intel-pcon-vrr-experimental.patch"
mode_vtotal_patch_path = evidence / "intel-vrr-mode-vtotal-f26a8df.patch"
freesync_patch_path = evidence / "intel-pcon-freesync-gmp-prototype.patch"
assert re.search(r"^\+\s*param\(bool,\s*pcon_freesync_sdp,\s*false,",
                 freesync_patch_path.read_text(), re.MULTILINE), "Prototype source default must be false"
doc_path = stage / "usr/share/doc" / package
assert patch_path.read_bytes() == (doc_path / patch_path.name).read_bytes()
assert mode_vtotal_patch_path.read_bytes() == (doc_path / mode_vtotal_patch_path.name).read_bytes()
assert freesync_patch_path.read_bytes() == (doc_path / freesync_patch_path.name).read_bytes()
assert (module_dir / "vmlinuz").read_bytes() == (evidence / "bzImage").read_bytes()
assert sha256(module_dir / "updates/dkms/hid-oxp.ko.zst") == sha256(evidence / "controller-module/hid-oxp.ko.zst")
report = {
    "status": "local payload validation passed; not installed or booted",
    "release": release,
    "package": package,
    "package_version": "7.2.9-3",
    "architecture": "x86_64",
    "experimental_patch_sha256": sha256(patch_path),
    "upstream_mode_vtotal_patch_sha256": sha256(mode_vtotal_patch_path),
    "freesync_gmp_prototype_patch_sha256": sha256(freesync_patch_path),
    "freesync_gmp_source_parameter_default": False,
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
    "experimental_display_parameters_present": display_parameters,
    "runtime_parameter_value_checked": False,
    "initramfs_generated": False,
    "initramfs_scope": "Kernel payload and dependency indexes only; target initramfs generation remains pending after authorized installation.",
    "offline_modprobe_dependency_checks": dependency_checks,
    "static_device_aliases": {"uhid": "c10:239", "uinput": "c10:223"},
}
report_path.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
