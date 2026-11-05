# Community XeSS XMX and frame generation

**Experimental, manual, per game.** This folder selects a private Intel Vulkan runtime for one game's child process. Existing game shortcuts retain their old runtime unless explicitly changed. CachyOS Mesa, Gamescope and unrelated applications keep their existing configuration.

The current GTA setup combines [xess-xmx-linux 20261104](https://github.com/HHHHanasak1/xess-xmx-linux/releases/tag/20261104), Intel XeSS SDK **3.0.2**, and a [GTA-specific OptiScaler build](https://github.com/daniel-h-0/OptiScaler/releases/tag/bc250-273e8d4). It preserves Intel identity and uses the game's original FidelityFX library. The **current HDR/SR route** adds [RenoDX, a per-game vkd3d-proton 3.1 Core and a private Gamescope WSI candidate](../gta-enhanced-hdr/README.md), with `MESA=26.3` selected explicitly; frame generation remains off. The default launcher retains the earlier SDR WSI-off workaround. Both profiles apply only to GTA's child process; Gamescope itself continues running.

## Current results

**HDR plus XeSS SR works in two short Story Mode cold-start tests** using the official vkd3d-proton 3.1 Core, original system32 D3D12 loader, private Mesa 26.3 and the private WSI candidate. **Combined HDR+FG remains unresolved:** native FSR FG flickered and lost application-HDR feedback. Intel XeFG testing progressed past presentation-chain adoption, then exposed a CPU command-list interface mismatch; a native-interface correction is awaiting a hardware test. See the [HDR diagnosis](../gta-enhanced-hdr/WRITEUP.md#frame-generation-scope).

| Game/configuration | Established | Still pending |
| --- | --- | --- |
| GTA HDR + XeSS SR, FG Off | ReShade/RenoDX HDR active, fresh SR 2.0.2 initialization and Story gameplay on two short Core-only 3.1 cold starts. | Long-play, controlled performance, necessity of private WSI/Mesa selection, and stock-WSI comparison. |
| GTA SDR, historical manual UI pass below | Before the Core 3.1 update, owner confirmed minimap, map and phone with `DrawUIOverFG=true`; repeated RenderUI passes and successful SDK depth/velocity/HUDless tags were observed. | Post-Core SDR support (a later control did not reach usable startup), actual presented-frame count, performance/latency and long-play. |
| Galactic Racer, historical 20261018 runtime | Owner-accepted 1080p gameplay; private runtime loaded and matrix code generated. | Controlled SR/FG correctness, actual base/presented FPS split and HDR. |

The earlier no-mod GTA Story Mode configuration remains a separate rollback baseline. Restore the Core's recorded original state when returning to that exact baseline; the old SDR manual-HUD pass is not a post-Core test. [WRITEUP.md](WRITEUP.md) explains implementation and qualification limits; [SOURCE.json](SOURCE.json), [credits](CREDITS.md) and [licenses](licenses/) record provenance. No SDK binaries, game files or diagnostic captures are included here.

## Prepare the private runtime

1. Download `xess-xmx-linux-20261104.zip` from its [release](https://github.com/HHHHanasak1/xess-xmx-linux/releases/tag/20261104). Verify SHA256 **`4d97b77e44f22235a567d0b5317421e65566089dc08a6a0caf9fa16549433173`** before extracting it.
2. Extract into a dedicated user-owned directory, for example `~/.local/lib/oxp3-xess-community/20261104`. Its root must contain `igdext64.dll`, `lib/` and `tools/`. Retain the full release and component notices.
3. Fetch its verified Intel dependencies:

   ```sh
   export PACKAGE="$HOME/.local/lib/oxp3-xess-community/20261104"
   bash "$PACKAGE/tools/get-igc.sh"
   bash "$PACKAGE/tools/get-xess.sh"
   ```

   These fetch IGC 2.10.10/ocloc 25.18 and XeSS SDK 3.0.2: SR **2.0.2.68**, FG **1.3.1.78**, XeLL **1.3.2.10**. They populate this private package without activating it. Keep Intel's license and third-party notices.
4. Stage matching host `libSPIRV-Tools.so` and `libdisplay-info.so.3` into the package's `lib/deps/` so the private driver can find them inside the Steam Linux Runtime. Retain their notices. Check `ldd` on the selected private driver for missing dependencies: `lib/mesa-26.3.0-rc3/libvulkan_intel.so` for the tested HDR route, or `lib/mesa-26.1.2/libvulkan_intel.so` for the historical SDR route. See upstream [container dependency notes](https://github.com/HHHHanasak1/xess-xmx-linux/blob/20261104/docs/debugging.md). A host Vulkan probe alone does not prove container loading.
5. Inspect the selected runtime without starting a game:

   ```sh
   MESA=26.3 python3 launcher.py --package "$PACKAGE" --probe
   MESA=26.3 python3 launcher.py --package "$PACKAGE" --print-env
   ```

A complete package also has `kernels/`, executable `tools/cm-compile.sh`, `tools/cmk_pack.py`, executable `igc/neo/bin/ocloc*` and `igc/igc/local/lib/`. It contains patched Mesa 26.3.0-rc3 and 26.1.2; **the tested HDR/SR profile explicitly selects 26.3 with `MESA=26.3`; the historical SDR FG/HUD recipe uses 26.1**.

Do not run upstream `install.sh` or `enable.sh` for this workflow: they make additional session/Proton/prefix changes. This launcher exposes the private shim directly and writes only a private Vulkan manifest. It accepts root `igdext64.dll` and the historical `shim/igdext64.dll` layout, preferring the root if both exist. Its default remains `20261018` for existing shortcuts; select `20261104` explicitly.

## GTA V Enhanced setup

Close GTA fully before editing files. Back up its current working `settings.xml`, Steam launch options and every destination you change; record which files were originally absent. Keep the original game saves and prefix. This procedure is manual and applies to **Story Mode**.

### Use the pinned GTA-compatible OptiScaler build

Download the DLL and default INI from [daniel-h-0/OptiScaler release bc250-273e8d4](https://github.com/daniel-h-0/OptiScaler/releases/tag/bc250-273e8d4):

| Input | SHA256 |
| --- | --- |
| `OptiScaler.dll` | `044cac6be344a6619e02af9cb0930eed4165ec606dc74486a1d28a573242ec87` |
| `OptiScaler.ini` before editing | `e08ac5e1de899bce37710ffe82f6dfc6e31edfa7febb11a8a9db4ac8dac41e95` |
| Source manifest | `2407174cdc2a462d82736d8ca6cec49b8619ca063f3ced96c4b39525eaa6226b` |

The source pin is `273e8d449763d0e9e051dee831dc42badcd15d00`. This fork adds GTA Social Club auxiliary-factory handling and Streamline initialization locking fixes. The release name refers to another target platform; **this Intel trial retains official Intel XeSS libraries**. It does not install the fork's FreeFG replacement libraries or activate their pacer. Keep the [GPL notice](licenses/OptiScaler-GPL-3.0.txt) and source provenance with the private package.

Place the DLL as **`dxgi.dll`** beside `GTA5_Enhanced.exe`, with the edited `OptiScaler.ini` beside it. Create an `OptiScaler/` support subfolder containing:

- The four matching SDK files from `$PACKAGE/xess/`: `libxess.dll`, `libxess_dx11.dll`, `libxess_fg.dll` and `libxell.dll`, with their licenses.
- A copy of GTA's **original** `amd_fidelityfx_dx12.dll`, named **`gta-stock-ffx.dll`**. Keep the original at the game root too. The tested game-library hash was `12a5081257ec95b0b53ad51b4a87fb3c03f97fe0bbb59f9496968f8d50ef93a6`; a different game update needs its own backup and retest.

Quarantine known older mod copies of XeSS libraries from the game root. The modular AMD D3D12 loader, upscaler and FG providers must be absent from both root and support directories: `amd_fidelityfx_loader_dx12.dll`, `amd_fidelityfx_upscaler_dx12.dll`, `amd_fidelityfx_framegeneration_dx12.dll`. Otherwise OptiScaler can select them ahead of the original combined library. Preserve them in the backup rather than deleting unverified files. Do not copy the old standalone `fakenvapi.dll`; this build integrates that implementation.

### Historical SDR configuration: Intel identity and native FidelityFX

Set these values in the pinned INI. Replace the example Windows `Z:` path with the actual absolute location of your copy; spaces are part of the value:

```ini
[Upscalers]
Dx12Upscaler=xess

[Plugins]
LoadReshade=false

[Inputs]
EnableFfxInputs=true
UseFfxInputs=true
EnableHotSwapping=true
EnableDlssInputs=false
EnableXeSSInputs=false

[Spoofing]
Dxgi=false
StreamlineSpoofing=false
DxgiFactoryWrapping=false

[Libraries]
FfxDx12Path=Z:\home\YOUR_USER\.local\share\Steam\steamapps\common\Grand Theft Auto V Enhanced\OptiScaler\gta-stock-ffx.dll
FfxDx12SRPath=auto
FfxDx12FGPath=auto

[FrameGen]
Enabled=true
FGInput=fsrfg
FGOutput=xefg
DrawUIOverFG=true
DisableUI=false
DisableHudless=auto
UIPremultipliedAlpha=auto

[XeFG]
InterpolationCount=1
UIComposition=false

[Hotfix]
SimulateWaitableObject=false
```

Native-context hot swapping retains the original FidelityFX API contract while XeSS supplies the upscale output. The full-file `FfxDx12Path` override loads the private stock copy; removing standalone providers prevents them from taking precedence for SR/FG queries. The incoming game interface is FSR, and GPU spoofing is disabled so Intel's extension path remains available. `EnableXeSSInputs=false` controls interception of native-game XeSS calls, not the chosen output backend. This is the owner-confirmed **SDR configuration tested before the Core 3.1 update**: OptiScaler draws the cached UI texture over the backbuffer while SDK UI composition stays off. The default alpha setting is unchanged. `LoadReshade=false` disables the ReShade/RenoDX chain retained from an HDR trial; selecting game HDR Off or removing `--hdr` alone does not do that. `InterpolationCount=1` requests **2×**; it does not establish presented-frame output. The separate current HDR/SR profile disables the FG proxy, adds the official Core 3.1 and explicitly selects Mesa 26.3; see its setup below. Leave unsupported-feature and ignored-init-check overrides disabled.

OptiScaler rewrites its INI with whitespace around `=` on exit. Edit keys within the correct section, ignoring case and surrounding whitespace; do not rely on a literal `Enabled=false` string.

### Launch the historical SDR FG/HUD workaround

The hardware observations in this guide used the existing device wrapper; the SDR HUD result predates the Core 3.1 update. The repository's new [gta-launch.sh](gta-launch.sh)/[gta-launch.py](gta-launch.py) helper has **unit-test validation only** and has not yet been launched on the device. Keep it beside [launcher.py](launcher.py); the following is its intended SDR launch option, which needs an on-device environment/library and gameplay check before treating it as equivalent:

```text
"/path/to/OXP3-CACHY/fixes/xess-xmx-community/gta-launch.sh" %command% -nobattleye
```

Select **AMD FSR 3.1 → Quality**, **Frame Generator → AMD FSR 3 → On**, **Reflex Off**, and **HDR Off** in GTA. When returning from the HDR trial, also set `[Plugins] LoadReshade=false` before restarting; RenoDX can select HDR10 independently of the game's HDR setting. These menu labels describe the inputs; OptiScaler supplies XeSS/XeFG output. The owner confirmed that the HUD, map and phone work with the manual RenderUI pass. The earlier configuration without that pass lost those elements.

The default profile sets `DISABLE_GAMESCOPE_WSI=1` only in the game process, leaves Gamescope running and preserves unrelated environment settings. It defaults to private package `20261104` and `MESA=26.1`, merges `dxgi=n,b` with existing Wine overrides, and selects the same Proton Experimental configuration. `OXP3_XESS_PACKAGE=/absolute/path` overrides the runtime; an inherited `MESA` value is preserved. No global environment file is written.

### HDR launch with XeSS SR and FG Off

Complete the [GTA HDR setup](../gta-enhanced-hdr/README.md), including its [Core-only 3.1 installer](../gta-enhanced-hdr/vkd3d/README.md), private WSI build and pinned ReShade/RenoDX files. Preserve the original system32 `d3d12.dll` loader and OptiScaler's game-root `dxgi.dll`. `[Plugins] LoadReshade=true` loads `ReShade64.dll`, which loads `renodx-gtav-enhanced.addon64`. ReShade **6.8.0** is the addon loader; RenoDX is separate. The HDR fix records exact [asset/source pins](../gta-enhanced-hdr/SOURCE.json), including [vkd3d provenance](../gta-enhanced-hdr/vkd3d/source-pins.json).

The repository helper remains **unit-tested only**; the HDR hardware observations used the existing device wrapper. Keep [gta-launch.sh](gta-launch.sh), [gta-launch.py](gta-launch.py) and [launcher.py](launcher.py) together. Its intended HDR launch option explicitly selects Mesa 26.3 and the per-game Core override:

```sh
MESA=26.3 WINEDLLOVERRIDES="d3d12core=n,b" "/path/to/OXP3-CACHY/fixes/xess-xmx-community/gta-launch.sh" --hdr %command% -nobattleye
```

Retain other existing Wine rules in that value. The helper merges `dxgi=n,b` while preserving `d3d12core=n,b`. It does not install the Core or change any INI/game setting.

`--hdr` checks that the private WSI manifest and library exist, removes `DISABLE_GAMESCOPE_WSI` entirely, sets `ENABLE_GAMESCOPE_WSI=1`, and prepends the private directory to `VK_ADD_IMPLICIT_LAYER_PATH`, retaining and deduplicating existing entries. A disable value of `0` still disables an implicit layer; it must be removed. The default private directory is:

```text
~/.local/lib/oxp3-gamescope-wsi/3.16.25-event-queues-20261105
```

`OXP3_GTA_HDR_WSI=/absolute/directory` selects another prepared private layer directory. Presence checks do not verify its contents/provenance. The private event-queue backport is retained in the successful profile, but has not been shown necessary; stock WSI has not been qualified for this exact combination.

Change the historical SDR INI above to `[Plugins] LoadReshade=true`, `[FrameGen] Enabled=false`, `FGInput=nofg`, `FGOutput=nofg`, and turn GTA's Frame Generator Off. Select **AMD FSR 3.1 → Quality** and **Reflex Off** in GTA. The FSR menu label names the input interface; OptiScaler supplies XeSS SR output. RenoDX supplies HDR10 independently of a native Rockstar HDR option.

Both helper modes default to private package 20261104 and `MESA=26.1`; the explicit `MESA=26.3` above selects the tested HDR driver. `OXP3_XESS_PACKAGE=/absolute/path` selects another complete private runtime. Driver/GPU-name changes can reset upscaling to Off; recheck the actual menu and fresh SR initialization/dispatch. Retain `-nobattleye` for Story Mode; it does not add Online support.

The Core-only update preserved ReShade device proxying and HDR feedback, with fresh XeSS SR 2.0.2 initialization and Story gameplay on two short cold starts. Earlier private-WSI-only cold starts were unreliable. Native FSR FG then flickered and lost application-HDR feedback. Intel XeFG presentation-chain reuse succeeded, but a subsequent native command-list interface failure still prevents FG qualification. The current working HDR profile keeps FG Off. No long-play, controlled-performance or combined HDR+FG claim is made.

## Verify and roll back

Before the Core 3.1 update, the existing device wrapper's SDR manual-UI configuration received the owner's short visual confirmation: **HUD, map and phone all work**. Logs show continuous `UI[0..3]` resources, RenderUI buffer/pass activity, XeFG selected, and successful depth/velocity/HUDless SDK tags. No UIColor SDK tags were observed. This establishes the configuration workaround's visual result; the proposed source patch below was not built or deployed.

Current HDR/SR validation is separate: after installing only official vkd3d-proton 3.1 Core and retaining the original loader, the private Mesa 26.3/private-WSI profile reached Story on two short cold starts with fresh XeSS SR initialization and HDR active. Combined FG is unresolved: native FSR FG flickered and lost application-HDR feedback; Intel XeFG chain adoption succeeded but was followed by a CPU command-list submission failure. The targeted native-interface correction remains pending hardware validation; the [HDR writeup](../gta-enhanced-hdr/WRITEUP.md#frame-generation-scope) records the current diagnosis. The earlier SDR manual RenderUI workaround has not been qualified with HDR or the updated Core.

The launcher's environment handling and file checks pass their tests; those tests do not establish device equivalence or game compatibility. Keep the original game configuration backed up. [WRITEUP.md](WRITEUP.md#proposal-only-refresh-xefg-ui-tags) describes the separate unapplied UIColor-tag source proposal; it did not produce the historical SDR workaround or the new HDR/SR result.

For FG qualification, obtain a visual HUD/gameplay check and actual `xefgSwapChainGetLastPresentStatus` frame counts; settings, initialization and an overlay multiplier do not establish 2× output. That API reports frames sent to the presenter. Long-play, performance, latency, higher multipliers and other display modes remain separate checks.

A Mesa selection or reported GPU-identity change can reset GTA's saved SR/FG choices to Off (`ResScalingType=0`, `FrameGenType=0`). A normal-looking menu or HDR feedback does not prove XeSS is active. Recheck the actual graphics menu, reselect the intended settings, and confirm fresh SR evaluation/dispatch activity in the running game; saved XML or shader-cache creation alone is insufficient. This check is especially important when comparing `MESA=26.1` and `26.3`.

Run the launcher/compiler tests without executing native community code:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

The 45 tests cover driver selection, old/new shim layouts, extension merging, WSI-flag/path inspection, scoped SDR/HDR profiles, absent or overridden HDR layer paths, removal of every WSI-disable value, missing-file failure before launch, literal arguments, Wine override merging, HDR preservation, private manifests, compiler hashes and safe extraction. They do not test the GPU. See the [hardware validation plan](WRITEUP.md#hardware-validation).

| Launcher option | Effect |
| --- | --- |
| `--package /absolute/path` | Explicit complete private runtime. |
| `--trace` | Community shim diagnostics. |
| `--fallback` | Generic shim path with the same private driver for comparison. |
| `--off` | Original environment/arguments; does not restore modified game files or a separate global install. |
| `--probe` | `vulkaninfo --summary`; loading/enumeration only. |
| `--print-env` | Whitelisted runtime/HDR/WSI settings without starting a child. |

With GTA closed, restore its saved launch options, settings and backed-up original files; remove only files newly added by this trial. Removing the launcher restores the usual per-game environment; use the [HDR fix rollback](../gta-enhanced-hdr/README.md#roll-back) and [Core installer rollback](../gta-enhanced-hdr/vkd3d/README.md) to restore its separately recorded files. Remove only the new Core override entry from the environment. The exact pre-Core SDR baseline requires restoring the recorded original Core state; the earlier manual-HUD pass does not establish post-Core SDR behavior. Do not delete saves or the Proton prefix. No global service/session changes need undoing.

## Other games and the historical build

Prefer a game's **native XeSS/FG** integration where available. Use the launcher with an explicit package; begin with FG off and SDR, then test 2× and HDR separately. Apply the WSI workaround only to a game that needs it. Upstream's optional direct FSR-to-XeSS providers are a separate experimental route and are not GTA's recommended method here.

`build-mesa.sh`, `build-shim.sh` and `fetch-compiler.py` retain the historical 20261018 source pins; they do not build release 20261104. [WRITEUP.md](WRITEUP.md#historical-20261018-source-build) retains that recipe, Galactic Racer observations and limits. Preserve old packages until their game shortcuts have been retested.
