# Community XeSS XMX and frame generation

**Experimental, manual, per game.** This folder provides a launcher for the community [xess-xmx-linux project](https://github.com/HHHHanasak1/xess-xmx-linux/tree/627566641c360c7a0e5d529898b2a81daef1c7ab), pinned to `627566641c360c7a0e5d529898b2a81daef1c7ab`. It can expose Intel's XMX path to a compatible D3D12 game's XeSS libraries through a private Mesa ANV driver and `igdext64.dll` shim. XeSS frame generation requires compatible game support and a separate in-game selection.

The community implementation is by HHHHanasak1 and contributors; kas5852 contributed the Mesa 26.3/Jay changes. Its shim derives from Intel's [dxvk-igdext](https://github.com/GameTechDev/dxvk-igdext). See [WRITEUP.md](WRITEUP.md), [SOURCE.json](SOURCE.json), [component credits](CREDITS.md) and [LICENSE](LICENSE) for provenance, implementation limits and licensing.

## Current status

On the Intel OXP3, **STAR WARS: Galactic Racer**, Steam AppID `4078430`, reached its title, first-run screen and main menu with the private Mesa 26.3.0-rc1 driver and rebuilt shim under **Proton Experimental `experimental-11.0-20261014-x86_64`**. The actual Wine process mapped the private runtime and received the intended environment. The game contains XeSS `2.0.2.68` and XeFG `1.3.1.78`. The initial super-resolution trial compiled 30 CM kernels without failures; a rebuilt convolution kernel matched the game-generated CMK code byte-for-byte and contained 96 DPAS matrix instructions.

The owner subsequently reported that **1080p feels good and shows roughly 80 FPS**, while 4K was difficult to play at roughly 40 FPS. The reported counter was Steam/MangoHud's performance overlay. The current saved configuration is **1920×1080, XeSS Balanced, native XeFG 4× and XeLL enabled, with game HDR off**. The initial selection was 2×; the multiplier active during the owner's report and whether the overlay counted generated frames have not been established, so those figures do not identify the base rendering rate or a frame-generation gain.

The running game mapped both private components, fresh `libxess_fg.dll` callers were observed, and 114 kernels compiled successfully with no recorded compilation failure. No recent GPU hang/reset was observed during this check. **Completed XMX dispatch, controlled SR/FG correctness and performance comparisons, and HDR remain unverified.** A canary, compiled kernels and saved settings do not establish those results. Earlier Proton Hotfix `hotfix-20261007-x86_64` startup trials, including generic-fallback and stock-driver controls, did not reach the game during observation; the cause was not established.

## What this changes

The [launcher](launcher.py) selects the private 64-bit Intel Vulkan driver for its child process, retains other drivers and 32-bit Intel manifests, and adds `VK_EXT_descriptor_buffer` to the existing vkd3d extension exclusions. It supplies the compiler helper and shim search path and disables Mesa's Intel-vendor-hiding override for that launch. Existing HDR flags and unrelated environment settings are retained.

The launcher creates a private ICD manifest beneath the runtime directory, or the user's cache directory when no runtime directory is available. It does not replace the system graphics driver, alter Gamescope, install the shim into Proton or a prefix, write Steam settings, or install a session service. XeSS itself can write its normal kernel metadata into the game's prefix and compiled kernels into the user's cache.

Do not run the upstream global installer as part of this workflow. Keep the private package at:

```text
~/.local/lib/oxp3-xess-community/20261018
```

## Build the private package

Use a normal user and a Linux x86-64 build environment compatible with the target CachyOS libraries. The source build requires a C/C++ toolchain, Git, Meson, Ninja and Mesa's ANV dependencies, including LLVM, Clang, libclc, SPIR-V tools/translator, glslang, libdrm, Wayland/X11/XCB, expat, zlib, zstd and libelf development dependencies checked by Meson. Python 3.12+ is required by the pinned runtime helper; the Mesa helper checks for Mako, packaging, PyYAML and PLY. The shim additionally needs CMake and the verified LLVM-MinGW toolchain. The verified compiler fetcher needs `ar` and, when the Python standard library cannot read zstd, the `zstd` command. The integration build used a private Python environment with PyYAML `6.0.3`, PLY `3.11`, pyelftools `0.32` and pefile `2024.8.26`.

The helpers take absolute paths as positional arguments; they do not install a system driver or configure Steam. The Mesa helper also stages the pinned compiler helper scripts, an empty kernels directory and component licenses. Use fresh, dedicated build directories whose parents already exist. Run these commands from this folder on Linux:

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

For Galactic Racer, select the tested **Proton Experimental 11, `experimental-11.0-20261014-x86_64`**. Earlier Hotfix startup trials did not complete during observation; this does not isolate the cause of that delay. For other games, preserve the existing compatibility selection as a baseline. GE-Proton has not been validated here; some versions rewrite `INTC_ALT_DRIVER_EXTENSIONS_PATH`. Replace the example checkout path below with the actual absolute path. Preserve any existing game launch settings before editing them.

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
