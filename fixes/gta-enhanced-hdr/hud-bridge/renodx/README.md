# GTA RenoDX HDR HUD composition source

The paired build passed a short Story Mode test on the Intel OXP3 at **1920×1200 HDR**.
The owner reported a normal picture and everything working, including the HUD and
frame generation. Long-play, performance, repeated toggles, mode changes and other
resolutions remain unqualified. Use the [paired profile and rollback guide](../README.md).

This source restores separately registered FFX UI at RenoDX's final HDR conversion
stage. The accepted addon hash is
`cbc474691f69996f3a4d1a922364f86544c0a5deb4ed760892954aa1bb140f2a`, built at
[workflow commit cd41ee6](https://github.com/Grippy98/OXP3-CACHY/commit/cd41ee65845a85e468c56d861ab6c980a06ea49b).
It requires the matching [OptiScaler producer](../optiscaler/README.md).

The patch targets RenoDX commit `bc0ead39917634e95c534f7e8cfb59ab82880747`. It requires the paired OptiScaler immutable UI-packet producer. [source.json](source.json) records pins and limits; [licenses/RenoDX-MIT.txt](licenses/RenoDX-MIT.txt) retains the upstream license. No third-party or game binaries are included.

## Implementation

The COM packet carries versioned copied metadata and owned resource/queue interfaces. Reno resolves its own existing live FP16 clone through its resource helpers; no internal C++ structure crosses the addon boundary. It verifies the observed original BGRA8 UNORM view, native device/queue, dimensions, alpha flags and resource state.

The implementation is deliberately restricted to the observed 1920×1200, FFX flags3,
GammaCorrection1 path. BGRA8/FP16 storage alone does not establish transfer semantics.
Encoded-space premultiplication was the explicit source-based hypothesis tested in
the successful short visual check; detailed colorimetry and other encoding paths
remain unqualified. Unsupported inputs retain the original scene conversion, so
frame generation at another resolution can still lack its separately registered HUD.

A fixed FP16 snapshot per physical backbuffer captures UI on the same immediate queue. This implements the registered UntilPresent/double-buffered lifetime without changing shader descriptors for alternating UI resources. Packet and clone references remain alive until a queue fence retires the copy/draw. Reset cleanup proves GPU completion with a checked native fence before proxy passes are destroyed; stale process-global publication IDs remain rejected across logical resizes. If completion cannot be proved, further composition stops and all affected resource and proxy-pass leases are quarantined until process exit.

The final shader unpremultiplies encoded UI before decoding, blends in linear BT.709, and uses Reno's existing live UI white, gamut conversion, clamp and PQ encoding once. Transparent pixels use the original conversion exactly; opaque UI does not depend on scene values. Composition occurs before the outer ReShade chain forwards Present to XeFG. Thus HUD becomes part of interpolation; per-generated-frame post-interpolation UI composition remains a separate refinement.

Shared helpers gain only optional render inputs and opt-in callbacks. Their object/UUID-backed data layouts and existing default call behavior are preserved. Global CMake presets, workflows and submodules are unchanged.

## Build

The [manual source-build workflow](../../../../.github/workflows/gta-hud-renodx.yml)
checks out the exact upstream commit and pinned submodules with LF line endings.
`build.ps1` validates and applies the patch, uses upstream's Windows Clang x64 Release
preset and builds only `gtav-enhanced` plus its regenerated shaders. The expected
addon is `renodx-gtav-enhanced.addon64`. The workflow never installs or launches it.

For a local Windows build, first prepare a clean checkout at the exact source pin
with recursive submodules and LF line endings, then run the unchanged recipe:

```powershell
./build.ps1 -SourceDir C:/src/renodx -ArtifactDir C:/artifacts/renodx-gta-hud
```

The existing `swap_chain_proxy_pixel_shader.ps_6_0.hlsl` is rebuilt by the upstream shader target with DXC. Its generated CSO/embed header must be new and linked into the addon; no checked-in precompiled Opti UI shader is used. The paired producer and consumer must contain the identical bridge header hash. The clean pinned-source patch check, independent COM/GPU lifetime review,
shader/layout review, 15-test CPU reference suite and Windows shader/addon build
passed. The exact paired build then passed short owner visual acceptance. CI build
records describe build-time status only; they are not hardware-test certificates.

## Repeat checks and remaining limits

- Build the exact addon and verify the generated proxy shader has `t0`, `t1`, existing `b13/space50` injection and the new four-DWORD `b14/space50` constants.
- Confirm a fresh packet and live clone are accepted on the matching game queue, with one process-global publication serial consumed once; new FFX sessions must not reset that serial. Unknown flags, missing clones, stale publications and other sizes must retain the original scene conversion.
- In Story Mode check minimap, map, phone, pause/menu, translucent edges, UI white changes and black/bright HDR backgrounds. Check motion/ghosting with generated frames and actual SDK present status, not only an FPS overlay.
- Check FG-off/null registration, duplicate resize, actual mode changes and process teardown without stale HUD or outstanding resource references. Other GammaCorrection modes, resolutions, output paths and manual addon unload remain unqualified.
- Measure the added full-resolution GPU UI copy and final-pass cost before making performance claims.

The short owner result establishes a limited visual pass for this pair/profile. Source review, CPU math tests and successful compilation do not establish long-play stability, general GPU correctness or performance.

## Pinned-source CI package

The local `build.ps1` validates source, patch, shared-interface and recursive submodule pins. It uses the upstream Clang x64 Release preset for the specific GTA target, regenerates the proxy shader, and records both addon and generated shader-header hashes. `tools.json` pins official DXC, Slang and glslang archives with SHA256 checks. Runner Clang/SDK versions are recorded at build time; future runner images need not produce byte-identical addons. The unmodified source build control passed before this consumer patch was added.

Run `python -m unittest discover -s tests -v` from this folder for the independent luminance/alpha reference checks. These 15 tests include randomized comparisons against absolute-nits composition; they do not replace shader compilation or hardware validation. No new automatic CI trigger is installed by these manual workflows.
