# Third-party fix-pack source review

This folder reviews [onexplayer3-steamos-setup](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/tree/ea371b357b8ba6467e00c0be372e1c86c1ac523b) at pinned commit `ea371b357b8ba6467e00c0be372e1c86c1ac523b` and release v1.6.1. It is source analysis, not an installer or a hardware reproduction of every reported issue.

Read [WRITEUP.md](WRITEUP.md) for applicability and [the implementation review](third-party.md) for 18 source-level findings. The foreign installer, firmware, ACPI image and downloaded binaries are not bundled or executed.

The [2026-10-20 game-pack follow-up](kas5852-game-pack.md) reviews kas5852's pinned branch and linked Intel Decky plugin against the current CachyOS setup. It separates useful per-game experiments from graphics correctness, rollback, power-control and firmware concerns.

This collection implements only independently scoped fixes. No action is installed by this folder or its menu entry.
