# Source and release provenance

| Item | Pin |
| --- | --- |
| Upstream project | [HansKristian-Work/vkd3d-proton](https://github.com/HansKristian-Work/vkd3d-proton) |
| Fix | [49a1e2c7098f4646374458b9a8fbc7c0d0b5ff3d](https://github.com/HansKristian-Work/vkd3d-proton/commit/49a1e2c7098f4646374458b9a8fbc7c0d0b5ff3d) |
| Fix merged | 2026-10-27 16:15:49 UTC |
| Official stable release | [v3.1](https://github.com/HansKristian-Work/vkd3d-proton/releases/tag/v3.1), published 2026-10-28 |
| Release source | `4522cc1a8b1347f1ab1b0f7b14a23ed9444d95d1` |
| Earlier Experimental build | `cae2e003bb8251627ff93c0f471ae18a28234490`, committed about three hours before the fix |
| Earlier Proton 11 stable build | `212991fc2c266bc0d59f4c4ce8f80f7126508d71` |

The [upstream patch](upstream/fence-event-registrations.patch) removes the duplicate-event early return. It preserves each completion registration rather than changing Wine's synchronization backend. `PROTON_NO_NTSYNC=1` therefore cannot repair this vkd3d registration bug. There is no supported `no_native_fence_sync` configuration option in the inspected implementation.

Source ancestry confirms the fix is included in v3.1. The downloaded archive matched GitHub's supplied SHA256 digest; separate x64 DLL hashes are recorded in [source-pins.json](source-pins.json). The old duplicate-event warning is absent from the new release Core DLL. These are source and integrity checks, not proof that the GTA symptom is resolved. The initial app-directory pair trial bypassed ReShade D3D12 device interception and had HDR inactive, so it did not qualify an HDR fix. The Core-only method subsequently reached Story Mode twice with RenoDX on D3D12, actual XeSS SR initialization and Gamescope application-HDR feedback. This is short validation; combined FG and long-play remain unqualified.

## Loader and compatibility

[v3.1's D3D12 loader](https://github.com/HansKristian-Work/vkd3d-proton/blob/v3.1/libs/d3d12/main.c) loads `d3d12core.dll` by name and requests its private Core interface, with a system-directory fallback. On Windows/Wine, [the platform implementation](https://github.com/HansKristian-Work/vkd3d-proton/blob/v3.1/libs/vkd3d-common/platform.c) uses ordinary `LoadLibraryA`.

The inspected old Experimental commit and v3.1 have **no source differences** in `libs/d3d12/`, `libs/d3d12core/`, or [`include/vkd3d_core_interface.idl`](https://github.com/HansKristian-Work/vkd3d-proton/blob/v3.1/include/vkd3d_core_interface.idl). This supports retaining the old loader while replacing only its Core with the official fixed release. It is a narrow compatibility statement for these exact pins.

[ReShade 6.8](https://github.com/crosire/reshade/blob/v6.8.0/source/dll_main.cpp) normally registers its D3D12 hooks against the system directory. An app-directory D3D12 replacement can consequently create a device that ReShade has not proxied; [its DXGI code then skips that swapchain](https://github.com/crosire/reshade/blob/v6.8.0/source/dxgi.cpp). Preserving the original loader's location addresses that integration constraint. ReShade's DXGI proxy configuration can broaden hook matching, but changing that chain is unnecessary for the Core-only control.

The official Core imports `CreateDXGIFactory1` from DXGI and Windows system/UCRT libraries; the inspected release has no external MSVC or pthread DLL dependency. The project's documented integration expects DXVK's DXGI implementation.

The existing community XMX path remains separately pinned and scoped. Its [D3D12 shim](https://github.com/HHHHanasak1/xess-xmx-linux/blob/a12948e247dfe43646cdb1409d0f2752633f7883/shim/src/dll/D3D12Api.cpp) uses standard D3D12 calls and includes a patched-driver placeholder self-test. That design supplies no reason to add a new SDK override for vkd3d v3.1. Runtime XMX, frame generation, and HDR still require separate validation.

## Reproduce the artifact

Download [the official archive](https://github.com/HansKristian-Work/vkd3d-proton/releases/download/v3.1/vkd3d-proton-3.1.tar.zst), verify its digest from `source-pins.json`, and extract its `x64/d3d12.dll` and `x64/d3d12core.dll`. No private rebuild or modified release binary was used. To inspect the source, check out the release commit above with its pinned submodules; the fix commit must be its ancestor.

## License and authorship

vkd3d-proton is LGPL-2.1-or-later. The upstream [license](LICENSES/LGPL-2.1-upstream.txt), [notice](LICENSES/UPSTREAM-NOTICE.txt), and [authors file](LICENSES/UPSTREAM-AUTHORS.txt) are retained. The included patch preserves its original upstream authorship and commit metadata. Source and binary downloads remain available from the linked upstream project. This folder does not redistribute the release binaries.
