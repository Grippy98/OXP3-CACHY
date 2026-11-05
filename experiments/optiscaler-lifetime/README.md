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
fields, and fullscreen mode/timing. Only the specific requested IGNORE versus
ReShade-visible UNSPECIFIED alpha pair is normalized: the HWND must be valid,
non-layered and not marked NOREDIRECTIONBITMAP, and the native SDK chain must
report the same HWND with IGNORE or UNSPECIFIED alpha. PREMULTIPLIED, STRAIGHT,
the reverse pair, and all other descriptor mismatches remain rejected. ReShade's
visible descriptor preserves the
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

## Opaque HWND alpha follow-up

The first reuse build captured the correct ReShade outer, passed HWND, queue and
other descriptor checks, and then cleanly rejected GTA's late FOR_HWND request:
requested alpha IGNORE (3) versus ReShade-visible UNSPECIFIED (0). It did not enter
the SDK destroy/recreate path. The game exited after the rejected API request.
That was a safety rejection, not runtime proof of successful adoption.

ReShade 6.8's modified-descriptor GetDesc1 reconstructs from legacy _orig_desc,
which carries no alpha field; it explicitly writes UNSPECIFIED. DXVK 3.1.1's
legacy CreateSwapChain conversion chooses IGNORE. For this actual D3D12 Linux
path, vkd3d-proton 3.1 creates its Vulkan swapchain with OPAQUE composite alpha.
Microsoft also documents UNSPECIFIED and IGNORE as equivalent for its composition
texture alpha setter; this patch does not generalize that to transparent swapchains.
The additional HWND style and native alpha checks keep this correction confined
to the opaque presentation case observed here.

- [ReShade 6.8 GetDesc1 reconstruction](https://github.com/crosire/reshade/blob/v6.8.0/source/dxgi/dxgi_swapchain.cpp)
- [DXVK 3.1.1 legacy swapchain conversion](https://github.com/doitsujin/dxvk/blob/v3.1.1/src/dxgi/dxgi_factory.cpp)
- [vkd3d-proton 3.1 Vulkan opaque composite alpha](https://github.com/HansKristian-Work/vkd3d-proton/blob/v3.1/libs/vkd3d/swapchain.c)
- [Microsoft alpha enum semantics](https://learn.microsoft.com/en-us/windows/win32/api/dxgi1_2/ne-dxgi1_2-dxgi_alpha_mode)
- [Microsoft composition texture alpha normalization](https://learn.microsoft.com/en-us/windows/win32/api/dcomp/nf-dcomp-idcompositiontexture-setalphamode)

## Native Intel D3D12 boundary follow-up

The alpha-adjusted reuse build successfully captured and adopted the actual
ReShade outer. HWND, queue, descriptors and native opaque-alpha validation passed;
there was no swapchain recreation or SDK pointer-in-use teardown failure. Intel
SetEnabled then succeeded. The game subsequently hit a **CPU access violation**
in official vkd3d-proton 3.1's ID3D12CommandQueue::ExecuteCommandLists path, reached
from libxess_fg Present. No GPU reset/hang was recorded in that failure window.
This was a later failure; it does not invalidate the observed adoption success.

The native command queue checks command-list implementation vtables. The fault
corresponds to dereferencing a rejected/foreign list in its query-reset hazard
check. Saved creation metadata also identifies the XeFG initialization device as
ReShade's device proxy, while the factory path can provide a native presenting
queue. Thus a mixed proxy/native D3D12 graph is the targeted compatibility
hypothesis. The exact submitted foreign list was not inspected from live memory,
so this remains an inference supported by the stack and object-creation metadata.

This source follow-up adds a typed, owned COM unwrap helper for **Intel SDK
inputs**, recursively supporting current ReShade and Streamline interfaces with
cycle/depth guards. It does not replace global State objects or unwrap the game's
ReShade outer swapchain. The previous capture/reuse and alpha guards remain.

XeFG initialization owns its native device and initial direct presentation queue
until SDK destruction succeeds. Queue.GetDevice must have the same canonical
native device identity. Reinitializing a live context with a different queue is
rejected; later resource-work queue updates own their own reference without
dropping the original SDK queue lease. XeFG helper allocators, lists, fences and
copy helpers use a separately retained native device; old borrowed-pointer
substitutions are removed. Helper readiness gates context activation and includes
successful creation/Close of every command list.

Game-supplied command-list pointers remain untouched. A temporary owned native
interface is used only during the SDK resource-tag call and must match the SDK
device. The preexisting ignored literal-1 argument for backbuffer/legacy SDK tags
is never queried as a COM object. OptiScaler's own XeLL output contexts also start
with an owned native device, so a previously initialized output reused by XeFG
has a consistent graph. The game's XeLL input objects remain unchanged. For local
XeLL contexts only, the real SDK destruction error now propagates before deleting
the wrapper, making device-reference retention accurate.

Failed SDK destruction retains its context input references. If an owner is
subsequently destroyed with a still-live SDK context, this diagnostic deliberately
retains those references until process exit instead of releasing them underneath
the SDK. It does not implement general recovery from failed SDK destruction.

The helper passed compile-only checks with instantiated device, queue and command
list types against the existing Windows cross-toolchain headers. Full MSVC CI and
a new HDR/XeSS/XeFG runtime canary are still required. A useful canary additionally
shows native-device and validated native-queue boundary logs, successful adoption,
HDR remaining active, successful resource tagging, and SDK present status with
multiple presented frames. No generated-frame or visual success is claimed yet.

- [Intel SDK 3.0.2 native D3D12 object compatibility notes](https://github.com/intel/xess/releases/tag/v3.0.2)
- [ReShade 6.8 device unwrap and proxy allocations](https://github.com/crosire/reshade/blob/v6.8.0/source/d3d12/d3d12_device.cpp)
- [ReShade 6.8 queue unwraps lists before native submission](https://github.com/crosire/reshade/blob/v6.8.0/source/d3d12/d3d12_command_queue.cpp)
- [vkd3d-proton 3.1 native command-list checks and query-reset submission](https://github.com/HansKristian-Work/vkd3d-proton/blob/v3.1/libs/vkd3d/command.c)
