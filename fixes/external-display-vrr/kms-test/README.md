# Bounded direct-KMS VRR test

`oxp3-kms-vrr.c` provides a moving-bar workload that uses libdrm directly, without
Gamescope, a desktop compositor, Vulkan, video decoding, Steam or HDR content.
It is a diagnostic client, not a VRR implementation. It cannot prove that the
converter or TV supports VRR merely because atomic commits succeed.

The fixed target is **DP-1, a compatible unoccupied CRTC, primary plane,
1920×1080 progressive at exactly 120.000 Hz**. The tool prefers DP-1's current
CRTC if no other connector uses it; otherwise it chooses another compatible
free CRTC. It prints the actual CRTC index and ID for the capture. It preserves
CRTCs attached to other connectors, including fbconsole on the built-in panel. A nominal 119.88 Hz mode is not
substituted. It requires an XRGB8888 framebuffer and requests connector maximum
8 bpc, default colorspace, full RGB when available, zero HDR metadata and
identity CRTC color transforms. The driver chooses the physical link format;
verify actual 24-bit RGB, HDR off and DSC off in the kernel state during the
run. These are not inferred from framebuffer format alone.

Default behavior only inspects resources and prints the plan. **No KMS state is
written until `--execute` is supplied.** Live execution requires DRM master and
must happen only after the compositor has stopped. The program refuses to
steal a CRTC attached to another connector, and does not stop services
or change firmware, EDID, boot configuration or the kernel.

## Build and inspect

Build on Linux with a C compiler, pkg-config/pkgconf and libdrm development
headers (`libdrm-dev` on Debian; `libdrm` on CachyOS/Arch):

```sh
sh build.sh
./oxp3-kms-vrr --device /dev/dri/card0
```

The build uses `-Wall -Wextra -Werror`. A Mac without Linux DRM headers is not a
suitable native build host. Compiling or running the inspection mode does not
require stopping Gamescope. Do not use the rendered-mode commands while it
holds DRM master.

## Controlled test

The operator must stop the actual compositor/session first and arrange its
restart after the program exits, including error exits. This tool does not know
the target's service topology and intentionally does not guess service names.

Run the fixed-refresh control first:

```sh
sudo timeout --signal=TERM --kill-after=2s 25s \
  ./oxp3-kms-vrr --execute --duration 20 --fps 60,80,100,119
```

Then the VRR-enabled run:

```sh
sudo timeout --signal=TERM --kill-after=2s 25s \
  ./oxp3-kms-vrr --execute --enable-vrr --duration 20 --fps 60,80,100,119
```

Without `--enable-vrr`, live execution explicitly writes `VRR_ENABLED=0`.
Supplying it explicitly writes `VRR_ENABLED=1`. The program uses atomic
`TEST_ONLY` before applying the initial modeset. It fails if that request is not
accepted; it never falls back to a different mode or silently drops VRR.

The default 20-second workload spends roughly five seconds at each listed
frame rate, below the output's 120 Hz ceiling. The white bar crosses the screen
once every two seconds, against a gray checkerboard. One through four green
blocks identify the active segment. A single rate is useful for a simpler
physical test:

```sh
sudo timeout --signal=TERM --kill-after=2s 25s \
  ./oxp3-kms-vrr --execute --enable-vrr --duration 20 --fps 80
```

Duration accepts only 1–20 seconds. Frame rates accept 40–119 FPS, with at most
four segments. Double buffering prevents drawing into the scanned-out buffer;
only one atomic frame flip is pending at a time. Monotonic absolute deadlines
set the frame cadence. A one-second page-flip event timeout terminates the test
if the driver stops completing flips. The outer `timeout` also bounds abnormal
ioctl stalls; its kill interval is for recovery, not extra rendering time.

## Exit and recovery

**This tool does not reconstruct the compositor's previous complex KMS state.**
On normal exit, error after modesetting, SIGINT, SIGTERM or SIGHUP, it attempts
to detach its connector/plane, disable its CRTC and VRR, release buffers and drop
DRM master. The external screen is therefore expected to be blank after the
test until the operator restarts the compositor. Other CRTCs are not disabled.
Restart the compositor only after this process exits. Keep a restart action in
the operator's surrounding error-handling path; neither a test failure nor a
`timeout` exit should skip recovery. There is no automated assumption that a
black TV is a successful test.

Each segment prints submitted frames and DRM display-event interval statistics
(minimum, mean, p99 and maximum). Those timestamps measure kernel scanout events,
not photons, HDMI analyzer results or the TV's VRR status. Record the TV's actual
behavior and VRR diagnostics, kernel connector/CRTC/DSC/HDR state, and AS packet
readback separately. Compare the VRR-off and VRR-on runs at the same mode.

Source references: Linux [atomic KMS API](https://docs.kernel.org/gpu/drm-kms.html)
and libdrm's original [modetest client](https://gitlab.freedesktop.org/mesa/drm/-/blob/main/tests/modetest/modetest.c).
