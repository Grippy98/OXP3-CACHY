# GTA Enhanced: HDR, XeSS and XeFG with the HUD restored

**Short Story Mode testing passed on the Intel OXP3 at 1920×1200.** The owner confirmed a normal picture and that everything works, including frame generation, after the minimap/map/phone check. This is the matched OptiScaler `126edef…` + RenoDX `cbc474…` pair. Long-play, other resolutions and display-mode changes remain unqualified.

The previous HDR/SR setup remains a [separate FG-Off baseline](../README.md#retained-hdrsr-rollback-baseline). This folder preserves the new source patches, build recipes, exact component pins and working profile. [pair.json](pair.json) records the complete matched inputs; [the technical writeup](../WRITEUP.md#paired-renodx-hud-candidate) explains the ownership, native-interface and color-conversion changes. No game files, diagnostic captures or runtime DLLs are committed.

## Scope

The accepted run used GTA V Enhanced build 25971420, Story Mode, the built-in **1920×1200 / 144 Hz** OLED, HDR output and RenoDX **GammaCorrection 1**. The consumer requires the observed full-size BGRA8 UNORM UI, its existing FP16 Reno clone, FFX UI flags 3 and an R10 HDR backbuffer. Another size or unsupported resource contract can retain scene conversion without restoring the HUD. Do not treat this profile as qualified for docked/4K use.

HUD is composited before interpolation. It can therefore develop motion/ghosting artifacts; the short accepted run does not establish every scene or transition. Repeated context creation, actual/zero-size resize requests, manual addon unload and repeated FG toggles still need separate qualification. Added GPU-copy cost has not been benchmarked.

## Required runtime

Retain the existing [community XeSS package](../../xess-xmx-community/README.md), its private **Mesa 26.3.0-rc3**, official Intel XeSS SDK **3.0.2**, **ReShade 6.8.0 full addon**, the [official vkd3d-proton 3.1 Core-only update](../vkd3d/README.md), and the [private HDR WSI layer](../BUILDING.md). Keep the original Proton system32 `d3d12.dll` loader and the original game FidelityFX library. The individual necessity of the private Mesa/WSI combination has not been isolated.

Both modified components are required. A stock RenoDX snapshot or unrelated OptiScaler build does not implement the matching packet contract. Preserve upstream licenses and the source patches with any private binary bundle.

| Component | Exact accepted SHA-256 |
| --- | --- |
| OptiScaler, installed as `dxgi.dll` | `126edef53d8da2962c943a35e6383fa41eb37c2fb79f25a59e95980363c9efde` |
| `renodx-gtav-enhanced.addon64` | `cbc474691f69996f3a4d1a922364f86544c0a5deb4ed760892954aa1bb140f2a` |
| Shared packet header in both source patches | `2ad88daaf8526a15769faa260bd02c4a3ead7e55073cfa3a846062fcdeec0fe7` |

## Build the pair

- [OptiScaler patch and Windows build recipe](optiscaler/README.md): exact base `273e8d449763d0e9e051dee831dc42badcd15d00`, native-interface/owned-chain corrections and immutable UI packet producer.
- [RenoDX patch and Windows build recipe](renodx/README.md): exact base `bc0ead39917634e95c534f7e8cfb59ab82880747`, live-clone snapshot and final HDR UI composition, with independent math tests.
- Manual GitHub Actions workflows: [OptiScaler](../../../.github/workflows/gta-hud-optiscaler.yml), [RenoDX](../../../.github/workflows/gta-hud-renodx.yml). CI builds source and shaders; it does not install anything or establish hardware correctness.

The accepted binaries came from [OptiScaler run 42141184954](https://github.com/Grippy98/OXP3-CACHY/actions/runs/42141184954) and [RenoDX run 42140406948](https://github.com/Grippy98/OXP3-CACHY/actions/runs/42140406948). Actions artifacts expire after 14 days. The source and build recipes here remain available afterwards. A new runner/toolchain can produce a different binary hash; compare its source, shared-header and generated-shader records and qualify that build separately.

## Apply the profile

This is an explicit per-game installation; the menu opens these instructions. Close GTA fully before replacing DLLs or editing INIs. Back up `dxgi.dll`, `renodx-gtav-enhanced.addon64`, `OptiScaler.ini`, `ReShade.ini`, Steam launch options and `settings.xml`, including whether each destination was absent. Preserve saves and the Proton prefix.

1. Start from the working HDR/SR runtime above. Obtain both matching builds and verify their source/header records and accepted hashes. Install OptiScaler as game-root `dxgi.dll` and RenoDX as game-root `renodx-gtav-enhanced.addon64`; retain `ReShade64.dll` and the Core-only `d3d12core.dll`.
2. Merge [profile.ini](profile.ini) into the existing working `OptiScaler.ini` by section/key. It is an overlay, not a complete replacement. Retain Intel identity, native FidelityFX interception and the full path to the private stock `gta-stock-ffx.dll` described in the [XeSS setup](../../xess-xmx-community/README.md#gta-v-enhanced-setup).
3. Keep RenoDX GammaCorrection at **1**. In GTA use **FSR Quality**, **AMD FSR 3 Frame Generator On**, and **Reflex Off**. The FSR controls supply input to OptiScaler; the selected output is XeSS/XeFG. The accepted XML values were `ResScalingType=3`, `FrameGenType=2`; prefer the game's UI over editing a running game's XML.
4. Retain the tested HDR launch environment. The original device wrapper remains the on-device tested route; the newer repository `gta-launch.py --hdr` helper still has unit-test validation only. Do not silently substitute launchers while reproducing this result.

The diagnostic launch used these functional settings around the existing `~/.local/bin/oxp3-gta-xess` wrapper (adjust only the private WSI path to the directory already installed):

```sh
VK_ADD_IMPLICIT_LAYER_PATH="$HOME/.cache/oxp3-hdr-wsi-build/artifacts/event-queues" MESA=26.3 WINEDLLOVERRIDES="dxgi=n,b;d3d12,d3d12core=n,b" "$HOME/.local/bin/oxp3-gta-xess" %command% -nobattleye
```

That wrapper uses the private 20261104 package, retains `FFX_XEFG_MULT=2`, and disables `VK_KHR_present_wait2` as in the working configuration. `DISABLE_GAMESCOPE_WSI` must be absent for this HDR profile. Keep all pre-existing functional wrapper settings. Steam's exact owner-specific launch path is deliberately omitted here.

`DisableUI=true`, `DisableHudless=true`, `DrawUIOverFG=false` and `XeFG.UIComposition=false` remain intentional: Reno handles the UI through the new packet and final HDR pass, avoiding raw SDR SDK input or double composition. The modern overlay and guarded duplicate-resize skip also remain part of this bounded profile.

## Quiet diagnostics

The successful capture used OptiScaler file logging at level 1 plus Proton/IGDEXT traces. These are diagnostic controls, not HDR/FG requirements. Once the game is closed, use the quiet `[Log]` settings in `profile.ini` and omit `PROTON_LOG=1`, `WINEDEBUG=...`, `IGDEXT_TRACE=1` and `PROTON_LOG_DIR=...` from launch options. Preserve the functional environment shown above. Restart normally for the next launch; no running game needs to be interrupted for cleanup.

Use the [ReShade overlay settings](../README.md#quiet-reshade) to suppress persistent tutorial/readouts. Its brief startup notice may remain.

## Roll back

Close GTA. Restore both backed-up DLLs, the INIs, game settings and launch options as one matched configuration. Returning to the known HDR/SR baseline requires its original OptiScaler/RenoDX pair, in-game FG Off and OptiScaler `Enabled=false`, `FGInput=nofg`, `FGOutput=nofg`; turning off only the game toggle does not remove the configured FG swapchain.

The official Core-only update has its own [checked rollback](../vkd3d/README.md#roll-back). Retain it when returning only to the newer HDR/SR baseline; restore its recorded original state when returning to the exact pre-Core baseline. No save deletion, prefix reset or system Mesa replacement is required.
