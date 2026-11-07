# Spider-Man Remastered: XeSS Frame Generation on Intel OXP3

**The owner accepted normal menus, colors and gameplay with XeFG configured on the built-in 1920×1200 / 144 Hz screen.** This profile uses official OptiScaler 0.9.4 to translate the game's FSR frame-generation input to Intel XeFG while retaining native XeSS super resolution and native HDR. It is a short compatibility test, not a measured 2× performance result or long-play qualification.

The setup is per game. GTA's patched OptiScaler/RenoDX HUD pair is a separate fix. This folder contains the [profile overlay](profile.ini), [launcher](launch.sh), [log-cleanup helper](quiet-logs.py), [technical writeup](WRITEUP.md) and [exact input pins](SOURCE.json). It contains no game files, runtime DLLs or device captures.

## Requirements and tested setup

- Marvel's Spider-Man Remastered, Steam AppID **1817070**, tested game build **23986256**.
- Intel OXP3, CachyOS Gaming Mode, Proton **11**, built-in **1920×1200 / 144 Hz** display and native HDR enabled.
- [Community XeSS runtime 20261104](../README.md#prepare-the-private-runtime), explicitly selecting its private **Mesa 26.3.0-rc3**. Keep the package private; the system Mesa package remains installed.
- Official [OptiScaler 0.9.4](https://github.com/optiscaler/OptiScaler/releases/tag/v0.9.4), archive `Optiscaler_0.9.4-final.20260718._MM.7z`, SHA256 **`575cb4df866116093df75af607e37fd70e10f5163e0f23fd5c804142e80ef0ad`**.
- Official Intel XeSS SDK **3.0.2**: super resolution **2.0.2.68**, frame generation **1.3.1.78**, XeLL **1.3.2.10**. These replace the older libraries bundled in that OptiScaler archive for this profile.

The game uses its original `amd_fidelityfx_dx12.dll`, SHA256 `12a5081257ec95b0b53ad51b4a87fb3c03f97fe0bbb59f9496968f8d50ef93a6`. Recheck that pin after a game update. This setup uses neither modular AMD provider replacements nor ReShade/RenoDX, and it adds no alternate D3D12 Core.

## Manual setup

Close Spider-Man completely before replacing files or editing its INI. Record the existing Steam launch options and back up every destination, including whether it was absent. Keep the saves and Proton prefix.

1. Prepare the pinned private runtime and Intel SDK using the [parent guide](../README.md#prepare-the-private-runtime). Verify the OptiScaler archive before extracting it. Preserve its component licenses and Intel's license/third-party notices beside the private package.
2. Place the following files **beside `Spider-Man.exe` in the game root**:

   | Destination | Source |
   | --- | --- |
   | `dxgi.dll` | Official 0.9.4 `OptiScaler.dll`, renamed |
   | `OptiScaler.ini` | Official 0.9.4 INI, with this profile merged by section/key |
   | `fakenvapi.dll`, `fakenvapi.ini` | Matching files from that same official archive |
   | `libxess.dll`, `libxess_fg.dll`, `libxell.dll` | Intel SDK 3.0.2 from the private package |

   The accepted OptiScaler DLL SHA256 is `fbfb6676b829dad7e020fb830586a16aa0ec6add78016db48ef12e2ae1803231`; `fakenvapi.dll` is `373e73dc06e2d66e90083fde3bc99ef5c1ed0bef98d1f7eda56c8b073269c3f1`. Keep the original game AMD DLL unchanged. Do not unpack the archive's modular AMD providers, `D3D12_Optiscaler` Core, or unrelated injection files over this setup.
3. Merge [profile.ini](profile.ini) into the full official INI. Keep GPU identity/spoofing disabled, native XeSS input interception disabled, FSR-FG input and XeFG output selected, and both auxiliary UI/HUD-less SDK inputs disabled. OptiScaler invokes the game's own presentation callback to restore its native HDR/UI pass; a second manual UI blend is unnecessary.
4. Keep the game's native **XeSS** upscaling choice, enable **FSR Frame Generation**, and keep **DLSS Frame Generation Off** and **Reflex Off**. FSR is the input menu label; OptiScaler selects Intel XeFG as the output. Use borderless/windowed fullscreen rather than exclusive fullscreen, retain native HDR, and leave the existing XeSS quality setting unchanged initially.
5. Use the [launch helper](launch.sh) with the existing private community launcher. The installed device entry point is `~/.local/bin/oxp3-spiderman-xefg`, which executes `~/.local/lib/oxp3-spiderman-xefg/launch.sh`. Its per-game Steam launch option is:

   ```sh
   WINEDLLOVERRIDES="dxgi=n,b" "$HOME/.local/bin/oxp3-spiderman-xefg" %command%
   ```

   Retain any pre-existing overrides needed by your own installation. The helper selects the 20261104 private package, Mesa 26.3 and the 2× request. It expects the existing private launcher at `~/.local/lib/oxp3-xess-community/20261104/launcher.py`; when preparing another system, copy the parent [launcher.py](../launcher.py) there if needed. For another Steam-library location, set `OXP3_SPIDER_GAME` to the absolute game directory so log cleanup uses the correct INI. This is a manual profile, not an automatic installer.

From the repository root, the helper files can be placed as follows after backing up any pre-existing destinations:

```sh
profile="$HOME/.local/lib/oxp3-spiderman-xefg"
install -Dm755 fixes/xess-xmx-community/spiderman-remastered/launch.sh "$profile/launch.sh"
install -Dm644 fixes/xess-xmx-community/spiderman-remastered/quiet-logs.py "$profile/quiet-logs.py"
install -Dm644 fixes/xess-xmx-community/spiderman-remastered/profile.ini "$profile/profile.ini"
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/oxp3-spiderman-xefg" <<'SH'
#!/bin/sh
exec sh "$HOME/.local/lib/oxp3-spiderman-xefg/launch.sh" "$@"
SH
chmod 755 "$HOME/.local/bin/oxp3-spiderman-xefg"
```

The reference `profile.ini` in that private directory does not replace the game INI automatically; merge it in step 3. The helper selects the runtime and quiet logging only. Retain the official component/Intel license notices with the private setup.

The accepted run used diagnostic logging. The launcher applies quiet OptiScaler log settings before the **next launch**; `OXP3_SPIDER_DEBUG=1` opts out of that cleanup for troubleshooting. This changes logging, not the selected SR/FG/HDR path. The deployed helper passed a child-environment probe, and log cleanup was checked for log-only edits and idempotence. The accepted running game was uninterrupted; a subsequent full gameplay launch with cleanup remains a separate check.

## Verify

The accepted run retained Gamescope application HDR, successful XeFG enablement, successful depth/motion-vector tagging, continuous FG dispatch and the game's presentation callbacks. The owner reported normal menus, colors and gameplay.

Those observations support a working configured XeFG path and its image/UI compatibility. Official OptiScaler 0.9.4 does not log `xefgSwapChainGetLastPresentStatus` counts in this path, so they do **not** establish a measured 2× output rate, base/presented FPS split or performance gain. If further verification is required, temporarily use `[XeFG] DebugView=true` to mark generated frames, then restore it to false. Longer play, fast swinging, combat, subtitles, repeated toggles, resize/docking and other output modes remain separate checks.

## Roll back

Close the game. On the configured device, `~/.local/state/onex3-fixes/spiderman-remastered/current-optiscaler-backup.txt` points to its backup directory. `manifest.json` records each target, original existence, backup file, original hash and installed hash.

For each managed destination, compare the current file hash to the recorded installed hash first. Restore the saved original only when the current file still matches; remove a newly added file only when the manifest records that it was originally absent and the installed hash still matches. If a game update or another mod changed it, preserve that file and reconcile the change manually. Do not run a broad deletion or overwrite newer files blindly.

Restore the recorded Steam launch options and game settings if you changed them. In the accepted installation only `libxess.dll` replaced an existing managed game file; the other mod destinations were originally absent, and the original AMD DLL remained unchanged. Keep saves, the Proton prefix and system Mesa. The private helper/package can remain unused after its launch option is removed.

## Credits and licensing

[OptiScaler contributors](https://github.com/optiscaler/OptiScaler) provide the GPL-3.0 interception layer; the [retained license](../licenses/OptiScaler-GPL-3.0.txt) and official archive notices apply. Fakenvapi retains its own bundled notice. Intel provides the separately licensed XeSS SDK. The [community shim/private Mesa integration](../CREDITS.md) retains its own notices. Nixxes/Insomniac provide the game and native HDR/UI implementation. No third-party runtime binaries are redistributed here.
