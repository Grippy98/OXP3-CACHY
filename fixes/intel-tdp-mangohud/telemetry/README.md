# MangoHud Intel telemetry backport

A source-only backport for **MangoHud v0.8.4**, commit `992103e4fb744897826de04ea00a2f71e7018214`. It adds Intel integrated graphics watts, exact-schema PMT GPU temperature, shared process GPU memory, fractional package/GPU power, and a separate upstream MangoApp render-loop fix. Sources, authors and licenses are listed in [CREDITS.md](CREDITS.md).

| Metric | Meaning |
| --- | --- |
| CPU/package watts | `package-0` energy divided by actual monotonic elapsed time; includes integrated graphics. `cpu_text=Package` can make that clear. |
| GPU watts | Named RAPL `uncore` graphics energy, with wrap handling and fractional watts; not added to package watts. |
| GPU temperature | Native hwmon first, otherwise Intel PMT `GT_MAX` only for GUID `0x03086000`, size 3352, byte 127; unknown layouts and invalid values remain unavailable. |
| GPU MEM | Focused-process resident shared GTT memory on Xe (`drm-resident-gtt`) or i915 (`drm-resident-system0`); not dedicated VRAM or total system usage. |
| Usage/clock | Existing process fdinfo and GT sysfs sources. Process metrics need the game's live PID/descriptors. |

RAPL fallback binds only the integrated graphics slot `0000:00:02.0` on a single-package system. Discovery prefers readable MSR package-0 over duplicate MMIO, skips unrelated domains, retries unavailable access at most once per second, and continues after failed opens. CSV GPU watts preserve fractions; the existing CSV VRAM column retains its dedicated-memory meaning and may remain zero on this iGPU.

The runtime stays unprivileged. Install [selected sensor read permissions](../permissions/README.md) separately and use a desktop user already in `video`. No power-limit writes are needed to read telemetry. This is a 64-bit backport; `lib32-mangohud` needs its own patch for 32-bit applications.

## Build and install

For native x86-64 Arch/CachyOS, use the [PKGBUILD](arch/README.md):

```sh
cd arch
makepkg --cleanbuild
```

Build as an ordinary user after installing the build dependencies listed in `PKGBUILD`. The recipe pins the commit, both patches, tests and all seven Meson archives. It builds without privileged hooks and does not install the result. Keep copies of the installed distribution package(s) from `/var/cache/pacman/pkg` before replacement, then install the specifically selected output with `sudo pacman -U /absolute/path/to/mangohud-onex3-0.8.4-3-x86_64.pkg.tar.zst`. Review the transaction and restart MangoApp or the gaming session afterward.

For a source build that only stages output:

```sh
./build.sh /path/to/new-build-output
```

Requires Git, C++17 compiler, Meson, Ninja, pkgconf, python-mako, glslang, Vulkan headers, dbus, libx11, libxrandr, libxkbcommon, Wayland and glfw development packages. Network access is required for pinned upstream sources. The build checks patch hashes, checks out the exact commit, applies both patches, runs helper tests, and installs only below the output's `staging/` directory. Existing output is refused. Use the package recipe to install system files.

## Tests and limits

```sh
./tests/run-tests.sh
```

ASan/UBSan tests exercise the production shared headers: elapsed time, fractional watts, energy wrap, delayed discovery, malformed counters/fdinfo, shared-memory selection, and PMT GUID/size/signed-temperature bounds. They do not replace a native Linux build or a device overlay check.

The separate [upstream MangoApp commit](https://github.com/flightlessmango/MangoHud/commit/01641ec2b6f7f231633e4e99bb2a21a2583dbef9) renders at most once per game-frame notification and uses a bounded wait. It is included unchanged with its author header. This patch alone does not resolve the full Gamescope frame-cap problem on the OXP3; display timing changes are a separate component.

`patched-source/` holds only the upstream files changed by these two patches, including the patched upstream README. It is a review snapshot, not a complete build tree. Keep `arch/` patch/test copies identical to the top-level files when editing and update PKGBUILD hashes deliberately. Before an upstream contribution, rebase against the current MangoHud backend and split independent CPU arithmetic, GPU power, memory and PMT changes for review.
