# Rollback and recovery

For an installation made with the root launcher, use its printed backup path:

```sh
./install.sh rollback controllers /var/lib/oxp3-fixes/controllers/BACKUP
```

The equivalent direct command is `sudo bash fixes/oxp3-controller/rollback.sh
BACKUP`. Backups must be restored in reverse order. A repeated no-change install
has no new module/profile changes to undo. The rollback script keeps dependency
packages and backups; it does not reboot or reload an active module.

For a manual package/DKMS installation, first roll back InputPlumber with its
own saved directory (see [its README](../inputplumber/README.md)), then remove
the external driver:

```sh
sudo dkms remove -m hid-oxp-onex3 -v 0.1.4396c18 --all
# If the optional source package was installed:
sudo pacman -R hid-oxp-onex3-dkms
sudo depmod -a "$(uname -r)"
sudo limine-mkinitcpio
modinfo -F filename hid_oxp
```

DKMS should select/restore the stock module. If it cannot, use the original for
that exact kernel from `/var/lib/dkms/hid-oxp-onex3/original_module/`, the
independent `module-path-before` and copied file in your installer backup, or
reinstall that kernel's package. Preserve its original path and compression;
do not substitute another kernel's module. Regenerate initramfs after recovery.
Reboot to load the restored driver.

InputPlumber rollback stops before overwriting later file edits. Save those
edits, then use its direct `rollback.sh BACKUP --force` only if restoring the
older files is intended. If files are restored manually first, also preserve the corresponding backup
and complete the DKMS removal manually rather than replaying its file rollback.
