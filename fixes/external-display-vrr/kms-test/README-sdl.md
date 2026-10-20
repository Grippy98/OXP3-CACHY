# SDL cadence test inside the existing Gamescope session

This test keeps the compositor and its KMS pipeline running. It uses SDL2's
accelerated renderer in a fullscreen Xwayland window, requests renderer VSync
off, and produces a moving white bar at a controlled cadence. It never opens a
DRM master, changes HDR/VRR or display modes, stops services, or modifies boot
configuration. Closing the program closes only its SDL window.

Build on the Linux target with SDL2 development files and pkg-config available:

```sh
sh build-sdl.sh
```

Launch as the logged-in Gaming Mode user with access to the existing Xwayland
session and its X authentication. Use the actual Xwayland DISPLAY from your running session; for example:

```sh
DISPLAY=:1 ./sdl-cadence
```

Default: **24 seconds, 60 → 80 → 100 FPS**, approximately eight seconds per
segment. A large green number identifies the requested frame rate; one through
three small green markers identify the segment. The white bar crosses the
screen every two seconds. The window closes automatically. Escape or normal
termination signals stop it early.

A steady 80 FPS run can simplify checking the TV's refresh counter:

```sh
DISPLAY=:1 ./sdl-cadence --fps 80 --duration 20
```

The supported duration is 1–30 seconds; the supported steady frame rate is
40–100 FPS. Values outside those limits are rejected, including 119 FPS. An
outer timeout can also bound a stalled graphics-driver call:

```sh
DISPLAY=:1 timeout --signal=TERM --kill-after=2s 35s \
  ./sdl-cadence --duration 24
```

The test forces SDL's X11 backend, requires an accelerated renderer and asks for
fullscreen desktop mode. It does not request an SDL display-mode change. It
logs the renderer output size and Xwayland's reported display information, which
must not be mistaken for actual HDMI link state. Verify the current KMS mode,
RGB/bpc, HDR metadata, DSC and VRR properties separately while it runs.

Scheduling uses absolute `CLOCK_MONOTONIC` deadlines. When a frame misses its
next slot, the test skips expired slots instead of sending a burst of catch-up
frames. Each segment reports:

- Requested FPS and achieved application-present FPS.
- Frame counts, late deadlines and skipped schedule slots.
- Minimum, mean, p99 and maximum intervals between completed SDL present calls.
- Mean and maximum time spent inside `SDL_RenderPresent`.

These are application-side timestamps. They do not establish physical scanout
or TV refresh. A compositor may repeat, delay or discard presented frames. For
matched tests, keep the display mode and compositor configuration constant and
change only the existing VRR control between runs. Capture the TV's behavior
and kernel/compositor state separately.

The log records the return value from `SDL_RenderSetVSync(renderer, 0)` when the
SDL version supports it: zero indicates the request succeeded. SDL renderer
flags describe capabilities; a VSync capability flag is not proof that VSync is
currently enabled. The measured cadence and present-call blocking times provide
additional evidence of pacing constraints.

Primary API references:
[SDL_RenderSetVSync](https://wiki.libsdl.org/SDL2/SDL_RenderSetVSync),
[SDL_RendererInfo](https://wiki.libsdl.org/SDL2/SDL_RendererInfo),
[SDL_RenderPresent](https://wiki.libsdl.org/SDL2/SDL_RenderPresent).

