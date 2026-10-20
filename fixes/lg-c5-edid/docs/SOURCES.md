# Pinned kernel sources and licenses

These identify the historical tested build, not current kernel recommendations. Reconstruct a research tree from the exact inputs; a changing branch URL must still match the recorded digest.

| Input | Pin / source | SHA256 |
| --- | --- | --- |
| `PKGBUILD` | [source](https://github.com/CachyOS/linux-cachyos/blob/ee39638ff003ef2def73671ec1677d48218e7c03/linux-cachyos-deckify/PKGBUILD) | `b8525fe77b72706dc4b807c8fb540490ae2510913ab83fb8240714a9281526bd` |
| `acpi-call.patch` | [source](https://raw.githubusercontent.com/CachyOS/kernel-patches/master/7.2/misc/0001-acpi-call.patch) | `acd2ed34838556809839398a91a8fae99261b13a04c5f4cf34cbc03d1011fe6a` |
| `bore.patch` | [source](https://raw.githubusercontent.com/CachyOS/kernel-patches/master/7.2/sched/0001-bore-cachy.patch) | `1809a4d4d6508a2a3f92cd8b3b385640583f90bd6cee46584f4bf105affd24a0` |
| `cachyos-7.2.9-2.tar.gz` | [source](https://github.com/CachyOS/linux/releases/download/cachyos-7.2.9-2/cachyos-7.2.9-2.tar.gz) | `2da9e6ffe31436657f46909db059059946dac22c2ac6cde05e49a66d61acfcba` |
| `handheld-pinned.patch` | [source](https://raw.githubusercontent.com/CachyOS/kernel-patches/edb006d5cea1b0544fd084ad6e3683e0ab2090c7/7.2/misc/0001-handheld.patch) | `48532eb3b3e68f6b15219dca1fe2bf6c0f34213d3fad37464073e0348729ca1f` |

CachyOS source commit: `09bc889a111715e4509b3819b628c9b9d9d09a0b` (`cachyos-7.2.9-2`). Distribution recipe: `ee39638ff003ef2def73671ec1677d48218e7c03`. The `drm_do_probe_ddc_edid` implementation matches upstream v7.2.9; the complete `drm_edid.c` files differ in already-read capability parsing. The retained upstream file is needed only for exact patch applicability and host extraction tests.

The saved `kernel/cachyos-src/upstream/drivers/gpu/drm/drm_edid.c` preserves its full original permissive copyright/license notice. Intel test fixtures preserve their Intel notices, and kernel patches inherit the corresponding kernel files’ licensing. Redistributed full kernels must retain Linux’s `COPYING`, applicable `LICENSES/` texts and complete corresponding source. The build packaging helpers copy the kernel’s GPL-2.0 license. Controller code is GPL-2.0-or-later; its notices/source and license text are preserved separately.

The public repository supplies source patches and build configurations, not compiled kernels, private signing keys, original display EDIDs or machine-specific boot images.
