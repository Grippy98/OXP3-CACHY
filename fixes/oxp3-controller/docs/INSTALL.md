# Installation details

The [main README](../README.md) provides the supported installation command.
`install.sh [KERNEL_RELEASE]` targets the running kernel unless another installed
CachyOS release is supplied; `install.sh --check [KERNEL_RELEASE]` checks without
root or writes. Checks report missing prerequisites rather than installing them.

State and an independent copy of the module selected before installation are
saved under `/var/lib/oxp3-fixes/controllers/BACKUP/`. DKMS also tracks its own
original module. The versioned source directory is
`/usr/src/hid-oxp-onex3-0.1.4396c18`; DKMS output goes into the selected kernel's
`updates/dkms/` directory. Initramfs is regenerated using `limine-mkinitcpio`
when available, otherwise `mkinitcpio -P`.

InputPlumber's three `/etc` overrides and service state are backed up separately
under `/var/lib/oxp3-fixes/inputplumber/`; the wrapper records that backup when
it creates one. A matching active installation is reused. Build failures attempt
to remove only the newly registered/installed override and regenerate initramfs.
Dependency packages remain installed after a failure or rollback.

The new installer has only undergone host syntax/review checks. The driver and
profiles themselves were physically tested together on CachyOS. A successful
DKMS build does not prove input, RGB, or suspend/resume behavior on another
firmware/kernel version. Use the physical checks in the main README.
