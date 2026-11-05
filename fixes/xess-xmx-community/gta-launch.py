#!/usr/bin/env python3
"""Select GTA's private XeSS runtime and per-process SDR or HDR WSI profile.

This profile edits no game files, INI, Steam settings, prefixes or services.
The shared launcher creates its usual private Vulkan manifest. It does not
enable SR/FG in the game; those settings require independent validation.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Mapping, Sequence


HDR_WSI_DIRECTORY = ".local/lib/oxp3-gamescope-wsi/3.16.25-event-queues-20261105"
HDR_WSI_FILES = (
    "VkLayer_FROG_gamescope_wsi.x86_64.json",
    "libVkLayer_FROG_gamescope_wsi_x86_64.so",
)


class ProfileError(Exception):
    """A missing private HDR layer; the child has not been started."""


def checked_hdr_wsi(original: Mapping[str, str]) -> Path:
    """Check the already-installed private layer without changing its files."""
    home = Path(original.get("HOME") or str(Path.home()))
    override = original.get("OXP3_GTA_HDR_WSI")
    if override:
        if override == "~":
            directory = home
        elif override.startswith("~/"):
            directory = home / override[2:]
        else:
            directory = Path(override).expanduser()
    else:
        directory = home / HDR_WSI_DIRECTORY
    if not directory.is_absolute():
        raise ProfileError("OXP3_GTA_HDR_WSI must be an absolute directory")
    if any(character in str(directory) for character in (":", "\n", "\r")):
        raise ProfileError("HDR WSI directory cannot contain colons or line breaks")
    for name in HDR_WSI_FILES:
        if not (directory / name).is_file():
            raise ProfileError(f"missing private HDR WSI file: {directory / name}")
    return directory


def prepend_layer_path(directory: Path, original: str) -> str:
    """Prefer the private layer while retaining other implicit layer paths."""
    entries = [str(directory), *(entry for entry in original.split(os.pathsep) if entry)]
    return os.pathsep.join(dict.fromkeys(entries))


def merge_dxgi_override(original: str) -> str:
    """Retain other Wine overrides while replacing conflicting DXGI rules."""
    rules = []
    for rule in original.split(";"):
        if not rule.strip():
            continue
        if "=" not in rule:
            rules.append(rule)
            continue
        names, order = rule.split("=", 1)
        old_names = names.split(",")
        retained = [name for name in old_names
                    if name.strip().lstrip("*").casefold().removesuffix(".dll") != "dxgi"]
        if len(retained) == len(old_names):
            rules.append(rule)
        elif retained:
            rules.append(",".join(retained) + "=" + order)
    rules.append("dxgi=n,b")
    return ";".join(rules)


def profile_environment(original: Mapping[str, str], *, hdr: bool = False) -> dict[str, str]:
    environment = dict(original)
    environment["MESA"] = environment.get("MESA") or "26.1"
    if hdr:
        layer_directory = checked_hdr_wsi(original)
        # Any nonempty disable value, including "0", disables an implicit layer.
        environment.pop("DISABLE_GAMESCOPE_WSI", None)
        environment["ENABLE_GAMESCOPE_WSI"] = "1"
        environment["VK_ADD_IMPLICIT_LAYER_PATH"] = prepend_layer_path(
            layer_directory, environment.get("VK_ADD_IMPLICIT_LAYER_PATH", ""))
    else:
        environment["DISABLE_GAMESCOPE_WSI"] = "1"
    environment["WINEDLLOVERRIDES"] = merge_dxgi_override(environment.get("WINEDLLOVERRIDES", ""))
    return environment


def main(arguments: Sequence[str] | None = None) -> int:
    command = list(sys.argv[1:] if arguments is None else arguments)
    hdr = command[:1] == ["--hdr"]
    if hdr:
        command = command[1:]
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        print("Usage: gta-launch.sh [--hdr] [--] COMMAND [ARGUMENT ...]", file=sys.stderr)
        return 2

    import launcher

    try:
        environment = profile_environment(os.environ, hdr=hdr)
        package = environment.get("OXP3_XESS_PACKAGE") or str(
            Path.home() / ".local/lib/oxp3-xess-community/20261104")
        if hdr:
            os.environ.pop("DISABLE_GAMESCOPE_WSI", None)
        os.environ.update(environment)
        return launcher.main(["--package", package, "--", *command])
    except (ProfileError, launcher.LauncherError) as error:
        print(f"gta-xess: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
