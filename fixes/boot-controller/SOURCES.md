# Sources and licenses

| Item | Pin |
| --- | --- |
| Limine base | [v12.9.0](https://github.com/Limine-Bootloader/Limine/tree/34fe53c3d27d229ea25c28fc3e04db362543715b), commit `34fe53c3d27d229ea25c28fc3e04db362543715b` |
| Release archive | [limine-12.9.0.tar.xz](https://github.com/Limine-Bootloader/Limine/releases/download/v12.9.0/limine-12.9.0.tar.xz) |
| Archive SHA256 | `86107e8754365124b1871479f766697461f16ce9d847b3c23bb269335588c565` |
| Preserved controller patch SHA256 | `c569a94dd9a0a16c56eefa425263b5be717e77140ef37c7ee18828eeaf2f344f` |

`limine-gamepad.patch` and `upstream/limine-gamepad-tested-v12.9.0.patch` are
identical preserved copies. `limine/` contains the changed files and supporting
upstream headers for review/testing. `reference-headers/` is copied from that
checksum-pinned release: PicoEFI headers retain their `COPYING`, license notice
file and per-file notices; freestanding C headers retain their 0BSD license.
Limine's 0BSD license is `COPYING`; its [third-party acknowledgments](limine/3RDPARTY.md)
describe dependency licenses. No vendored source was changed for publication.

Technical references:

- [UEFI USB support / USB IO protocol](https://uefi.org/specs/UEFI/2.11/17_Protocols_USB_Support.html).
- [Limine 12.9.0 configuration](https://github.com/Limine-Bootloader/Limine/blob/v12.9.0/CONFIG.md)
  and [configuration discovery](https://github.com/Limine-Bootloader/Limine/blob/v12.9.0/common/lib/config.c).
- [Linux xpad wired Xbox 360 reports](https://github.com/torvalds/linux/blob/master/drivers/input/joystick/xpad.c).
- [CachyOS Limine entry management](https://gitlab.com/Zesko/limine-entry-tool).

The original tested build used Clang/LLD 19.1.7 and NASM 2.16.03 in ARM64 Debian.
No compiled EFI image is distributed here. Rebuilds need their own image hash
and physical checks; matching source alone does not imply a byte-identical image.
