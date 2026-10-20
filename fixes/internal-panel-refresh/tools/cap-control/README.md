# Internal-display cap-only control

`gamescope-cap-control` sends one Gamescope Wayland request with an FPS value from 0 through 144 and flags `INTERNAL_DISPLAY` (`0x1`). Zero disables the cap. It is a runtime control tool; it does not install a service or change kernel settings.

The helper is intended for controlled OXP3 captures that require the panel's highest mode, 144 Hz, with a separate 60 FPS game cap. Gamescope's `debug_set_fps_limit` changes both the stored cap and combined dynamic-refresh override. Direct X properties are overwritten when the next paint reapplies that stored override. This helper stores the cap-only override through the protocol instead.

In the pinned source, this request clears the desired combined dynamic rate. The paint policy therefore selects the connector's highest valid mode. On this OXP3 profile that is 144 Hz. This is not a general promise to retain an arbitrary currently selected mode.

## Protocol verification

Before sending a setting request, the helper verifies that the compositor offers `gamescope_control` version 2 or newer and binds version 2, the version that introduced `set_app_target_refresh_cycle`. It waits for the feature-list completion event, advertised display-info support, and the initial active-display event. It rejects an active external display.

The protocol has no named feature enumeration for the basic cap-only request; version 2 is its capability contract. The helper does not set `ALLOW_REFRESH_SWITCHING` or `ONLY_CHANGE_REFRESH_RATE`. After sending, it completes a roundtrip so the server has processed the request. A successful roundtrip does not confirm the physical mode, actual cap, or active VRR state.

All arguments are checked before connecting: decimal digits only, no signs, no trailing text, overflow rejected, range 0–144. `--help` prints usage without connecting.

## Build and run

The checked-in XML matches Valve Gamescope 3.16.25, commit `17baf4abd1ab3353fb705e4d0d023f84e870f7e8`. Its generated protocol files are included so the helper can be built without regenerating them. The protocol's copyright and license are retained.

Build on Linux with Wayland client development files installed:

```sh
cc -std=c11 -O2 -Wall -Wextra -Werror \
  gamescope-cap-control.c gamescope-control-protocol.c \
  $(pkg-config --cflags --libs wayland-client) -o gamescope-cap-control
```

The executable is ignored by the local `.gitignore`. To regenerate protocol files when reviewing the pinned XML:

```sh
wayland-scanner client-header gamescope-control.xml gamescope-control-client-protocol.h
wayland-scanner private-code gamescope-control.xml gamescope-control-protocol.c
```

Run in the Gaming Mode user session with its correct `XDG_RUNTIME_DIR` and `GAMESCOPE_WAYLAND_DISPLAY`:

```sh
./gamescope-cap-control 60
```

If `GAMESCOPE_WAYLAND_DISPLAY` is unset, the helper tries `gamescope-0`, matching the existing performance-query helper. The setting persists until another Gamescope or Steam control request replaces it. A later combined debug command can also replace it.

For a VRR driver comparison, enable adaptive sync separately and verify a settled bounded trace has `refresh_mhz=144000`, `cap=60`, and `vrr=1`. Also verify hardware VRR state and count physical game presentations. The request's display-info event describes capability, not whether VRR is currently active.

## Expected limiter behavior

When `IsVRRActive()` is true, Gamescope calculates the limited app cycle as `1/60` second and gates each eligible window against its last frame-callback/latch time plus that interval. It allows a 0.2 ms early-admission tolerance and arms a separate timer for the earliest deferred deadline. It does not use `floor(144/60)` in that branch. Rendering, driver timing, and overlay behavior can still affect physical cadence; 60 FPS is the requested deadline policy, not a guaranteed measured result.

With VRR inactive at 144 Hz, the fixed-refresh branch uses a divisor of `floor(144/60) = 2`, resulting in a 72 FPS admission cadence. Confirm `vrr=1` before treating a 144/60 capture as a VRR cap test. Steam and overlay windows are exempt from the game limiter.

