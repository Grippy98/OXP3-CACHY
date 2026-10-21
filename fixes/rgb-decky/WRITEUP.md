# HueSync OXP3 integration and validation

## Pinned implementation

This entry packages [HHHHanasak1's OXP3 HueSync fork](https://github.com/HHHHanasak1/HueSync/tree/e05aa394f8e3a339b0f6e0c54e0ed23b955e7e84), release **20261014**, commit `e05aa394f8e3a339b0f6e0c54e0ed23b955e7e84`. It derives from [honjow/HueSync](https://github.com/honjow/HueSync), based on upstream 3.9.0. Credit remains with honjow, Steam Deck Homebrew and the fork contributors; the original BSD 3-Clause notices remain in the prepared artifact and [LICENSE](LICENSE).

The input is the complete [huesync-oxp3.zip release asset](https://github.com/HHHHanasak1/HueSync/releases/download/20261014/huesync-oxp3.zip), SHA256 `6164fa7bea9e605f9689b6977a13b5b5904b49780bc269b821054e98bd7481d5`. [SOURCE.json](SOURCE.json) records provenance. The release archive includes the frontend, backend and dependencies; copying only a locally built frontend is not equivalent.

The fork recognizes the current `ONE-NETBOOK` / `ONEXPLAYER 3` device and defines three zones. Its native backend writes `oxp:rgb:joystick_rings`, `oxp:rgb:guide_button` and `oxp:rgb:rear_logo` under the kernel LED class. The kernel remains responsible for controller communication. Recognition by DMI alone does not prove those nodes exist or that an LED command produced the intended color.

## Local guards and preparation

[prepare.py](prepare.py) fetches or accepts the original pinned archive, checks the exact SHA256, validates extraction paths and prepares a new complete ZIP outside this repository. It applies two narrowly scoped backend guards:

1. For the OXP3/X2-class path, missing native LED nodes stop the operation rather than entering the fork's older raw-HID fallback. This keeps RGB requests on the kernel interface alongside the existing controller integration.
2. `update_latest` returns false, and `get_latest_version` reports the installed version. The upstream updater would otherwise replace this OXP3 build with an unreviewed upstream package lacking the same support/guards.

The preparation helper retains the archive's original license and bundled components. It neither executes downloaded code nor writes to the device. Generated ZIPs, plugin binaries, logs and settings belong outside this source folder. The [README](README.md) provides the preparation and plugin-only deployment steps.

## Zone behavior

The primary zone drives both rings together. Solid color uses the color's brightness and the driver's monocolor effect. OXP presets map to named native effects such as `aurora`, `neon` and `warm_sun`; preset brightness levels map to 25, 60 and 100. The backend orders brightness before the preset effect because a brightness write can schedule a return to monocolor in the driver. Effect selection can wait for a controller acknowledgement, so rapid repeated changes are not a useful correctness test.

The secondary Xbox/guide-button zone and tertiary rear-logo zone support solid color or off. The tertiary controls use **Enable Third Zone**. Primary **Disabled** turns off the rings while secondary/tertiary switches remain independent. The fork does not provide independent left/right-ring controls through this primary zone.

A fresh frontend profile has `enableControl=false`; installing or opening it does not automatically apply colors. Existing settings can retain a different control preference. Turn on **Enable RGB Control**, then the **LED** switch deliberately for a visible test; use **Enable Third Zone** for the rear logo. Preserve the separate Decky settings when backing up/restoring an existing installation. This plugin's metadata requests Decky's root capability for native sysfs LED writes; the integration does not broaden the kernel's LED permissions.

## Validation boundary and upstream direction

The pinned archive passed preparation and verification, and the complete guarded payload was installed. Only **HueSync** was reloaded through Decky; Steam was not restarted. Its real installed/latest version callables both returned `3.9.0-oxp3.20261014`. Device capabilities reported primary, secondary Xbox Button and tertiary Slogan Light zones. Mode capabilities reported Disabled, Solid, nine OXP presets and Classic: 12 modes with the three zones available.

Fresh backend settings were absent (`get_settings` returned null), and the native LED attributes matched their pre-load values afterward. No colors/effects were applied during these capability checks. This verifies loading, device recognition, the update guard's reported version and the three-zone API; physical colors/effects, controller coexistence during lighting writes and suspend/resume remain unverified. A source-level mode list, native LED directories or a successful callable cannot substitute for viewing each physical zone. No independent ring-control, resume-restoration or visible lighting result is claimed.

The kernel-native path is the preferred boundary for RGB controls. Keep the local no-HID fallback and update guards when rebasing the OXP3 plugin, and validate on the actual kernel/firmware rather than assuming every similarly named OneXPlayer uses this layout. Rollback restores/removes only the plugin and its settings; it does not remove the kernel LED driver or promise a previous hardware color will be restored.
