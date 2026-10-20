# DRM event-delivery cadence

`analyze.py` reads a saved ftrace `drm_vblank_event_delivered` capture without
accessing or changing the device. It groups events by DRM-file token and CRTC,
then reports first-to-last delivery rate, median interval and nearest-rank p95.

```sh
python3 analyze.py drm-vrr-dc-on-repeat-flips.txt
```

The capture should use an isolated tracefs instance with only this event enabled,
with tracing disabled during setup and stopped before saving the buffer. Preserve
the header's entries-written count to check buffer loss. Stop and remove the
instance after capture; leave global tracing and other instances unchanged.

These are CPU dispatch timestamps. They establish continued DRM event delivery
when the userspace timer diagnostic is blind, but do not carry game commit
identity or the DRM event's first-visible timestamp. Compare the same settled
scene, cap, refresh, HDR and VRR state; corroborate with game telemetry and
per-submission timing when available. No optical smoothness claim follows from
this measurement alone.
