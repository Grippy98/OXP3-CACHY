# Read-only CRTC vblank sequence sampler

This small libdrm client reads the running CRTC's vblank counter and timestamp
with `drmCrtcGetSequence`. It opens the primary DRM node **read-only**, never
requests DRM master and never changes modes, properties, buffers or services.
Run it while Gamescope and the controlled SDL workload remain active.

Build on the Linux target with its installed libdrm headers and pkg-config:

```sh
sh build-sequence.sh
./crtc-sequence --device /dev/dri/card0 --crtc 151 --seconds 10 --interval-ms 1000
```

Permissions must allow reading the primary node; run as root if necessary. The
CRTC ID is a DRM object ID, **not** a pipe number, connector ID or resource index.
The program checks the requested ID and prints its actual resource index and
current mode. It refuses an inactive or missing CRTC and never substitutes one.
The sample ID 151 is illustrative: identify the current external CRTC again after topology or compositor changes.

`vblank_hz` is the difference in kernel frame sequence divided by the difference
in the corresponding kernel nanosecond timestamps. `wall_hz` uses elapsed
monotonic polling time as a cross-check; it can differ slightly due to the
position of a sample within a frame. `TOTAL` averages the entire capture. A
counter or timestamp that stops or resets is an error, not a successful zero-Hz
measurement. Duration is bounded to 1–60 seconds and polling intervals to
100–5000 ms. SIGINT/SIGTERM close the file descriptor without changing display
state.

Compare fixed-refresh and VRR runs at the same mode and workload, or take a
capture during each steady 60/80/100 FPS phase. These counters describe the GPU
CRTC's vblank cadence; they do not prove converter-to-TV HDMI timing or physical
delivery. Record the LG's FreeSync/rate indication and any blackouts separately.

The API is declared in libdrm's [public header](https://android.googlesource.com/platform/external/libdrm/+/master/xf86drm.h)
and implemented as `DRM_IOCTL_CRTC_GET_SEQUENCE` in its [primary source](https://cgit.freedesktop.org/drm/libdrm/tree/xf86drm.c).
The interface uses a CRTC object ID and returns a frame sequence plus the
nanosecond timestamp for that frame, as described by its [original author](https://keithp.org/blogs/DRM-lease-4/).
