# OXP3-CACHY

Fixes for the **Intel ONEXPLAYER 3 running CachyOS / Deckify**. Each fix has its own README, technical writeup, source and rollback instructions.

## Start here

```sh
git clone https://github.com/Grippy98/OXP3-CACHY.git
cd OXP3-CACHY
./install.sh
```

The terminal menu lets you select one or several fixes, read their instructions, run checks, install, or roll back. It starts without root and requests `sudo` only for system changes. **Nothing installs just by opening it.** Boot promotion, reboots and experimental VRR activation are separate actions.

Prefer individual commands?

```sh
./install.sh list
./install.sh check controllers
./install.sh install controllers
./install.sh docs boot-controller
```

See [installation and rollback](docs/INSTALLATION.md) for prerequisites, arguments and backup locations. Review the selected fix before applying it. The new portable packaging/menu has host tests; it has not itself been deployed to another handheld.

## Fixes

| Fix | What is available | Status |
| --- | --- | --- |
| [Controller buttons and rear paddles](fixes/oxp3-controller/README.md) | PR 13 HID driver, DKMS package, InputPlumber mappings | Driver/profile hardware tested; menu installer available |
| [Controller navigation in Limine](fixes/boot-controller/README.md) | Tested native gamepad patch, pinned EFI build, one-time staging and rollback | Hardware tested; build the EFI image first |
| [Power button](fixes/power-button/README.md) | CachyOS native power-button daemon | Sleep/wake hardware tested; installer available |
| [Intel TDP and MangoHud](fixes/intel-tdp-mangohud/README.md) | RAPL backend, 8–40 W policy, narrow permissions, telemetry patch | Backend/telemetry hardware tested; MangoHud build separate |
| [TV audio](fixes/tv-audio-profile/README.md) | Native HDMI profile and default-sink selection | Audio/reconnect hardware tested; reversible helper available |
| [LG TV EDID recovery](fixes/lg-c5-edid/README.md) | Saved-EDID workaround and kernel recovery patch | Hardware tested workaround/patch; explicit capture required |
| [Built-in panel refresh](fixes/internal-panel-refresh/README.md) | Lua profile, accepted zero-lead runtime and kernel patches | Full setup hardware tested; menu installs the profile only |
| [External HDMI VRR](fixes/external-display-vrr/README.md) | Opt-in Intel PCON / FreeSync prototype and build recipes | Experimental: 1080p SDR worked at 60/80 FPS; 4K VRR unresolved |
| [HDMI-CEC](fixes/hdmi-cec/README.md) | Read-only transport probe and limitations | No usable transport on the tested adapters |
| [Qt login recovery](fixes/cachyos-qt-login-recovery/README.md) | Package-mismatch diagnosis and recovery guide | Historical repair; no automated downgrade |
| [Third-party fix-pack review](fixes/repository-audit/README.md) | Applicability and implementation review | Read-only source analysis |

## Repository layout

- `install.sh`, `fixes.json`, `scripts/`: menu and per-fix dispatcher.
- `fixes/<name>/README.md`: applicability, usage and rollback.
- `fixes/<name>/WRITEUP.md`: implementation, limitations and upstream direction.
- Build recipes, source patches and host tests stay beside their fix.
- [Development checks](docs/DEVELOPMENT.md), [contribution guide](CONTRIBUTING.md), [component licenses](LICENSES.md).

This repository contains source and documentation. Device captures, test-result dumps, backups, signing keys, compiled kernels/EFI images and package archives are excluded. Hardware-tested describes the original fix; it does not establish every mode, dock, kernel or revised installer as tested.
