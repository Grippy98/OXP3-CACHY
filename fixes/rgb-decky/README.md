# HueSync RGB controls for OXP3

Adds the **HueSync** Decky panel for the Intel ONEXPLAYER 3, using the kernel's existing native LED interface. The two joystick rings form one primary zone; the built-in Xbox/guide button and rear logo are separate zones.

**Status: installed and capability-verified; physical lighting response and suspend/resume remain unverified.** The live plugin reports all three zones and 12 modes, and loading it left the LED attributes unchanged. A fresh profile starts with lighting control disabled (`enableControl=false`), so installation alone does not apply colors. An existing HueSync profile can retain its previous preferences; back it up before replacing the plugin.

## Requirements and controls

Use Decky Loader and an OXP3 kernel exposing all three directories under `/sys/class/leds/`. Check the actual nodes rather than relying on a kernel version alone:

| HueSync zone | Native LED | Controls |
| --- | --- | --- |
| Primary | `oxp:rgb:joystick_rings` | Both rings together: solid color, brightness and supported OXP preset effects. |
| Secondary / Xbox Button | `oxp:rgb:guide_button` | Built-in guide-button solid color or off. |
| Tertiary / Slogan Light | `oxp:rgb:rear_logo` | Rear-logo color or off; use **Enable Third Zone** to expose it. |

The native backend requires all three nodes. If they disappear or are unavailable, this prepared build skips OXP3 lighting writes instead of falling back to raw HID. It adds no kernel driver or controller remapping.

## Prepare and install

From the repository root, with Python 3:

```sh
python3 fixes/rgb-decky/prepare.py /absolute/new/HueSync-OXP3.zip
```

Choose a new absolute output path in an existing directory outside this repository. The helper downloads the pinned release, verifies its SHA256, validates the archive, applies the local backend guards and creates a complete private ZIP. It does not install or execute the plugin. To reuse an already downloaded original release archive, add `--archive /absolute/original/huesync-oxp3.zip`; the same checksum is required.

Use Decky's **Install Plugin from ZIP/URL** action to select the prepared ZIP. Before replacing an existing HueSync installation, retain its complete payload and settings backup outside Decky's plugin directory. For manual deployment, stage the entire prepared `HueSync` folder in Decky's configured plugin directory, keep deployed code root-owned and retain the separate settings, then reload **HueSync** through Decky. Reload only this plugin; Steam does not need to restart.

Open **Decky → HueSync**, turn on **Enable RGB Control**, then the **LED** switch when ready to apply lighting. Choose the primary color/effect; use the Xbox Button controls for the guide light and **Enable Third Zone** for the rear logo. Use each zone's enable switch to turn it off. Primary **Disabled** affects the rings; the other zones keep their own switches. Give an effect change time to complete before choosing another.

This build disables the plugin's built-in updater and upstream update prompt so they cannot replace the OXP3 fork. Prepare and review a newly pinned package when intentionally updating. The source pin, archive identity and guards are documented in [WRITEUP.md](WRITEUP.md) and [SOURCE.json](SOURCE.json).

## Check and remove

The installed plugin was reloaded by itself. Its installed/latest version calls both return `3.9.0-oxp3.20261014`, with primary, Xbox Button and Slogan Light zones and 12 reported modes. Fresh settings were absent, and LED readback remained unchanged after loading. No color or effect was applied during these checks.

Verify a modest solid color first, then the guide button, rear logo and one preset independently. Confirm controller input still works. Native LED availability and a successful backend call do not establish the visible result or suspend/resume behavior.

To remove the panel, uninstall **HueSync** in Decky, or restore its complete backed-up payload and settings and reload only that plugin. Removing it does not guarantee restoration of an earlier hardware color. This entry leaves the kernel LED driver, controller integration and other fixes installed. The prepared archive retains the upstream [BSD 3-Clause notices](LICENSE); no plugin binaries or private settings are stored here.
