# Steam TDP integration

This root-owned Python provider implements SteamOS Manager's supported system-bus remote interface. The session manager relays it to Steam. It discovers `package-0` PL1 (`long_term`) and PL2 (`short_term`) by name in both `intel-rapl` and `intel-rapl-mmio`, writes all four controls, verifies readback, and restores prior values after a partial failure. It leaves time windows, enabled flags and unrelated domains alone.

The configured slider is 8–40 W: 8–35 W is the manufacturer's normal advertised range and 40 W is an optional endpoint on the [Japanese product page](https://www.onexplayer.online/onexplayer-3). Change policy deliberately in `rootfs/etc/onex3-tdp.json` before installation. Sysfs nominal maximum attributes are not used as the slider ceiling.

## Install

Use native x86-64 CachyOS/Arch with systemd, `steamos-manager` and `python-dbus-next` already installed. This integration was developed for SteamOS Manager 26.4.1. Its remote TDP interface and service layout must remain compatible; the installer checks the native executable and logged-in user bus. Keep the existing controller integration.

From this directory, as the desktop user:

```sh
python3 -m unittest discover -s tests -v
sudo ./install.sh --session-user "$USER"
```

The installer also accepts `$SUDO_USER` as its default session user. Running directly from a root shell requires `--session-user NAME`. It renders the configuration and D-Bus policy together; do not deploy the source templates by copying `rootfs` over `/`.

Before changing anything it checks device DMI, both RAPL domains, required executables, Python dependency and safe root-owned destination parents. It snapshots all eight payload files, existing symlinks, service enable links and active state under `/var/lib/onex3-fixes/tdp-install/`, then enables the provider and session manager. Starting captures a fresh hardware baseline and requests no watts. Restart Steam afterward to discover the remote.

## Behavior and checks

The manager drop-in pauses an existing provider before manager setup and activates a fresh provider after manager readiness. A separate `org.onex3.PowerControlActivator` bus name prevents a startup cycle: the actual TDP bus name stays non-activatable. The vendor manager executable is preserved.

```sh
sudo /usr/bin/python3 /usr/local/lib/onex3-fixes/tdp/onex3_tdp.py status
sudo systemctl status onex3-tdp.service
busctl --system introspect org.onex3.SteamOSManager.PowerControl /org/onex3/SteamOSManager/PowerControl
```

After selecting a value in Steam, all four package constraints should agree within hardware readback quantization. `status` only reads. Stopping `onex3-tdp.service` restores the baseline captured by that provider process. Steam's `TdpLimit1` exposes value/min/max, with no checkbox flag or restore method; a client may implement an unchecked box by requesting the maximum.

Private D-Bus integration tests require `dbus-daemon` and `dbus_next`; they use fake RAPL files and do not change hardware:

```sh
python3 tests/run_dbus_test.py
python3 tests/run_activation_test.py
```

## Remove

```sh
sudo ./rollback.sh
```

Rollback first requires successful provider cleanup, then restores the recorded files and previous service state. Files or enable links changed later are retained as conflicts. Backups remain for inspection. An active installation record prevents reinstalling over its baseline. A previously manual deployment requires its own backup; the installer cannot reconstruct stock files that were replaced before it ran.

Abrupt process termination cannot restore limits. Inspect a failed provider's journal and constraints before starting it again, since each new instance intentionally captures a new baseline. Firmware resume/shutdown can independently reset limits; this provider does not poll firmware or issue EC commands.

Sources: [Valve remote example](https://gitlab.steamos.cloud/holo/steamos-manager/-/blob/v26.4.1/steamos-manager/examples/basic_remote.rs), [Valve TDP API](https://gitlab.steamos.cloud/holo/steamos-manager/-/blob/v26.4.1/data/interfaces/com.steampowered.SteamOSManager1.xml), [Linux powercap ABI](https://docs.kernel.org/power/powercap/powercap.html), [ONEXPLAYER global page](https://onexplayerstore.com/products/onexplayer-3-next-gen-3-in-1-ai-gaming-and-productivity-handheld). See [upstream plan](UPSTREAM-PLAN.md).
