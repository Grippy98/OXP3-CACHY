# Blank login screen after inconsistent Qt packages

This is a historical package-repair guide, not an OXP3 graphics driver installer. A mixed Qt/Plasma update caused the login manager to require symbols newer than the installed Qt core library. Restoring a coherent signed package set recovered the built-in display and Gaming Mode.

## Diagnose

Check the active login manager and its journal, then inspect package versions and library dependencies:

```sh
systemctl status display-manager
journalctl -b -u display-manager --no-pager
pacman -Q qt6-base qt6-declarative qt6-tools qt6-webengine kwin plasma-workspace
```

A missing `Qt_6.12` symbol with an older Qt core is a package consistency problem. A powered/detected eDP panel does not make the login-manager failure a display-link fault.

## Recovery and verification

Use a coherent repository update, or explicitly select a compatible signed set from the local package cache with `pacman -U`. Keep dependency checks and package hooks enabled. Inspect every selected archive and dependency before downgrading; this repository deliberately does not reproduce the old package list as an installer.

Once corrected, reset the failed login-manager unit and start `display-manager.service`. Confirm both Gaming Mode and the display you use. Resume full upgrades when the repository set is coherent; indefinite partial downgrades are not the fix.

See the [writeup](WRITEUP.md) and [pacman manual](https://man.archlinux.org/man/pacman.8.en). No files or package changes are made by the menu entry.
