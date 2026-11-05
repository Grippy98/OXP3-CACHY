# GTA V Enhanced HDR implementation

## Problem and resulting behavior

The tested GTA V Enhanced PC build had no available HDR control and used an SDR Rec.709 swapchain while Gamescope's HDR output was enabled. RenoDX adds game-specific HDR rendering and presentation. The current profile combines the official vkd3d-proton 3.1 Core with the original D3D12 loader, private Mesa 26.3 and the private Gamescope WSI event-queue candidate. It reached Story Mode with fresh XeSS SR initialization and HDR active on two short cold-start tests. Frame generation is off in the working profile.

This supersedes the earlier result of one accepted HDR session followed by repeat startup freezes. It does not establish long-play stability, controlled performance, or that every component of the working combination is necessary. Native FSR frame generation flickered in an owner test; a separate Intel XeFG experiment failed proxy-swapchain teardown.

## RenoDX and the injection chain

The [GTA addon](https://github.com/clshortfuse/renodx/blob/bc0ead39917634e95c534f7e8cfb59ab82880747/src/games/gtav-enhanced/addon.cpp) replaces selected game shaders, upgrades render resources, calls `SetUseHDR10(true)`, ignores Rockstar's temporary `RGSCD3D12_TEMPWINDOW`, and forces borderless presentation. RenoDX's [swapchain implementation](https://github.com/clshortfuse/renodx/blob/bc0ead39917634e95c534f7e8cfb59ab82880747/src/mods/swapchain_v2.hpp) selects `R10G10B10A2_UNORM` with HDR10/ST2084; internal cloned render resources can still use FP16. This adds HDR through a mod, rather than enabling native Rockstar HDR support.

Keep the existing OptiScaler `dxgi.dll`. Its [plugin loader](https://github.com/daniel-h-0/OptiScaler/blob/273e8d449763d0e9e051dee831dc42badcd15d00/OptiScaler/dllmain.cpp#L1204) loads game-root `ReShade64.dll` when `[Plugins] LoadReshade=true`. It sets the loading-check override needed for this non-proxy filename. Full-addon ReShade discovers the game-root `.addon64` file. The original system32 D3D12 loader remains the device-interception point, while only its Core implementation is overridden per game.

The official ReShade full-addon installer's embedded ZIP supplies the 64-bit DLL. No effect packs, global Vulkan layers, kernel changes or prefix replacements are part of this fix. The [RenoDX installation guide](https://github.com/clshortfuse/renodx/wiki/Mods) requires ReShade 6.8.0 or newer with full add-on support.

## Per-game vkd3d Core update

Older vkd3d-proton discarded repeated fence-event registrations for the same fence value and native event handle. Two threads waiting on one auto-reset event could then receive only one wakeup and deadlock. Upstream [49a1e2c](https://github.com/HansKristian-Work/vkd3d-proton/commit/49a1e2c7098f4646374458b9a8fbc7c0d0b5ff3d) removes that suppression, and the official [3.1 release](https://github.com/HansKristian-Work/vkd3d-proton/releases/tag/v3.1) includes it. The old diagnostic appeared in the failing GTA path; that correlation justified a targeted control, but does not prove all GTA freezes have this cause.

The [Core guide](vkd3d/README.md) and [checked installer](vkd3d/install-vkd3d.py) use only the official x64 `d3d12core.dll`, SHA-256 `0dfd690a39ef8361ca3b64e9fd8e945b27d2c568dac5dc0dce1a45abf65914cc`, beside the game executable. The existing system32 `d3d12.dll` loader is retained. The inspected Experimental loader and release 3.1 have no source changes in their loader/private Core interface; this is compatibility evidence for these exact versions, not a promise for arbitrary future pairs.

An earlier diagnostic placing both release DLLs beside the game loaded with HDR inactive because ReShade missed its D3D12 device interception. That was not an HDR success. The Core-only control preserved ReShade device proxying, RenoDX initialization and application HDR feedback. The helper changes no prefix, shared Proton files, registry, Steam options or INI. Its exact original file/symlink/absent-state backup supports checked rollback; the launch command separately merges `d3d12core=n,b` with existing overrides.

## Gamescope WSI and Mesa selection

Disabling Gamescope's WSI layer had avoided an earlier XeSS startup stall, but also removed the demonstrated HDR presentation path. The private Gamescope 3.16.25 candidate gives WSI-owned Wayland globals and swapchains private event queues, dispatches those queues, removes an unnecessary blocking default-queue dispatch during registry setup, and corrects related object retirement/lifetime handling. It adapts upstream fixes to the older vkroots interface. The system compositor/package remain installed. See [BUILDING.md](BUILDING.md), the [builder](build-wsi-layer.py), [patch](patches/0001-private-wayland-event-queues.patch), and [source manifest](WSI-SOURCE.json).

One pre-Core session worked, but identical-profile cold starts later froze. The Core-updated profile works in short tests with this private layer retained. The backport is not established as the cause of the improvement, and stock WSI has not been qualified for this exact working combination. No Wayland queue deadlock was proved from the earlier captures.

The HDR launch profile selects the private layer and unsets `DISABLE_GAMESCOPE_WSI`; a zero value still disables this implicit Vulkan layer. It explicitly selects the runtime package's private Mesa **26.3.0-rc3** using `MESA=26.3`, while the earlier SDR launcher default remains 26.1.2. No system Mesa package is replaced. A changed driver identity can reset GTA's saved upscaling to Off, so validation checked actual XeSS initialization and gameplay rather than accepting a menu, XML value or shader-cache creation as proof.

## Frame generation scope

The working HDR profile sets `[FrameGen] Enabled=false`, `FGInput=nofg`, and `FGOutput=nofg`, with GTA's FG switch off. An FG-off game setting alone does not remove OptiScaler's configured swapchain proxy. The owner reported artifacting/flickering after enabling native FSR FG during an OptiScaler `nofg` control; the game was restored to FG Off.

XeSS FG's [HDR requirements](https://github.com/intel/xess/blob/v3.0.2/doc/xess_fg_developer_guide_english.md#hdr-display-support) require HDR10 and compatible backbuffer, HUD-less and UI textures. RenoDX's final R10/PQ output does not by itself qualify its internal FP16/original SDR auxiliary resources. OptiScaler's manual `DrawUIOverFG` shader performs raw RGB alpha composition without PQ/gamut conversion. The earlier accepted SDR manual-HUD test predates the Core update and is not a validated HDR or post-Core SDR result.

A bounded full-backbuffer Intel XeFG experiment disabled HUD-less/UI auxiliary inputs and manual composition, with SDK UI composition off. It failed when GTA requested a replacement FFX swapchain: the wrapper called XeFG context destruction while an underlying proxy-swapchain reference remained, contrary to the [SDK shutdown contract](https://github.com/intel/xess/blob/v3.0.2/doc/xess_fg_developer_guide_english.md#shutdown). Initial depth/motion-vector flags already matched GTA's later context flags, so pre-setting them is not a supported remedy. This is a source-audited teardown issue; no new OptiScaler patch is runtime-qualified here. The working profile remains HDR plus XeSS SR with FG Off.

## ReShade overlay defaults

ReShade's first-run tutorial uses a separate setting from the game or OptiScaler overlays. The optional quiet configuration sets `[OVERLAY] TutorialProgress=4` and disables extra readouts/messages using the keys read by [ReShade 6.8.0](https://github.com/crosire/reshade/blob/v6.8.0/source/runtime_gui.cpp#L310). No persistent tutorial was reported in the successful short gameplay sessions. The normal brief startup notice may still appear; a frozen frame can keep it visible indefinitely.

## Validation and provenance

The Core-only profile loaded the original system32 D3D12 loader and pinned official app-directory Core. ReShade/RenoDX initialized on D3D12, the swapchain used R10/PQ Rec.2020, Gamescope reported application HDR, and fresh XeSS SR 2.0.2 initialization reached Story Mode. The owner said the profile worked, then reported artifacting/flickering when native FSR FG was enabled. After FG Off was restored, a second cold start returned to Story Mode with a normal gameplay/HUD image. These are short-session results; no long-play, controlled-performance or combined HDR+FG qualification is claimed.

ReShade is official full-addon version **6.8.0**; its extracted DLL reports **6.8.0.2155**. The GTA addon reports **0.2026.1104.1857**. [SOURCE.json](SOURCE.json) records hashes and source references. RenoDX's source and successful snapshot workflow reference commit `bc0ead39917634e95c534f7e8cfb59ab82880747`; hosted modification timing is consistent with that workflow. This associates the observed snapshot with the source/build without claiming a reproducible build or verified binary attestation. The [vkd3d provenance](vkd3d/WRITEUP.md) records its source, release pins and licensing separately.

The private layer is tied to Gamescope 3.16.25 and should be reviewed when updating Gamescope. Rollback restores the recorded Core state and earlier launch profile, INI and pre-existing ReShade/RenoDX files. No game saves or Proton prefix need removal.

## Credits

- **ShortFuse / Carlos Lopez and Musa**: RenoDX's GTA V Enhanced work; RenoDX is MIT-licensed.
- **crosire and ReShade contributors**: ReShade and its add-on API; BSD 3-Clause license.
- **Valve and Gamescope contributors**: Gamescope WSI and upstream queue/lifetime fixes; Gamescope is BSD 2-Clause with additional notices retained in its license.
- **Hans-Kristian Arntzen and vkd3d-proton contributors**: D3D12 translation and the upstream fence-registration fix; LGPL-2.1-or-later, with notices retained in the [vkd3d subfolder](vkd3d/WRITEUP.md).
- **OptiScaler contributors and Daniel's fork**: XeSS/FG translation and the ReShade loading path; GPL-3.0. Its provenance is retained in the [XeSS fix](../xess-xmx-community/SOURCE.json).

Third-party binaries are downloaded from their authors and are not redistributed here.
