# Pinned driver sources

`hid-oxp.c` is unchanged from [the selected PR head](https://github.com/Grippy98/linux-unstable/blob/4396c18eef297543889681a77283c13e047dfe22/drivers/hid/hid-oxp.c).

| Item | Pin |
| --- | --- |
| Change | [OGC Linux PR 13](https://github.com/OpenGamingCollective/linux-unstable/pull/13) |
| Driver commit | `4396c18eef297543889681a77283c13e047dfe22` |
| Series parent | `5be7813f340baa3b2cac9e8297fea101f2d8f35b` |
| Driver SHA256 | `64e1edb403f31808f44d6b347017b4c73d3dd7670d5bba995231e8e6ec9a9e29` |
| Consolidated patch SHA256 | `d28466a0ffc7e8d62554a7ac0a40b6b1e947520f9d75869c73ff4630e672b1c7` |

`patches/series` lists the fifteen original contribution patches in order, with
their original author and sign-off metadata. `reference/hid-oxp-series-parent.c`
is the pre-series driver. `reference/hid-oxp-cachyos.c` is the CachyOS 7.2.9
baseline for the consolidated driver-only patch. Applying that patch reproduces
the pinned final driver; applying the PR's complete multi-commit diff would also
include unrelated kernel history and should be avoided.

The [sysfs ABI documentation](https://github.com/Grippy98/linux-unstable/blob/4396c18eef297543889681a77283c13e047dfe22/Documentation/ABI/testing/sysfs-driver-hid-oxp)
is included as `sysfs-driver-hid-oxp`. Kernel source/patch licensing is
GPL-2.0-or-later; `COPYING` and `GPL-2.0` retain the kernel license material.
`hid-ids.h` supplies the kernel HID identifiers needed for the external build.
No driver changes or new upstream sign-offs were added during packaging.
