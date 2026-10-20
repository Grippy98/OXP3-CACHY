# How the controller fix works

The OXP3 exposes a native Xbox controller plus a companion keyboard and vendor
HID interface. The kernel MCU configuration path and userspace event composition
serve different parts of that hardware.

The pinned `hid-oxp` driver corrects X2-family three-page button mapping and
M1/M2 defaults, limits configuration ownership to interface 2, adds independent
RGB zones, and improves transaction/teardown and suspend restoration. Its original
series and exact final source are retained; the external module is compiled
against each target kernel rather than distributing a machine-specific module.
See [driver pins and ABI documentation](kernel/SOURCES.md).

InputPlumber combines the Xbox, companion keyboard and vendor HID events into
one virtual Xbox Elite controller. The local map changes the keyboard chord's
target from `QuickAccess2` (screenshot in the pinned default profile) to
`Keyboard` (Guide + North). OXP3-only hwdb enables automatic management. The
original device topology and remaining mappings are preserved. Both kernel and
userspace components were present when the owner verified the menu controls and
both rear paddles. [The userspace README](inputplumber/README.md) lists routes,
source pins and schema checks; [the source review](inputplumber/CODE-REVIEW.md)
explains filtering, chord timing and nonrecursive mapping.

The new CachyOS installer validates model identity and exact matching headers,
backs up the prior selected module, registers versioned DKMS sources, rebuilds
initramfs, and invokes the backed-up userspace installer. Matching state is
reused; conflicting source at the same version is refused. Rollback uses each
installation's saved state and leaves packages/backups available. These scripts
have host checks and packaging validation, but were not run on another device.

The driver is pinned to [OGC PR 13](https://github.com/OpenGamingCollective/linux-unstable/pull/13);
its complete PR diff also contains unrelated history, so only the retained driver
series is relevant here. The userspace contribution in
[PR 660](https://github.com/ShadowBlip/InputPlumber/pull/660) was closed unmerged.
Future stock kernel/InputPlumber versions may need a rebase or make an override
unnecessary. Review current stock support before installing the older pin.
Follow [the README](README.md) for setup, physical verification and rollback;
[build details](docs/BUILD.md) cover the optional source package.
