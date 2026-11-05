# GTA V Enhanced HDR implementation

## Problem and resulting behavior

The tested GTA V Enhanced PC build had no available HDR control and used an SDR Rec.709 swapchain while Gamescope's HDR output was enabled. RenoDX adds game-specific HDR rendering and presentation. The current profile combines the official vkd3d-proton 3.1 Core with the original D3D12 loader, private Mesa 26.3 and the private Gamescope WSI event-queue candidate. It reached Story Mode with fresh XeSS SR initialization and HDR active on two short cold-start tests. Frame generation is off in the working profile.

This supersedes the earlier result of one accepted HDR session followed by repeat startup freezes. It does not establish long-play stability, controlled performance, or that every component of the working combination is necessary. Native FSR frame generation flickered in an owner test. Intel XeFG testing exposed separate presentation-chain ownership and native command-list interface problems; the next targeted correction is awaiting hardware validation.

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

The bounded Intel XeFG experiment disables HUD-less/UI auxiliary inputs and manual composition, with SDK UI composition off, so it can isolate presentation and SDK integration before evaluating auxiliary-resource color handling. Its initial depth/motion-vector flags already matched GTA's later flags; changing those flags is not a supported remedy.

GTA requests another FFX swapchain when enabling FG. The original OptiScaler path consumed references and attempted SDK destruction while the application/ReShade still held the SDK presentation chain, contrary to the [SDK shutdown contract](https://github.com/intel/xess/blob/v3.0.2/doc/xess_fg_developer_guide_english.md#shutdown). A GTA-bounded experimental change instead captures an owned reference to the application-visible ReShade chain, checks the requested window, queue and descriptor, and reuses it through a separately owned FFX lease. That adoption succeeded at runtime and retained application HDR, but did not establish working FG.

The next failure was a **CPU access violation in native D3D12 command-list submission**, without a contemporaneous kernel GPU reset. Static analysis of the pinned Core located the failure in `ID3D12CommandQueue::ExecuteCommandLists`: a null or foreign command-list vtable reached a native command-list dereference. The [3.1 command-queue implementation](https://github.com/HansKristian-Work/vkd3d-proton/blob/4522cc1a8b1347f1ab1b0f7b14a23ed9444d95d1/libs/vkd3d/command.c) checks its known command-list vtables; ReShade's [queue wrapper](https://github.com/crosire/reshade/blob/v6.8.0/source/d3d12/d3d12_command_queue.cpp#L178) unwraps its command lists before native submission. In the failed integration, XeFG initialization used ReShade's device proxy while its presentation queue could already be native. Creating proxy command lists and submitting them through a native queue bypasses that required unwrapping boundary.

The pending correction supplies owned, typed native device/queue interfaces to XeFG and OptiScaler's own XeLL context, creates OptiScaler's helper command lists through the native device, and unwraps external command lists only at the SDK resource-tag call. It verifies queue/list device identity and preserves the application-facing ReShade swapchain and global game objects. This is an experimental interface correction, not a replacement HDR install recipe, and runtime validation is pending. Source review and a successful build alone cannot establish generated-frame output or visual correctness.

Native FSR FG has a separate HDR limitation: replacing its presentation chain was followed by loss of application-HDR feedback. Relabeling only the final presenter as PQ would not establish correct FFX transfer-function handling. Keep FG Off in the working profile until the full chain is validated.

The historical SDR manual-HUD result predates Core 3.1 and has not been requalified with the updated HDR runtime. The working profile remains HDR plus XeSS SR with FG Off.

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
