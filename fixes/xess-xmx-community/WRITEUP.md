# XeSS XMX community integration: scope and validation

## Sources and build identity

This integration wraps [HHHHanasak1/xess-xmx-linux](https://github.com/HHHHanasak1/xess-xmx-linux/tree/627566641c360c7a0e5d529898b2a81daef1c7ab), pinned to `627566641c360c7a0e5d529898b2a81daef1c7ab`. Credit for the community implementation remains with HHHHanasak1 and contributors, including kas5852's Mesa 26.3/Jay work. The shim is based on Intel GameTechDev's MIT-licensed dxvk-igdext; Mesa and the community patches retain their original notices. Compiler/toolchain components have their own licenses. [SOURCE.json](SOURCE.json), [LICENSE](LICENSE) and the helper sources record the inputs; retain the notices when redistributing builds.

The integration built Mesa 26.3.0-rc1 from source on the target Linux device, applying the four community patches. Build-time Python additions were isolated in a private environment: PyYAML `6.0.3`, PLY `3.11`, pyelftools `0.32`, pefile `2024.8.26`. The unchanged community shim source was rebuilt on macOS with LLVM-MinGW `20261006`, static C++ runtime and UCRT; its DLL loaded successfully under the tested Proton Experimental build.

| Recorded input/output | SHA256 |
| --- | --- |
| Mesa 26.3.0-rc1 source archive | `63327d58a51d189c1d1600746c505609bba5c495123b4e51de4e0c038b745542` |
| Private patched ANV build | `2081106041cac6c59e290ba099f9fa5c20cb22cd0728f67a5099186ade0d391a` |
| macOS LLVM-MinGW 20261006 archive | `a7a19b11048e89372637d26279cdb7c430ed3cf8c1e224310421312bf986ebf6` |
| Rebuilt `igdext64.dll` | `92811b8ae72cb5e597dea982260fe057ca672443674cd036da0926f5669cf96f` |

Output hashes identify this integration build; rebuilding from the pinned sources is not a claim of byte-for-byte reproducibility. No binary, trace, capture or device-specific dump is included here.

## Mechanism and compatibility boundary

The shim answers Intel D3D extension queries and records XeSS CM kernels as placeholder D3D12 shaders. Patched ANV recognizes those placeholders, invokes the private Intel compiler, loads the resulting native kernels and reconstructs their resource bindings from vkd3d-proton's descriptor layout. This is a community userspace implementation; it does not add an Intel Windows kernel driver or a Linux display-driver fix.

The Mesa series adds native-kernel injection, optional developer diagnostics, Xe2 large-GRF handling, and a Mesa 26.3 fix selecting the older shader compiler for affected divergent-barrier shaders. The latter is a separate Mesa compatibility change. The descriptor reconstruction requires the classic vkd3d path, so the launcher adds `VK_EXT_descriptor_buffer` to any existing disabled-extension list. It also sets `force_vk_vendor=0` so Mesa's per-game vendor hiding does not prevent the Intel extension path from being selected.

Keep this runtime private and per game. The launcher selects only the child process's 64-bit ANV manifest, preserves other driver selections and 32-bit Intel manifests, and passes the shim directory through `INTC_ALT_DRIVER_EXTENSIONS_PATH`. Galactic Racer reached its main menu under Proton Experimental `experimental-11.0-20261014-x86_64` with the private runtime loaded and the intended environment. Earlier Steam-selected Proton Hotfix `hotfix-20261007-x86_64` trials established loading but did not complete startup during observation. GE-Proton behavior is not covered. Steam's runtime container can relocate manifests, so inspect the final game's environment and mapped libraries rather than relying solely on the launcher's pre-execution printout.

The launcher does not write a system/session environment, replace installed Mesa, patch Proton, or copy a DLL into the game or prefix. Gamescope and unrelated applications retain their existing driver selection. The game's XeSS runtime can create kernel metadata in its prefix and compiled kernels in the user's cache. [README](README.md) gives the manual configuration and rollback; no automatic Steam configuration installer is provided.

## What has been established

STAR WARS: Galactic Racer, AppID `4078430`, contains XeSS `2.0.2.68` and XeFG `1.3.1.78`. Its actual Wine process mapped both private ANV and the rebuilt shim, and retained the intended environment. A fresh community canary was written, and the initial super-resolution trial compiled 30 CM kernels without failures. The Intel compiler disassembled a convolution kernel to 96 DPAS instructions; its native code matched the game-generated CMK cache byte-for-byte. This establishes generated XMX code, rather than a precise frame-rate or execution result.

The game subsequently reached its title, first-run screen and main menu under Proton Experimental `experimental-11.0-20261014-x86_64`. The owner then reported that 4K was difficult to play at roughly 40 FPS, while 1080p felt good and showed roughly 80 FPS. This establishes a positive subjective gameplay result at 1080p; it is not a controlled comparison or an attribution of the reported frames to XMX or XeFG.

The current saved selections are 1920×1080, XeSS Balanced, `Current3PAAUMode=XeSS`, `CurrentFrameGenerationProvider=XeFG`, `XeSSFGMode=On4x` and `bXeLLMode=True`, with game HDR off. The first selection was 2×, but the owner subsequently changed settings. The owner identified the reported counter as Steam/MangoHud's performance overlay. The multiplier active at that time and whether the overlay counted generated frames have not been established; the report therefore does not establish a base rendering rate or a 2×/4× gain. The running process still mapped private ANV and the shim. Fresh `libxess_fg.dll` callers were observed, and 114 kernels compiled successfully with no recorded compilation failure. No recent GPU hang/reset was observed during this check.

Earlier Hotfix trials with normal XMX, private-driver/generic fallback and a stock control had not completed startup during observation; the stock control also showed continuing CPU/shader-cache work. Reaching the menu later under Experimental does not, by itself, isolate the earlier delay to Proton or XMX.

These observations establish loading, compilation, generated matrix ISA and an owner-accepted 1080p gameplay result, not completed XMX dispatch or controlled SR/FG correctness. WaveSize-64 compute-pipeline rejections appeared in both private and stock logs; they can be optional variants and have not been established as the cause. A separate [upstream Galactic Racer report](https://github.com/ValveSoftware/Proton/issues/10228) describes similar startup symptoms on other hardware, without establishing an Intel solution. The canary is written when the driver recognizes a placeholder during pipeline compilation. It does not dispatch a correctness workload. The upstream kernel checker checks static filenames and file sizes, not dynamic-cache execution. The 13 launcher tests establish environment/path/process behavior without executing community code; 11 compiler-helper tests cover hashes, extraction and atomic publication. The saved shim build helper reproduced the installed DLL hash. The compiler helper also unpacked the real pinned DEBs in an isolated offline check. **Completed XMX dispatch, controlled SR/FG correctness and performance comparisons, and HDR remain unverified.**

## Experimental limits

The implementation depends on specific Mesa, vkd3d-proton, XeSS and compiler details. It infers the resource heap, push-constant layout and sampler selection rather than using a public Vulkan ABI for CM injection. Its native-kernel metadata and payload handling are not a general validated kernel-loading interface. A new game library, Proton update or unsupported kernel layout can therefore compile yet produce incorrect output or fail at runtime. Pin the complete tested combination and repeat validation when it changes.

Compilation failure can leave a placeholder in the current launch; generic fallback normally applies on a later launch. A working canary does not guarantee that every kernel compiled or that resource bindings are valid. Keep developer overrides such as self-test bypass, ignored failures, forced feature answers and dispatch modification out of normal launch settings.

Community reports distinguish native XeSS frame generation from adding it through OptiScaler. The latter introduces separate swapchain hooks, with reported HDR crashes in one tested game. Begin with the game's native integration. XeLL uses its cross-vendor application-side pacing; Windows driver timestamp/latency support is not supplied. Additional presented frames are not an equivalent increase in simulation rate or a demonstrated reduction in input latency.

## Hardware validation

1. Keep the accepted display configuration and start in SDR. Hold resolution, scene, quality, power limit, frame cap and Proton version constant; disable dynamic resolution for comparisons.
2. Confirm the final game process maps the private driver and shim. Check the fresh canary and compilation results, then correlate SR/FG library callers with injected kernel hashes and actual dispatches. Target-matching ISA inspection for DPAS strengthens the XMX attribution; compilation alone does not establish it.
3. Test XeSS super resolution with FG off. Compare the private driver with `--fallback` against the same private driver in normal mode, using warm caches. A separate stock-driver baseline is useful, but changing Mesa/Jay at the same time cannot isolate XMX's contribution.
4. Enable native XeSS frame generation at 2×, then higher multipliers individually. Distinguish simulation cadence from presented cadence and inspect moving edges, disocclusion and UI for black, repeated, unstable or corrupted frames. Obtain the owner's visual confirmation.
5. Exercise cold/warm caches and failed-compiler recovery, then test HDR separately. Check game stability and GPU-reset reports, followed by dock/undock and resume. No VRR changes are required by this module.
6. Remove the per-game launcher and confirm the original driver path and game behavior return. Preserve the normal game prefix and Proton installation throughout.

Until those checks complete for a specific game and configuration, describe this as an experimental integration, not a general XMX/XeFG compatibility or performance result.
