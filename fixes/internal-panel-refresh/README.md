# Internal OLED refresh and presentation pacing

See [WRITEUP.md](WRITEUP.md) for the technical explanation and upstream scope.

**Accepted device state:** the owner confirmed controls and motion with `7.2.9-onex3-vrr-test`, internal VRR enabled and the guarded Gamescope runtime at **zero extra wake lead** with tracing disabled. That combination was made persistent and verified by a normal reboot on the original device. The source and recipes for that complete runtime are retained here. Wider games, suspend/resume, dock switching, latency and power remain open.

## Profile-only installation

The Intel OXP3's Samsung `SDC:4301` / `AMS881KB01-0` panel advertises native 60 and 144 Hz fixed modes. The [Lua profile](profile/onexplayer3-sdc-refresh.lua) adds a tested 120 Hz mode so a 60 FPS request can select 120 Hz. It requires the exact panel identity and native base timing; it does not alter HDR/color/backlight interpretation.

```sh
# From the repository root, as the Gaming Mode user (without sudo):
./install.sh check panel-refresh
./install.sh install panel-refresh
./install.sh rollback panel-refresh
```

**This adapter installs only the refresh profile. It does not install the full accepted pacing fix.** It backs up the user's existing file, installs under `${XDG_CONFIG_HOME:-~/.config}/gamescope/scripts/`, and refuses to overwrite a subsequently edited managed profile. Close games and restart Gaming Mode to load or unload it. No session restart, kernel, boot-default change or experimental lead is automatic.

The generated timing is `380160000 / (2000 × 1584) = 120 Hz`, using a vertical front porch of 320, eight sync lines and 56 back-porch lines. The profile exposes 60/120/144 Hz and checks both native timing shapes before deriving a mode. Its match score 6000 takes priority over Valve's later 5000 profile for the same panel: remove/reassess the override when the distribution includes suitable upstream support.

## Full accepted runtime (manual)

The refresh profile addresses mode choice. The accepted presentation setup also includes:

- [Kernel build](kernel/README.md): the existing EDID retry, two upstream Intel DSB corrections and the upstream DC-balance gate defaulting off. The signed OXP controller override and UHID/UINPUT transports are retained.
- [Gamescope build](gamescope/README.md): pinned 3.16.25 with the complete guarded timer/trace source. Both extra lead and tracing default to zero; the accepted VRR setup leaves them there.
- [Runtime selection and rollback](permanent/README.md): an isolated runtime, checksum-guarded wrapper and session configuration. Kernel and boot-menu selection remain manual.
- [Mangoapp upstream patch](upstream/mangoapp-one-render-per-frame.patch): the one-render-per-game-frame correction used in the accepted setup. It did not independently fix the display pacing issue; the sibling telemetry/Mangoapp build carries it.

The earlier two-upstream-patch Gamescope candidate is preserved for review in `gamescope/build.sh`; it failed to resolve the problem on its own and is not the accepted executable. A 1.7 ms extra-lead experiment improved bounded fixed-refresh tests but remains opt-in research, separate from the accepted zero-lead VRR setup. No universal fixed-refresh scheduling repair is claimed.

## Tests and upstream path

```sh
python3 fixes/internal-panel-refresh/tests/test_installer.py
luajit fixes/internal-panel-refresh/tests/test_profile.lua   /usr/share/gamescope/scripts/00-gamescope/common/modegen.lua   fixes/internal-panel-refresh/profile/onexplayer3-sdc-refresh.lua
python3 fixes/internal-panel-refresh/diagnostics/telemetry-snapshot/tests/run.py
```

The Lua suite checks matching/exclusions, exact mode generation from both native modes, immutable input, changed-timing rejection and fallback. The separate telemetry snapshot regression test addresses per-submit identity attribution; it is **not part of the accepted runtime**. Host tests and software FPS counters do not establish physical TV/panel refresh or optical smoothness.

The Intel corrections are upstream commits [f7140c7c](https://github.com/torvalds/linux/commit/f7140c7cef3037f5d3757bb5db0f4c6aee4a240f), [4a68c751](https://github.com/torvalds/linux/commit/4a68c7516c57a3d03b406c8aaa073c62149aad68) and [c034e8a4](https://github.com/torvalds/linux/commit/c034e8a46e4cb703018fe7e10fe5a3a974d6a7c3). Prefer distribution updates carrying those fixes over maintaining a local old kernel. Valve's [same-panel profile](https://github.com/ValveSoftware/gamescope/blob/36848c2f30e4afef02f4500665710d8006bd6619/scripts/00-gamescope/displays/lenovo.legiongo2.oled.lua) provides an upstream direction for refresh support. The local scheduler and telemetry changes need independent upstream review and broader tests; they must not be conflated with merged Intel fixes.
