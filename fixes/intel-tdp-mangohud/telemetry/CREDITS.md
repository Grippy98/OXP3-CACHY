# Sources and licenses

| Material | Pinned upstream source | Attribution/license |
| --- | --- | --- |
| MangoHud base and changed-file snapshots | [v0.8.4 / `992103e4fb744897826de04ea00a2f71e7018214`](https://github.com/flightlessmango/MangoHud/tree/992103e4fb744897826de04ea00a2f71e7018214) | flightlessmango and contributors; [MIT](LICENSE) |
| Intel graphics RAPL power reference | [JohnnySun commit `427199768b4bbe990c29f96f430f8965d4029698`](https://github.com/JohnnySun/MangoHud/commit/427199768b4bbe990c29f96f430f8965d4029698) | JohnnySun; MangoHud MIT |
| Shared Intel memory / unavailable sensor reference | [JohnnySun commit `d6846ec128d866b5f0a038beaa11b45c40f301e0`](https://github.com/JohnnySun/MangoHud/commit/d6846ec128d866b5f0a038beaa11b45c40f301e0) | JohnnySun; MangoHud MIT |
| MangoApp one-render-per-frame patch | [Matthew Schwartz commit `01641ec2b6f7f231633e4e99bb2a21a2583dbef9`](https://github.com/flightlessmango/MangoHud/commit/01641ec2b6f7f231633e4e99bb2a21a2583dbef9), [PR 2067](https://github.com/flightlessmango/MangoHud/pull/2067) | Matthew Schwartz; original patch unchanged, MangoHud MIT |
| Panther Lake PMT schema copies | [Intel-PMT commit `1cd92cfb62b8757ed437d6d3f05836dd1a456fa0`, `xml/PTL/0`](https://github.com/intel/Intel-PMT/tree/1cd92cfb62b8757ed437d6d3f05836dd1a456fa0/xml/PTL/0) | Intel; [Apache-2.0](references/intel-pmt/LICENSE) |
| Arch packaging reference | [Arch MangoHud packaging](https://gitlab.archlinux.org/archlinux/packaging/packages/mangohud) | Package dependency/layout reference; local PKGBUILD glue |

The local Intel backport adapts JohnnySun's relevant changes and adds actual-time energy sampling, counter-wrap handling, fractional CSV power, retry/discovery fixes, integrated-GPU scoping, the shared-memory label, and exact-schema Intel PMT `GT_MAX`. It excludes unrelated fork experiments. PMT `GT_MAX` is Container 15 bits 56–63, a signed Celsius byte at file offset 127. The sysfs `offset` attribute is not added to a normal `telem` file read.

Patch SHA256 values:

```text
8533955ee8bee194647c1caba69b0959ec6df72744a6d446b3c51259f9b63e21  mangohud-intel-telemetry.patch
8ff1195d0b13339628615f0728fcd98177d22a91823e055d55733bb6db44b507  mangoapp-one-render-per-frame.patch
```

Apply the Intel patch first and the MangoApp patch second. `PKGBUILD` also pins the helper tests and each archive required by the release's Meson wraps. Preserve these licenses and the upstream commit authorship when redistributing or submitting changes.
