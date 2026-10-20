# Gaming Mode power button

The native CachyOS `steamos-powerbuttond` handler restored short-press sleep and wake on the Intel OXP3. It supplies the userspace action that was missing while logind ignored the button. The fix uses the distribution package; it does not change logind policy or install a custom input daemon.

## Install and check

From the repository root, as the Gaming Mode user:

```sh
./install.sh check power-button
./install.sh install power-button
```

The adapter installs the native package if needed, refreshes hwdb/udev properties, and starts the user unit when Gaming Mode is active. Otherwise its packaged session dependency starts it on the next Gaming Mode login. It records prior package presence, version and user-unit activity in `/var/lib/oxp3-cachy/power-button/`.

Briefly press power, wait for suspend, then wake. Inspect `systemctl --user status steamos-powerbuttond.service` and its journal if it cannot find a readable tagged button.

## Rollback

```sh
./install.sh rollback power-button
```

A preexisting package is retained and its prior daemon activity restored. A package added by this installer is removed only while its recorded version still matches. Changed versions require explicit package review. Neither action reboots.

The handler's short-press behavior was hardware tested. Long-press routing comes from the pinned source; revised packaging is covered by review/syntax checks rather than a new device deployment. See [the writeup](WRITEUP.md) and [upstream proposal](upstream/README.md).
