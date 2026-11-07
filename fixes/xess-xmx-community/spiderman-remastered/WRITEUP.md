# Spider-Man Remastered XeFG: why this implementation

## Problem and result

Spider-Man Remastered exposes native XeSS super resolution and FSR frame generation, but this Linux setup needed a compatibility layer to use Intel XeFG. Nixxes documents [XeSS 1.3 and FSR 3.1 frame-generation support](https://support.nixxes.com/hc/en-us/articles/48468405822739-Version-3-618-0-0-Release-Notes). The accepted profile updates the native XeSS library to SDK 3.0.2 and translates the existing FSR-FG input through official OptiScaler 0.9.4. It preserves Intel identity, the game's own AMD FidelityFX library and its native HDR/UI renderer.

In a short built-in-screen 1920×1200 / 144 Hz test, the owner reported normal menus, colors and gameplay with XeFG configured. Runtime checks showed application HDR, successful XeFG enablement and depth/motion-vector tags, continuous dispatch and presentation callback execution. No numeric presented-frame count or controlled speedup is claimed for this OptiScaler run.

## Rejected direct provider swap

The first per-game trial replaced only FSR frame generation with the community 20261104 XeFG provider, retaining native XeSS SR. It achieved successful SDK status with two presented frames and interpolation enabled, but the owner saw wrong colors and missing menu entries. That result was a functional failure, despite the frame counters.

The [pinned provider source](https://github.com/HHHHanasak1/xess-xmx-linux/blob/20261104/ffxfg/ffx_xefg.cpp) logs the game's presentation callback without invoking it. The game supplied a non-null callback. A missing native UI/HDR presentation pass is therefore the leading explanation for the broken menus/colors; this was not isolated through a callback-only source patch. The provider's HUD-less toggle cannot invoke that callback. Its registered-UI path can also enable UI composition even when `FFX_XEFG_HUDLESS=0`, so that switch is not a complete UI-composition bypass for games that register a UI texture.

The failed trial was closed and its changes rolled back with file-hash checks before the OptiScaler trial. Its provider/AMD-loader files do not remain in the accepted game folder. Its successful two-frame SDK status does not transfer to the later OptiScaler configuration.

## Why official OptiScaler works better here

The [official game compatibility entry](https://github.com/optiscaler/OptiScaler/wiki/Marvels-Spider%E2%80%90Man-Remastered) lists FSR 3.1 FG to XeFG and requires spoofing disabled for reliable ray-tracing startup on AMD/Intel. The exact 0.9.4 [Spider-Man quirk](https://github.com/optiscaler/OptiScaler/blob/7534ad00bf9e590eedb99e8dd9fd8c89dae3654f/OptiScaler/misc/Quirks.h#L289) disables DXGI spoofing. That release does not contain the later fork's Spider-specific HUD-less mismatch quirk; no such correction is claimed here.

The decisive difference is the [FSR input presentation callback](https://github.com/optiscaler/OptiScaler/blob/7534ad00bf9e590eedb99e8dd9fd8c89dae3654f/OptiScaler/inputs/FG/FfxApi_Dx12_FG.cpp#L1370). OptiScaler captures the game's callback and registered UI, constructs a real-frame presentation descriptor and invokes the native renderer before SDK presentation. UI capture for this callback is separate from the SDK's UIColor acceptance gate. Thus `DisableUI=true` can suppress raw auxiliary SDK UI input while still allowing the native game callback to draw the UI.

The accepted configuration uses the complete native HDR backbuffer as the interpolation color input. `DisableUI=true`, `DisableHudless=true`, `DrawUIOverFG=false` and `XeFG.UIComposition=false` avoid a second blend or an unverified transfer/format comparison between auxiliary resources. Native HDR remains the game's responsibility. This differs from GTA's RenoDX clone/COM bridge, which is unnecessary here. HUD can consequently be interpolated with the scene, so fine motion/ghosting still needs broader testing.

Native XeSS SR remains native: `EnableXeSSInputs=false` prevents OptiScaler from replacing the game's XeSS calls. The updated `libxess.dll` uses the existing private Intel shim/Mesa route. FSR-FG interception stays enabled; no DLSSG spoofing or `-forceReflexMarkers` workaround is needed. DXGI, Streamline and DXGI-factory spoofing remain disabled. The modern Opti overlay is selected, and ReShade loading remains off.

The original game `amd_fidelityfx_dx12.dll` stays in the game root. Avoid extracting unrelated modular AMD providers or the OptiScaler archive's alternate D3D12 Core: those would change a separate part of the tested chain. No game saves, prefix registry or shared Proton/system Mesa files are changed by this profile's deployment.

## Validation boundary

Official 0.9.4 does not expose SDK presented-frame counts in the inspected XeFG/wrapped-swapchain path. Successful initialization, `SetEnabled`, tags and dispatch establish the active processing path, not a measured output multiplier. The requested interpolation count is one generated frame per rendered frame; its configured 2× request is not a benchmark. The earlier failed direct-provider trial has separate counters and cannot qualify this configuration.

The accepted result covers a short gameplay/menu/color check with native HDR on the built-in display. Long play, controlled FPS/latency comparisons, detailed motion artifacts, repeated FG toggles, cold-start repetition, resize/docking and other resolutions remain unqualified. A temporary SDK generated-frame debug mark can support visual verification without modifying the official OptiScaler binary. Diagnostic logging cleanup applies on a subsequent launch and should be assessed separately from the original accepted run.

## Reproduction and rollback

[README.md](README.md), [profile.ini](profile.ini), [launch.sh](launch.sh) and [SOURCE.json](SOURCE.json) record the component selection and deployment boundary. The official archive is verified by SHA256; only its selected files plus SDK 3.0.2 are deployed. The backup manifest records original file existence and both original/installed hashes. Rollback closes the game and checks installed hashes before restoring or removing each managed destination; it preserves later game/mod changes for manual review.

Retain the official archive's licenses and Intel's license/third-party notices with the private package. This repository includes documentation and small configuration helpers, not runtime DLLs, game assets or raw device evidence.
