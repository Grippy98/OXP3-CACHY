# Controller input in the Limine boot menu

This opt-in Limine 12.9.0 patch lets the ONEXPLAYER 3's built-in controller select
an OS before Linux starts. Native navigation, selection and a successful CachyOS
boot were physically tested on the owner's handheld. The preserved bootloader
patch and test sources are unchanged. Packaging scripts have since been made
reusable; the revised deployment scripts have host checks but have not been
rerun on a handheld.

## Controls and implementation

D-pad Up/Down or the left stick moves selection. A boots; B/Left collapses a
directory or selects its parent; Right expands directories. A/B need a fresh
press after neutral input. Keyboard/mouse remain available, and entry editing
requires a keyboard.

The adapter accepts the tested USB `045e:028e`, interface `ff/5d/01`, interrupt IN
endpoint `0x81`, using firmware USB IO and wired Xbox 360 reports. It validates
ownership and descriptors, buffers short presses, repeats only navigation,
preserves the autoboot deadline, and cancels callbacks before handoff. Failed
cancellation blocks handoff instead of unloading live callback code. See the
[technical writeup](WRITEUP.md), [proposal](upstream/PROPOSAL.md), and [source pins](SOURCES.md).

## Build

Requires Docker, curl, patch, tar and shasum. From this folder:

```sh
bash build.sh
bash tests/run-state-tests.sh
bash tests/run-firmware-tests.sh
bash tests/run-wait-tests.sh
```

The recipe verifies the pinned release archive, applies `limine-gamepad.patch`,
and builds x86-64 UEFI with Clang/LLD 19 in Debian. Output is `build/BOOTX64.EFI`
and its checksum; `bash build.sh OUTPUT_DIRECTORY` selects another destination.
The fresh Docker recipe was not rebuilt during publication preparation.
`limine/` is a source subset for review/host tests, not a complete build tree.
Vendored headers and licenses are retained for offline testing.

## Check and stage a one-time test

The reusable deployment scripts target CachyOS with a FAT EFI system partition
mounted at `/boot`, stock `/boot/EFI/limine/limine_x64.efi`, and live
`/boot/limine.conf`. They require Linux UEFI, the OXP3 DMI identity,
`efibootmgr`, util-linux tools, Python 3, and disabled Secure Boot for this
unsigned build. From the repository root:

```sh
./install.sh list
./install.sh check boot-controller
./install.sh install boot-controller /absolute/path/to/BOOTX64.EFI
```

The installer validates PE architecture and checksum, saves private backups under
`/var/lib/onex3-boot-controller/backups/`, and creates a separate firmware entry
pointing to `/boot/EFI/limine-oxp3-controller/BOOTX64.EFI`. A sibling test menu
copies your current entries/default, enables gamepad input and disables autoboot.
The stock loader/configuration, BootOrder and BootNext remain unchanged. Repeating
the same recorded image is a no-op; conflicting/incomplete state is refused.
An adjacent `.sha256` is checked when present; an explicit expected SHA256 can
also be supplied after the image path.

Use the entry ID printed by the installer to opt into the next boot:

```sh
sudo efibootmgr --bootnext XXXX
sudo systemctl reboot
```

The installer never schedules BootNext, promotes the loader, or reboots. Firmware
consumes the one-time request before launch, so the ordinary boot order remains
your fallback. Test navigation, held buttons, directory controls, A to Linux,
and input in Steam after boot. A different firmware may not expose this USB IO
interface even when Linux sees the controller.

## Optional normal use and rollback

Only after booting through this loader and confirming the controls, run:

```sh
sudo bash fixes/boot-controller/promote-default.sh
```

Promotion discovers the unique active stock Limine entry on the current ESP;
no firmware entry number or kernel entry name is hardcoded. It verifies the
recorded image and BootCurrent, preserves the existing nonzero menu countdown
(or `timeout: no`), enables global `gamepad: yes`, removes the test-only sibling
menu, and places the custom entry first. The custom loader then reads live
kernel entries. Promotion remains a separate manual operation.

If promoted, restore the stock default first:

```sh
./install.sh rollback boot-controller
```

Then remove the staged entry/files through the root dispatcher:

```sh
./install.sh rollback boot-controller --remove
```

Rollback preserves backups, unrelated firmware entries and newer kernel entries;
it retains a gamepad setting edited since promotion. No helper reboots.

## Status and limitations

The decoder, firmware ownership and input-wait host suites passed, including
ASan/UBSan. Existing QEMU scenes cover selection, disabled input, idle autoboot
and directory navigation; see [test instructions](tests/README.md). Firmware
coverage is limited to the physically tested OXP3 and x86-64 UEFI. Transfer-error
reconnection and Secure Boot deployment are not implemented. Stock Limine package
updates do not update this separate image: adoption of a newer release needs a
rebase, rebuild and tests. The patch has not been accepted upstream; the
[upstream review notes](upstream/README.md) describe the remaining work.
