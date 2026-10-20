# Bounded timing-trace analysis

`analyze.py` reads the diagnostic Gamescope journal text without accessing the
computer or changing its state. It uses each DRM submission's captured base
CommitID/AppID rather than mutable Mango telemetry identity.

```sh
python3 analyze.py TRACE.log --first 482 --last 721 --app 1710820
```

Select a contiguous capture explicitly when the file contains older records.
The first timer identifies the already displayed base; its repeated first flip
is not counted as a new game update. A game transition is the next change of
submission identity for the chosen AppID. Reported rates use first-to-last
physical timestamps and transition counts, rather than a periodic FPS readout.

A fixed-refresh game flip more than 1 ms after its recorded target is counted
late. This threshold suits the observed 8.33 ms missed-cycle separation and is
not an adaptive-sync timing model; VRR captures report the late-frame count as
`null`. Rounded interval buckets may split one
nominal period between adjacent values. Both raw logs and their hashes should
be retained alongside the analysis.

The trace has a bounded secondary-line budget, so missing page-flip records
can hide transitions. Results are scoped to the logged window, scene and
single active output. Logging overhead, mode transitions and a change of
active application can affect the measurement; this is a diagnostic, not a
lossless performance monitor.
