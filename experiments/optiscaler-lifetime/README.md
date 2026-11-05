# GTA Enhanced: experimental XeFG/ReShade ownership canary

This is a source patch and reproducible Windows build recipe against OptiScaler
`273e8d449763d0e9e051dee831dc42badcd15d00`. It is **not runtime-qualified**.
The built DLL is a CI artifact; no third-party runtime DLL is committed here.

## Problem and change

With Intel XeFG already owning the physical chain, GTA later requests an FFX
`FRAMEGENERATIONSWAPCHAIN_FOR_HWND_DX12` context. Upstream releases
`currentWrappedSwapchain` repeatedly and recreates the chain. In this configuration
that object is the **inner native chain created inside Intel's SDK**, while the
game and ReShade retain the outer XeFG proxy. The release loop destroys an object
whose references the FFX request did not transfer. The SDK then reports
`ERROR_POINTER_STILL_IN_USE` during teardown.

This diagnostic applies only to `GTA5_Enhanced.exe`, FSRFG input and XeFG output.
It captures one owned reference to ReShade's actual API-visible outer proxy during
ReShade's constructor `SetPrivateData` bridge. Capture requires the exact SDK
object, ReShade swapchain UUID, pointer size, ReShade caller export, and matching
unwrapped COM identity. It never upgrades a borrowed private-data pointer later.

When GTA asks for a compatible NEW/FOR_HWND chain, the patch transfers that owned
capture into a unique FFX context lease and separately AddRefs the same ReShade
outer for the new caller. No factory creation, caller-reference Release, resize,
or SDK teardown occurs in this adopted path. Compatibility checks cover canonical
command queue identity (including current ReShade and Streamline unwrap bridges),
HWND, client-resolved zero dimensions, API-visible format and all descriptor
fields, and fullscreen mode/timing. ReShade's visible descriptor preserves the
game's original format before RenoDX upgrades the native HDR surface.

Destroying the FFX context removes its registry entry, clears the caller context,
and releases exactly its own outer reference outside the registry lock. It keeps
the Intel SDK context alive. Configure/query/dispatch on an owned lease are
intercepted before configuration-dependent routing; an unsupported descriptor or
stale SDK identity returns an error locally and never reaches native FFX with an
emulated context.

The capture remains owned across buffer-only ResizeBuffers/ResizeBuffers1; it
does not acquire backbuffer references. Adoption revalidates its visible descriptor
and SDK identity after any such resize. Unused captures are released before actual
SDK context destruction/replacement. Failed Intel SDK teardown retains the SDK context and
returns failure. The earlier experiment's incorrect reorder in the inner native
wrapper is **not** included.

The patch also logs the first sixteen enabled XeFG present statuses from the
already-existing SDK query: API result, `framesPresented`, `frameGenResult`, and
`isFrameGenEnabled`. It makes no extra SDK query and changes no debug rendering.

## Limits and runtime canary

This is a bounded ownership diagnostic, not a general swapchain manager. If the
game never makes its late FFX request, the constructor capture may retain the outer
proxy until explicit SDK context teardown/replacement or process exit. After a
capture has been consumed and its FFX lease destroyed, a later adoption request
fails closed unless a new constructor capture exists. Generic repeated toggles,
all exclusive-fullscreen policies, other games, and broader upstream release
loops are not fixed. A request after its owned capture was consumed and destroyed
produces a clean `no constructor-owned ReShade outer reference` rejection.

A useful canary must show all of these together:

1. `GTA captured owned ReShade outer ...` during initial chain construction.
2. The later FFX FOR_HWND request produces `GTA FFX adopted API-visible ReShade
   outer ...; no recreation or caller Release`, without SDK teardown errors.
3. RenoDX remains mapped and the compositor reports HDR active after adoption.
4. XeFG enabled present-status entries report successful interpolation and
   multiple presented frames; the owner verifies picture and HUD remain correct.

A descriptor, extension, queue, or capture rejection leaves the existing chain
intact and reports the reason. Restore the prior hash-verified DLL after a failed
canary. Do not label the game fixed from menu entry alone.

## Build

The workflow reuses the upstream MSVC Release x64 project and exact recursively
pinned submodules. `build.ps1` verifies source and patch pins, disables only the
upstream packaging pre/post commands, generates a unique resource version label,
builds the DLL, and emits its hash, compiler versions and source provenance.
The workflow has read-only repository permission and disables persisted checkout
credentials. Run only on the isolated experiment branch or by manual dispatch.
No installation, game launch, or device change is performed by CI.

## Primary contracts

- [DXGI ResizeBuffers: release backbuffer resource references](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/nf-dxgi-idxgiswapchain-resizebuffers)
- [Exact OptiScaler base](https://github.com/daniel-h-0/OptiScaler/tree/273e8d449763d0e9e051dee831dc42badcd15d00)
- [FFX provider: NEW/FOR_HWND caller reference plus separate context reference](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/v2.4.0/Kits/FidelityFX/framegeneration/fsr3/dx12/ffx_provider_fsr3framegenerationswapchain_dx12.cpp)
- [FFX swapchain create descriptor ownership](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/v2.4.0/Kits/FidelityFX/framegeneration/include/dx12/ffx_api_framegeneration_dx12.h)
- [ReShade 6.8 constructor bridge and reference forwarding](https://github.com/crosire/reshade/blob/v6.8.0/source/dxgi/dxgi_swapchain.cpp)
- [ReShade 6.8 swapchain UUID](https://github.com/crosire/reshade/blob/v6.8.0/source/dxgi/dxgi_swapchain.hpp)

OptiScaler's upstream license is included in the build artifact. These source
changes remain subject to that license; Intel, AMD and ReShade runtime licenses
remain separate. This recipe packages no vendor runtime libraries.
