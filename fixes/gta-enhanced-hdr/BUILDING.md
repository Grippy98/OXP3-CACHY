# Build the private WSI layer

This builds an **experimental Gamescope WSI candidate** for controlled GTA HDR tests. HDR transport worked in one Story Mode session, but later cold starts still froze or exited, including with frame generation off. The queue patch alone did not resolve startup. A later [Core-updated HDR/SR profile](README.md) passed short tests, but the necessity of this queue patch has not been isolated. It leaves the installed compositor and system Vulkan manifests alone and is used only when a per-game launcher selects its directory.

Run on **Linux x86-64 as your normal user**, without `sudo`. Requirements are Python 3, a C++20 compiler (`g++`), a C compiler, `patch`, `pkg-config`, `wayland-scanner`, Vulkan/GLM headers, and the X11, X11-XCB, XCB, XCB-composite and Wayland client development libraries. The tested CachyOS device already had these. The helper does not install packages.

```sh
python3 build-wsi-layer.py
```

The default output is:

```text
~/.local/lib/oxp3-gamescope-wsi/3.16.25-event-queues-20261105/
  libVkLayer_FROG_gamescope_wsi_x86_64.so
  VkLayer_FROG_gamescope_wsi.x86_64.json
  build-info.json
```

The build downloads nine small, commit-pinned public source inputs from Gamescope and its matching vkroots dependency. Every file, the local patch and the final patched source are checked against [WSI-SOURCE.json](WSI-SOURCE.json). There is no archive extraction or vendored source tree. Original download bytes are cached under `${XDG_CACHE_HOME:-~/.cache}/oxp3-fixes/gta-enhanced-hdr/3.16.25-event-queues-20261105` for offline rebuilds.

Compilation and dependency checks finish before complete output files are published. An unrecognized nonempty output directory is refused. Neither build success nor `build-info.json` claims that the layer is active in a game.

## Options

| Option | Purpose |
|---|---|
| `--output PATH` | Choose a different private output directory. |
| `--cache PATH` | Choose the source-download/build cache. |
| `--offline` | Require the pinned sources to be cached; make no downloads. |
| `--prepare-only` | Verify/download and patch sources without compiling or publishing; also works on macOS. |

`CC` and `CXX` can select compilers. Changing a compiler can change the output hash; source pins and the patch still must verify. This helper builds only the userspace layer, not a kernel, a full compositor or a Proton distribution.

## Use and validation

For a controlled diagnostic run, the companion XeSS `--hdr` profile selects the standard private output:

```text
"/path/to/OXP3-CACHY/fixes/xess-xmx-community/gta-launch.sh" --hdr %command% -nobattleye
```

For a custom output, set `OXP3_GTA_HDR_WSI` to that directory. That profile prepends its manifest path, enables Gamescope WSI and removes `DISABLE_GAMESCOPE_WSI` entirely. **A disable variable set to `0` still disables an implicit layer.** Other implicit Vulkan layers stay discoverable. Check the actual game process maps this private `.so`; a saved launch option alone does not prove selection.

This layer supplies transport for the game-specific HDR mod; it does not create HDR through shader changes or edit graphics settings. The one successful session used GTA V Enhanced Story Mode, XeSS SR and RenoDX, with **frame generation off**. Subsequent cold starts still failed with FG off and the earlier settings restored. Use the main instructions for the current investigation status and ReShade/RenoDX setup. Combined HDR and XeFG, other games, long sessions and future versions remain unqualified.

Gamescope's `GAMESCOPE_COLOR_APP_WANTS_HDR_FEEDBACK` root property becomes `1` when it recognizes HDR input. Before the session's first HDR transition that property can be absent, since Gamescope 3.16.25 does not initialize it to zero. An HDR-capable output flag alone does not establish actual HDR input.

Removing `--hdr` from the per-game profile stops selecting this private layer. Remove the private output/cache folders later if desired; the helper makes no global changes that need reverting.

## Patch provenance

The [candidate patch](patches/0001-private-wayland-event-queues.patch) is a manual backport to Gamescope **3.16.25** and its older vkroots API, inspired by upstream event-queue and ownership fixes. It is not a literal cherry-pick. Registry startup uses one private queue roundtrip, without an initial blocking dispatch on a shared queue. Protocol version, HDR formats and compositor behavior are unchanged.

HDR10/PQ/BT.2020 output and compositor HDR-input feedback were demonstrated in **one Story Mode session with FG off**, and the owner reported correct HDR, gameplay and HUD in that run. Later cold starts failed even with FG off and the previously used settings restored. The patch therefore remains a candidate, not a demonstrated startup fix. Captured thread locations did not establish a WSI/Wayland/XCB blocking frame; an event-queue deadlock remains unproven. Reliable cold startup, combined FG behavior and broader compatibility are unresolved.

The upstream work is credited to PancakeTAS and Matthew Schwartz: [bound-global ownership](https://github.com/ValveSoftware/gamescope/commit/1e7a0bbca86f00157bbce464294a149125790c18), [private surface queues](https://github.com/ValveSoftware/gamescope/commit/92363db5088393f62aebe43a050b5af26d792ea4), [swapchain event dispatch](https://github.com/ValveSoftware/gamescope/commit/330b8c131589194206cdf645599099304748e56f), and [driver/Wayland teardown order](https://github.com/ValveSoftware/gamescope/commit/f61e0a44843f8b340749615d2f072651666e760d). Exact source pins are listed in [WSI-SOURCE.json](WSI-SOURCE.json). Gamescope's BSD notice, vkroots' license notice/MIT text and the SDL-derived helper notice are retained under [licenses](licenses/).
