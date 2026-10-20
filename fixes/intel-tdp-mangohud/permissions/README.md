# Read-only Intel telemetry access

This helper grants the existing `video` group read access to three narrowly selected OXP3 sensor files: MSR RAPL `package-0/energy_uj`, its named `uncore/energy_uj`, and the Intel PMT endpoint with GUID `0x03086000` and size 3352. It checks ONE-NETBOOK ONEXPLAYER 3 DMI, resolves actual sysfs paths, and applies `root:video 0440`. RAPL power-limit write permissions stay unchanged.

From this directory on the Linux device:

```sh
python3 -m unittest discover -s tests -v
sudo ./install.sh
```

Requires Python 3, systemd/udev, and the existing `video` group. The installer checks matching sensors before deployment, backs up its three destination files and previous service state under `/var/lib/onex3-fixes/metrics-install/`, and enables the oneshot service. The desktop user must already belong to `video`; group changes require a new login session and are managed separately. No MangoHud package is installed by this command. Keep this complete fix group together when running the installer: it reuses the sibling TDP deployment safety helpers. The installed permission runtime has no TDP dependency.

The service applies at boot and stays active so `ExecStop` can restore its snapshot. Matching udev add events invoke the same locked helper. The private runtime state under `/var/lib/onex3-metrics-permissions/` records boot ID and first group/mode baseline. A previous boot's snapshot is never applied to new sysfs nodes. Apply failures undo that invocation's completed and intermediate changes; later administrator attribute changes are retained.

```sh
sudo ./rollback.sh
```

Rollback removes its matching udev rule, reloads rules and waits for queued events before stopping the service. It then restores recorded files, enable links and service state. Changed files are retained as conflicts; backup records remain available. An installation made outside these scripts requires its own original backups. SIGKILL cannot run immediate cleanup; inspect the retained runtime snapshot if restoration fails.

Tests use temporary files and mocked ownership; they never touch host sysfs. PMT schema and license attribution are in [telemetry credits](../telemetry/CREDITS.md).
