# Per-submit DRM telemetry identity (separate research)

This candidate is **not part of the accepted display runtime**. It targets Gamescope 3.16.25 (`17baf4abd1ab3353fb705e4d0d023f84e870f7e8`) and snapshots CommitID/AppID into `DRMPresentCtx` before atomic submission. The callback copies them before releasing its waiter, avoiding attribution to a subsequently painted base. The one-argument Vulkan overload retains existing behavior.

The patch preserves physical timestamps, notification ordering, timer/FIFO scheduling and wire formats. It addresses a source-level attribution race; it does not establish that this race caused the observed FPS discrepancy or fix multi-output/cross-app accounting generally. It has no device/full Gamescope build claim.

Run `python3 tests/run.py` with Clang++ and C++20. The small source fixture preserves the exact patched output-update functions; the harness checks submitted AppID, duplicate overlay suppression, physical timestamp deltas, legacy overload and output-timing switch. An optional `--baseline-source /path/to/original/src/mangoapp.cpp` exercises the original wrong-attribution counterexample. No captures or reports are required.

`gamescope-drm-telemetry-snapshot.patch` is the complete change against the pinned source. Keep Gamescope's MIT license with redistribution; it is preserved in [the accepted-runtime license](../../gamescope/accepted-runtime/LICENSE).
