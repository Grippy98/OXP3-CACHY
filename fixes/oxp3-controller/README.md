# ONEXPLAYER 3 controllers and RGB

The pinned `hid-oxp` driver fixes X2-family button configuration, rear-paddle
defaults, RGB zones, USB-interface ownership, and suspend/teardown handling.
The accompanying InputPlumber overrides combine the native Xbox controller,
companion keyboard, and vendor HID buttons into one virtual Xbox Elite controller.
Both layers were tested together on an ONEXPLAYER 3 with CachyOS; the owner
confirmed the menu buttons and both rear paddles worked. The reusable installer
is new and has not been executed on another handheld.

## Setup and install

Requires CachyOS on ONE-NETBOOK / ONEXPLAYER 3, an installed CachyOS kernel,
matching kernel headers, and a working package repository. From the repository
root:

```sh
./install.sh list
./install.sh check controllers
./install.sh install controllers
```

The installer requests root through the launcher, installs missing `base-devel`,
`dkms`, `inputplumber`, and the target kernel's header package with `pacman
--needed`, then verifies the headers identify the selected release. Pacman may
ask for confirmation. Repository headers must match the installed kernel; after
a kernel update, boot that kernel or provide its exact headers before continuing.

The default target is `uname -r`. To select another installed CachyOS kernel:

```sh
./install.sh install controllers KERNEL_RELEASE
```

The per-fix equivalent is `sudo bash fixes/oxp3-controller/install.sh
[KERNEL_RELEASE]`. It checks DMI and the driver checksum, installs versioned
sources into `/usr/src/hid-oxp-onex3-0.1.4396c18`, builds through DKMS, regenerates
initramfs, and installs the backed-up InputPlumber overrides. It starts/enables
InputPlumber, which briefly changes the controller exposed to Steam. Matching
DKMS source and active matching profiles are reused. Other source at the same
version causes a refusal instead of replacement. Reboot when ready to load the
new kernel driver; installation does not reload the driver or reboot.

## Verify

```sh
modinfo -F filename hid_oxp
modinfo -F vermagic hid_oxp
cat /sys/module/hid_oxp/srcversion
ls /sys/class/leds/oxp:*
systemctl is-active inputplumber.service
inputplumber devices list
```

After reboot, the driver path should use `updates/dkms/` for the running kernel.
The tested source version was `84DBD8A4A7B20A3D712F884`; compiler/configuration
changes may alter it. Expected LED names are `oxp:rgb:joystick_rings`,
`oxp:rgb:guide_button`, and `oxp:rgb:rear_logo`.

In Steam Gaming Mode, test sticks, triggers, front buttons, each rear paddle,
ONEX/Quick Access, keyboard and Home shortcuts, reconnect, and suspend/resume.
The tested keyboard/Home route is Guide + North; ONEX is Guide + A. Cached
sysfs mapping values or an active service alone do not establish physical input.

## Rollback

Use the exact backup directory printed by the installer:

```sh
./install.sh rollback controllers /var/lib/oxp3-fixes/controllers/BACKUP
```

Rollback restores that run's InputPlumber files/service state and removes the
DKMS override only when that run installed it. DKMS restores its saved original
module. Initramfs is regenerated; reboot to activate the restored driver.
Packages and private backups remain. Restore in reverse installation order if
you have several backups; later changes to InputPlumber files cause a refusal.
See [rollback details](docs/ROLLBACK.md) for manual recovery.

## Sources and limits

- [Technical writeup](WRITEUP.md) and [driver source pins/licensing](kernel/SOURCES.md).
- [Build and packaging](docs/BUILD.md), [installation details](docs/INSTALL.md).
- [InputPlumber profile, controls and limitations](inputplumber/README.md).

The kernel driver is pinned to [OGC PR 13](https://github.com/OpenGamingCollective/linux-unstable/pull/13)
commit `4396c18eef297543889681a77283c13e047dfe22`; it is an external module,
not a promise that the current stock kernel needs the same override. Review
upstream support before replacing a newer driver. Kernel API changes can
require rebasing, and each installed target needs matching headers. Custom
headerless kernels are outside the installer. Secure Boot needs a DKMS signing
key trusted by that installation. No prebuilt kernel module is distributed.
