# Rollback

From this directory:

```sh
sudo ./rollback.sh tdp
sudo ./rollback.sh permissions
```

Each command restores only the installation recorded by its own installer, including replaced files and previous service enable/running state. Backups remain under `/var/lib/onex3-fixes/`. Changed files, symlinks and service enable links are retained and reported for review. An existing manual installation must use its own original backups; installing over it cannot recover an earlier stock state.

The TDP rollback requires a successful provider stop before removing its source or integration. Stopping restores that process's fresh RAPL baseline. A crash or SIGKILL cannot run cleanup; inspect the journal and current constraints before restarting a failed provider. Remove activation and manager integration together through the rollback script, since a disabled unit can still be activated by D-Bus.

The permissions rollback first removes its udev rule, reloads rules and waits for queued events, then stops the helper to restore same-boot group/mode values. Later administrator permission changes are retained.

For the optional MangoHud package, reinstall the original distribution package(s) saved before replacement with `sudo pacman -U /path/to/original.pkg.tar.zst`. Review pacman's proposed transaction, then restart MangoApp or the gaming session. Source builds only stage files and need no system rollback. Keep dependency packages that other software still uses.
