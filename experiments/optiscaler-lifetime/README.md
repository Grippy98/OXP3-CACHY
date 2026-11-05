# Experimental XeFG swapchain lifetime diagnostic

This source patch targets OptiScaler fork commit `273e8d449763d0e9e051dee831dc42badcd15d00` from https://github.com/daniel-h-0/OptiScaler. It is experimental and has not been runtime-qualified.

When the final OptiScaler wrapper reference is released, XeFG's SDK context was destroyed before releasing the wrapper's owned proxy reference. Intel requires application references to its returned swapchain interface to be released before destroying the SDK context. The patch releases exactly that owned reference first, for the matching XeFG HWND only, and clears the borrowed release-hook alias before the COM call to prevent recursive teardown. Other FG outputs retain their existing order.

The patch also returns failure from SDK context destruction when the SDK reports failure, preserving the live context, and makes `ReleaseSwapchain` return failure instead of unconditionally discarding that restored context pointer. This does not provide complete recovery: existing callers can ignore the failure and attempt to initialize a still-live SDK context.

Known remaining risk: upstream's late FFX NEW/FOR_HWND paths still force-release an existing wrapper until its reference count reaches zero. Those descriptors do not transfer ownership of an old wrapper; consuming game or ReShade references is unsafe. This narrow diagnostic deliberately does not redesign that ownership. It must not be described as a complete lifetime fix, even if one test passes.

Intel SDK source contract: https://github.com/intel/xess/tree/main/inc/xess_fg and its XeSS-FG developer guide. FidelityFX NEW/FOR_HWND versus WRAP descriptors: https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/v2.4.0/Kits/FidelityFX/framegeneration/include/dx12/ffx_api_framegeneration_dx12.h .

The proposed workflow runs only on the explicit `experimental/gta-xefg-lifetime-20261105` branch or manual dispatch. It checks out the exact source and recursively pinned submodules, applies the SHA-pinned patch, builds Release x64 with Visual Studio, and uploads a DLL plus source provenance. The token is read-only and checkout credentials are not retained. It does not publish a release, commit a DLL, install it, or alter a device. Upstream packaging steps are disabled because only the experimental OptiScaler DLL is needed; bundled third-party runtimes are not replaced.

The build artifact's `build-record.json` records the source, patch, submodule pins, compiler environment, DLL hash, and workflow commit. The generated resource label identifies this experimental patch. Existing OptiScaler licensing and upstream notices remain applicable; the patch and exact public source pins are supplied beside the artifact. Device deployment and rollback require a separate, parent-controlled backup/restore step.
