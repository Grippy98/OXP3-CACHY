# GTA V Enhanced HDR

**HDR with XeSS upscaling works in short Story Mode tests; keep frame generation off.** The current profile reached gameplay on two cold starts using the official vkd3d-proton 3.1 Core, private Mesa 26.3 and the private Gamescope WSI candidate. Experimental Intel XeFG now generates frames with stable, normal-color output in a short controlled test, but its HUD is still broken. Combined HDR/FG remains unqualified.

RenoDX adds HDR to the tested PC build; this does not enable a native Rockstar HDR option. The private WSI backport remains a candidate: its necessity has not been isolated, and this profile has not yet been compared successfully with the stock WSI layer.

## Requirements

- GTA V Enhanced, Steam AppID `3240220`, Story Mode.
- Gamescope HDR output enabled on an HDR-capable display.
- The [XeSS community setup](../xess-xmx-community/README.md), including its updated GTA launcher with `--hdr` support, and its private Mesa 26.3 driver. The tested package provides **26.3.0-rc3**; select it explicitly with `MESA=26.3`.
- The official **vkd3d-proton 3.1 x64 Core only**, installed with the [per-game guide and checked installer](vkd3d/README.md). Preserve the original system32 `d3d12.dll` loader so ReShade keeps intercepting D3D12 device creation.
- The private Gamescope 3.16.25 WSI build prepared with the [build guide](BUILDING.md).
- [ReShade 6.8.0 with full add-on support](https://reshade.me/downloads/ReShade_Setup_6.8.0_Addon.exe), plus the [GTA V Enhanced RenoDX addon](https://clshortfuse.github.io/renodx/renodx-gtav-enhanced.addon64).

The repository contains source, instructions and provenance, not third-party binaries. [SOURCE.json](SOURCE.json) records exact versions and SHA-256 hashes. The RenoDX snapshot URL changes over time; a different hash requires a new review.

## Reproduce the tested HDR/SR profile

Close GTA completely. Back up its Steam launch options, `OptiScaler.ini`, `settings.xml`, and any existing ReShade/RenoDX files before changing them.

1. Follow [BUILDING.md](BUILDING.md) and run the [private layer builder](build-wsi-layer.py) as your normal Linux user. Its default output is `~/.local/lib/oxp3-gamescope-wsi/3.16.25-event-queues-20261105`. This is a per-game layer; keep the system Gamescope package installed.
2. Follow the [vkd3d Core guide](vkd3d/README.md). Run `python3 vkd3d/install-vkd3d.py install --game-dir "/path/to/Grand Theft Auto V Enhanced"` from this fix's folder. The checked installer downloads the pinned official release and changes only app-directory `d3d12core.dll`; it retains the original file/symlink/absent state for rollback. It does not edit Proton, the prefix, Steam options or DLL overrides.
3. Download the official full-addon ReShade installer. Extract only its **64-bit `ReShade64.dll`** from the installer's embedded ZIP; do not replace OptiScaler's `dxgi.dll` or the original D3D12 loader.
4. Place `ReShade64.dll` and `renodx-gtav-enhanced.addon64` beside `GTA5_Enhanced.exe`.
5. Set these values in `OptiScaler.ini`:

   ```ini
   [Plugins]
   LoadReshade=true

   [FrameGen]
   Enabled=false
   FGInput=nofg
   FGOutput=nofg
   ```

6. Keep GTA's **Frame Generator Off**, **FSR Quality** for the XeSS input, and **Reflex Off**. A driver identity change can reset upscaling to Off; recheck the actual game setting after switching Mesa.
7. Use the updated GTA helper in Steam's launch options:

   ```sh
   MESA=26.3 WINEDLLOVERRIDES="d3d12core=n,b" "/path/to/OXP3-CACHY/fixes/xess-xmx-community/gta-launch.sh" --hdr %command% -nobattleye
   ```

   If you already have other DLL overrides, retain them in `WINEDLLOVERRIDES` and add the Core entry. The helper merges its DXGI override while preserving this entry.

`--hdr` selects the private WSI layer and completely removes `DISABLE_GAMESCOPE_WSI` from the game environment. Without `--hdr`, the GTA helper keeps the earlier WSI-disabled startup workaround. Setting the disable variable to `0` is insufficient for an implicit Vulkan layer; it must be unset.

Setting only the game's Frame Generator Off does not remove OptiScaler's configured FG swapchain. Both `FGInput=nofg` and `FGOutput=nofg` are intentional. RenoDX's GTA addon selects **HDR10** itself; leave OptiScaler's `[HDR] ForceHDR` at its default. Open ReShade with **Home** to access RenoDX settings and calibrate brightness for the display in use.

## Quiet ReShade

With GTA closed, set these values in game-root `ReShade.ini`, then restart. They skip the first-run tutorial and disable extra overlay readouts/messages. The brief startup notice may still appear.

```ini
[OVERLAY]
TutorialProgress=4
ShowFPS=0
ShowClock=0
ShowFrameTime=0
ShowPresetName=0
ShowScreenshotMessage=0
ShowPresetTransitionMessage=0
```

## Validation and limits

The Core-only profile retained the original system32 D3D12 loader and loaded the official 3.1 app-directory Core. ReShade/RenoDX initialized on D3D12, Gamescope reported application HDR, and fresh XeSS SR 2.0.2 initialization plus Story Mode gameplay were observed. The owner reported that it worked; a second cold start returned to Story Mode after frame generation was restored to Off. This is short-session HDR/SR validation, with no long-play or controlled-performance claim.

**Combined HDR and frame generation remains unresolved.** Native FSR FG flickered and lost application-HDR feedback. The experimental Intel XeFG correction briefly reported successful interpolation with two frames sent to the presenter, followed by owner-reported oversaturation and an OptiScaler legacy-menu crash. Failed duplicate resizes also left RenoDX tracking unregistered, providing a concrete color-corruption lead without identifying who held the backbuffer references. A narrowly scoped resize/menu retry reached stable, normal-color Story Mode with generated frames, but HUD elements were broken until the owner disabled FG. See the [implementation diagnosis and test limits](WRITEUP.md#frame-generation-scope). None of these experiments changes the FG-off installation recipe.

The accepted SDR manual-HUD workaround predates this Core update and is not qualified for HDR. A final HDR10 backbuffer alone does not establish compatible HUD-less/UI inputs.

The earlier private-WSI-only session did not reproduce reliably before the Core update. The upstream fence-registration fix is a stronger lead for those freezes, but the current working combination does not prove the WSI backport or Mesa selection is individually necessary. The private WSI build targets Gamescope 3.16.25; review it when updating that component.

## Roll back

Close GTA and run `python3 vkd3d/install-vkd3d.py rollback --game-dir "/path/to/Grand Theft Auto V Enhanced"` to restore the Core's recorded original state. The installer refuses to overwrite a subsequently modified Core. Remove only this fix's `d3d12core=n,b` override entry, retaining other entries.

Remove `--hdr` and the explicit `MESA=26.3` selection from the GTA launch options, or restore the exact saved launch options. Set `[Plugins] LoadReshade=false` to disable this ReShade loading path. Restore the saved INI if you need the previous SDR profile; post-Core SDR qualification is separate from the earlier manual-HUD test.

Remove only the ReShade/RenoDX files newly added by this fix; restore backups if they already existed. The private WSI directory can remain unused or be removed after GTA closes. Do not remove saves or the Proton prefix. See [WRITEUP.md](WRITEUP.md) for implementation and credits.
