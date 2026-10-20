# EDID transport regression tests

Run `python3 make_and_test.py` with Python 3, Git and Clang (or set `CC`). The runner checks the saved patch against the pinned upstream `drm_edid.c`, applies it to a temporary tree, and compiles the actual original/patched functions with mocked I²C. Generated includes and binaries remain in temporary directories.

The 21 cases cover the retained-segment reproducer, unchanged valid reads, explicit-zero recovery, legacy sinks, NAK/ENXIO handling, extended-to-base reads, short probes, ordinary/recovery retries, the five-transfer limit, partially matching headers, malformed data, block 1, longer reads and short transfer returns. Blocks are synthetic; no saved display EDID is required or distributed.

AddressSanitizer and UndefinedBehaviorSanitizer cover the host harness. This is not a kernel integration test and does not model real DP AUX timing, concurrency, HPD, suspend/resume or every noncompliant sink. See [the fix README](../../README.md) for tested hardware status.
