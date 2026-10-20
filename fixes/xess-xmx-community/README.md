# Community XeSS XMX and frame generation

**Experimental, manual, per game.** This folder provides a launcher for the community [xess-xmx-linux project](https://github.com/HHHHanasak1/xess-xmx-linux/tree/627566641c360c7a0e5d529898b2a81daef1c7ab), pinned to `627566641c360c7a0e5d529898b2a81daef1c7ab`. It can expose Intel's XMX path to a compatible D3D12 game's XeSS libraries through a private Mesa ANV driver and `igdext64.dll` shim. XeSS frame generation requires compatible game support and a separate in-game selection.

The community implementation is by HHHHanasak1 and contributors; kas5852 contributed the Mesa 26.3/Jay changes. Its shim derives from Intel's [dxvk-igdext](https://github.com/GameTechDev/dxvk-igdext). See [WRITEUP.md](WRITEUP.md), [SOURCE.json](SOURCE.json), [component credits](CREDITS.md) and [LICENSE](LICENSE) for provenance, implementation limits and licensing.

## Current status

On the Intel OXP3, the source-built private Mesa 26.3.0-rc1 driver and rebuilt shim both loaded in **STAR WARS: Galactic Racer**, Steam AppID `4078430`, under Steam-selected Proton Hotfix `hotfix-20261007-x86_64`. The final Wine process received the intended environment. The game contains XeSS `2.0.2.68` and XeFG `1.3.1.78`; a fresh driver canary and 30 compiled CM kernels were observed without compilation failures. The observed shim callers were from super resolution. A rebuilt convolution kernel matched the game-generated CMK code byte-for-byte and contained 96 DPAS matrix instructions.

**Galactic Racer has not yet completed startup in the trial, so actual kernel dispatch, XMX execution, visual correctness, frame generation and HDR are not verified.** The normal XMX launch, the same private driver with generic fallback, and the stock-driver control all remained at the launch screen during observation. The stock control was still doing CPU/shader-cache work; this does not establish that XMX caused the delay. In-game XeSS and 2× frame-generation selection and the owner's visual test are pending. Loading the driver, recognizing the canary and compiling kernels do not establish those results. No comparative FPS gain is claimed.

## What this changes

The [launcher](launcher.py) selects the private 64-bit Intel Vulkan driver for its child process, retains other drivers and 32-bit Intel manifests, and adds `VK_EXT_descriptor_buffer` to the existing vkd3d extension exclusions. It supplies the compiler helper and shim search path and disables Mesa's Intel-vendor-hiding override for that launch. Existing HDR flags and unrelated environment settings are retained.

The launcher creates a private ICD manifest beneath the runtime directory, or the user's cache directory when no runtime directory is available. It does not replace the system graphics driver, alter Gamescope, install the shim into Proton or a prefix, write Steam settings, or install a session service. XeSS itself can write its normal kernel metadata into the game's prefix and compiled kernels into the user's cache.

Do not run the upstream global installer as part of this workflow. Keep the private package at:

```text
~/.local/lib/oxp3-xess-community/20261018
```

## Build the private package

Use a normal user and a Linux x86-64 build environment compatible with the target CachyOS libraries. The source build requires a C/C++ toolchain, Git, Meson, Ninja and Mesa's ANV dependencies, including LLVM, Clang, libclc, SPIR-V tools/translator, glslang, libdrm, Wayland/X11/XCB, expat, zlib, zstd and libelf development dependencies checked by Meson. Python 3.12+ is required by the pinned runtime helper. The verified compiler fetcher additionally needs `ar` and, when the Python standard library cannot read zstd, the `zstd` command. The integration build used a private Python environment with PyYAML `6.0.3`, PLY `3.11`, pyelftools `0.32` and pefile `2024.8.26`.

The helpers take absolute paths as positional arguments; they do not install a system driver or configure Steam. Use fresh, dedicated build directories whose parents already exist. On Linux:

```sh
export PACKAGE="$HOME/.local/lib/oxp3-xess-community/20261018"
mkdir -p "$HOME/.cache/oxp3-xess-build"
./build-mesa.sh "$HOME/.cache/oxp3-xess-build/mesa" "$PACKAGE"
python3 fetch-compiler.py "$PACKAGE"
```

Build the shim on macOS or Linux with a verified native LLVM-MinGW toolchain:

```sh
./build-shim.sh "/path/to/llvm-mingw-toolchain" "/absolute/new/shim-build" "/absolute/staging-package"
```

Copy the resulting `shim/igdext64.dll` into that same relative location in the Linux runtime package when building on another host. Build helpers refuse existing output binaries; use a new staging package for a rebuild rather than overwriting a running game's runtime.

See [build-mesa.sh](build-mesa.sh), [build-shim.sh](build-shim.sh) and [fetch-compiler.py](fetch-compiler.py) for the pinned inputs, dependency checks and supported host/toolchain requirements. The shim integration build used the macOS LLVM-MinGW `20261006` toolchain, static C++ runtime and UCRT. No release DLL or Vulkan driver binary is stored in this repository. Retain the supplied licenses with any private package or redistributed build.

## Use for one game

Keep the game's existing compatibility selection for the first trial. Galactic Racer used Steam-selected **Proton Hotfix `hotfix-20261007-x86_64`**; a separate shim load test passed under Proton Experimental 11 dated 2026-10-14. GE-Proton has not been validated here; some versions rewrite `INTC_ALT_DRIVER_EXTENSIONS_PATH`. Replace the example checkout path below with the actual absolute path. Preserve any existing game launch settings before editing them.

In Steam's launch options for the selected game:

```text
python3 "/path/to/OXP3-CACHY/fixes/xess-xmx-community/launcher.py" -- %command%
```

Start with in-game **XeSS super resolution**, frame generation off, and SDR. After confirming a correct, stable image, try the game's native XeSS frame generation at 2×, then test higher multipliers and HDR separately. These instructions make no changes to display modes or VRR; keep the accepted display configuration.

| Option | Effect |
| --- | --- |
| `--package /absolute/path` | Use another complete private runtime package. |
| `--trace` | Enable the community shim's diagnostic trace. |
| `--fallback` | Keep the private driver but request the shim's generic fallback, useful for an A/B comparison. |
| `--off` | Pass the original environment and arguments through without checking the package or writing a manifest. |
| `--probe` | Run `vulkaninfo --summary` instead of a game; requires `vulkaninfo`. |
| `--print-env` | Print only the runtime/HDR environment whitelist, without starting a child. |

Place launcher options before `--`, followed by the child command. `--probe` does not accept a child command. Both probe and environment inspection can create the private ICD manifest unless `--off` is selected. Examples:

```sh
python3 launcher.py --probe
python3 launcher.py --print-env
python3 launcher.py --off --probe
```

Existing environment overrides remain effective. In particular, an inherited `IGDEXT_FORCE_FALLBACK` can keep XeSS on its fallback path. `--off` preserves the incoming environment; it does not undo a separate global community installation.

## Verification and rollback

Run the 24 launcher/compiler-helper tests without loading the community driver, DLL or compiler:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

The compiler tests additionally check verified downloads, safe extraction, atomic publication and preservation of an existing bundle. Launcher tests check driver-list precedence and architecture retention, literal paths/arguments, extension merging, HDR preservation, private manifest handling, inspection, probe and passthrough behavior. They do not simulate Proton's runtime container or execute GPU work. Follow the [hardware validation plan](WRITEUP.md#hardware-validation) before treating any game configuration as supported.

To stop using this fix, close the game and remove the launcher from that game's Steam launch options, restoring the saved original text. Leave the game, prefix and Proton files intact. Once no game is using it, the dedicated private package can be removed. Generated caches and private ICD manifests can be retained or removed separately; they do not enable the feature on their own.
