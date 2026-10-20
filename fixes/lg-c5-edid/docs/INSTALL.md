# Kernel installation and recovery

The automatic adapter installs only a connector-scoped saved-EDID workaround. The kernel patch requires a manual Linux build and a distribution-appropriate package/boot entry. Keep the distribution kernel and working boot entry installed; preserve its existing root, storage and encryption arguments. Never copy another machine's root UUID, initramfs or boot config.

For a separately named test package, inspect package contents and matching modules before installing it. Rebuild the destination machine's initramfs using its native hooks, verify the generated entry references the matching image/initramfs, and select that entry from the boot menu for a controlled first boot. Do not replace the normal default merely because compilation succeeded. The accepted internal-panel build additionally needs its signed controller module and UHID/UINPUT; see [the complete panel workflow](../../internal-panel-refresh/kernel/README.md).

When testing **native EDID recovery**, remove the connector's saved-EDID override from the test entry so it cannot mask the transport path. Preserve the known-good entry for recovery. To return to prior behavior, boot the retained kernel and disable/remove the test entry/package with the distribution tools. Package removal must happen after booting another kernel.

The saved-EDID workaround writes only its dedicated firmware and config files and regenerates startup files. Its rollback restores the previous files and regenerates startup files again. No live display reprobe or reboot is performed by the adapter. The currently running kernel command line changes only on the next boot; rollback's restored startup state is therefore fully active after reboot.
