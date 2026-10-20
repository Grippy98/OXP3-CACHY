#!/usr/bin/env python3
"""Stage only Gamescope runtime files, without executing installation scripts."""
from pathlib import Path
import json
import shutil
import struct
import sys

source = Path(sys.argv[1]).resolve()
stage = Path(sys.argv[2]).resolve()
assert not stage.exists(), stage
prefix = stage / "opt/onex3/gamescope"
(prefix / "bin").mkdir(parents=True)
(prefix / "lib").mkdir()
(prefix / "share/gamescope").mkdir(parents=True)
(prefix / "share/vulkan/implicit_layer.d").mkdir(parents=True)
for name in ("gamescope", "gamescopestream", "gamescopereaper", "gamescopectl", "gamescope-type"):
    src = source / "build/src" / name
    data = src.read_bytes()
    assert data[:6] == b"\x7fELF\x02\x01", src
    assert struct.unpack_from("<H", data, 18)[0] == 62, src
    dst = prefix / "bin" / name
    shutil.copyfile(src, dst)
    dst.chmod(0o755)
layer = "libVkLayer_FROG_gamescope_wsi_x86_64.so"
shutil.copyfile(source / "build/layer" / layer, prefix / "lib" / layer)
(prefix / "lib" / layer).chmod(0o755)
manifest = "VkLayer_FROG_gamescope_wsi.x86_64.json"
shutil.copyfile(source / "build/layer" / manifest,
                prefix / "share/vulkan/implicit_layer.d" / manifest)
for name in ("scripts", "looks"):
    shutil.copytree(source / name, prefix / "share/gamescope" / name)
license_root = prefix / "share/licenses/gamescope"
for name, repo in (("gamescope", source), ("wlroots", source / "subprojects/wlroots"),
                   ("libliftoff", source / "subprojects/libliftoff"),
                   ("openvr", source / "subprojects/openvr"),
                   ("reshade", source / "src/reshade"),
                   ("vkroots", source / "subprojects/vkroots"),
                   ("glm", source / "subprojects/glm"),
                   ("stb", source / "subprojects/stb")):
    for license_file in repo.iterdir():
        if license_file.is_file() and license_file.name.lower().startswith(("license", "copying")):
            dest_dir = license_root / name
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(license_file, dest_dir / license_file.name)
assert not any(p.is_symlink() for p in stage.rglob("*"))
assert not any(p.name.startswith("._") for p in stage.rglob("*"))
assert not any(p.name.endswith((".a", ".pc")) for p in stage.rglob("*"))
assert not (prefix / "include").exists()
json_data = json.loads((prefix / "share/vulkan/implicit_layer.d" / manifest).read_text())
assert json_data["layer"]["library_path"] == "/opt/onex3/gamescope/lib/" + layer
print(prefix)
