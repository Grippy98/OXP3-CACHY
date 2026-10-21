# OXP3 battery charge limit

Exposes the Intel ONEXPLAYER 3 firmware's battery charge limit through Linux's standard battery interface and SteamOS Manager's native battery-limit API. The existing Windows-programmed limit is retained: loading the module or starting/stopping the provider does not request a different percentage.

**Status: kernel backend, persistent deployment, native API and Steam capability discovery tested.** The signed module loaded on `7.2.9-onex3-vrr-test` and exposed the existing Windows-programmed **80%** limit without changing it. Both direct sysfs and real session-bus API write/readback tests passed, including Steam's disabled-limit translation, and the final limit is **80%**. Steam reports charge limiting available with minimum 50%, maximum 100% and default 80%, without a client restart. The service, module override and boot-loading configuration are installed. The existing awake-only bypass setting remained unchanged, and the controller driver stayed loaded. **The Settings → Power control's visual confirmation, physical charging-stop behavior, suspend/resume and reboot verification remain pending.**

The kernel change follows the accepted platform-x86 [OXP3 quirk](https://github.com/kernelorg-mirror/linux_kernel_git_pdx86_platform-drivers-x86/commit/493f34eacd779e6551e5405440008ea5488c22b0), rather than an inferred EC map. No bypass, fan or turbo settings were written during the backend test.

## Components and requirements

| Component | Purpose |
| --- | --- |
| Matching `oxpec` kernel module | Adds OXP3 recognition to the Linux 7.2.9 driver and exposes `charge_control_end_threshold` on the existing battery. |
| `BatteryChargeLimit1` remote provider | Lets native SteamOS Manager relay the control to Steam, with a 50% minimum and correct handling of Steam's disabled-limit value. |

This targets the Intel OXP3 with board vendor `ONE-NETBOOK` and board name `ONEXPLAYER 3`, native CachyOS/Deckify, systemd and SteamOS Manager. The backend test used BIOS **5.08** and the accepted custom Linux 7.2.9 kernel. No full-kernel replacement is required. The module must match the exact running kernel's configuration, generated headers, symbol versions and release; a generic upstream 7.2.9 build or another CachyOS kernel is insufficient.

The current kernel has `CONFIG_OXP_EC` disabled. Building this standalone module requires the matching prepared kernel build tree, not just installed userspace headers. A signed module must use a key trusted by the target kernel when signature enforcement is active. The repository contains source and build instructions, not a compiled module or private signing key.

## Build and install

From the repository root, build against the prepared tree for the exact target kernel:

```sh
bash fixes/battery-charge-limit/build-module.sh \
  "/absolute/path/to/matching/prepared-kernel" \
  "/absolute/new/module-output"
```

The helper uses the included Linux 7.2.9 [driver source](source/oxpec.c) and applies the [accepted quirk patch](patches/0001-oxpec-add-onexplayer3-quirk.patch). It successfully compiled the matching module in a Linux container with `LLVM=-19`; use the compiler/toolchain appropriate for the prepared kernel. Keep the output directory separate from the source. Check the resulting module's `vermagic` against the target kernel and complete required signing with that kernel's trusted key before deployment. No signing key is included.

On the target, as the normal Gaming Mode user:

```sh
sudo bash fixes/battery-charge-limit/install.sh \
  --module "/absolute/path/to/oxpec.ko" --user "$USER"
```

The module argument also accepts `.ko.zst`. Use the generated module from the matching build, not a downloaded module for another release. The installer supplies the root-owned provider, system service, D-Bus policy, SteamOS Manager remote configuration and module-loading configuration. It records previous files and service state beneath `/var/lib/onex3-fixes/charge-limit-install/` and does not restart Steam or the manager automatically.

As the session user, refresh the manager to load the new static remote:

```sh
systemctl --user restart steamos-manager.service
```

The live manager then exposed an 80% battery limit with a 50% suggested minimum while retaining the existing TDP interface. The running Steam client discovered charge limiting and TDP availability without restarting; its charge-limit state reported 50–100% with an 80% default.

## Behavior

Steam's **no limit** value is `-1`; the firmware's normal full-charge value is `100`. The dedicated provider translates between these values. It accepts ordinary limits from 50 through 100 and rejects unsupported values. It does not write zero to represent disabled limiting.

This distinction matters because the generic SteamOS Manager `acpi_sb` path resets the threshold by writing `0`, and `oxpec` passes that byte to the EC unchanged rather than converting it to 100. Zero's firmware behavior was not tested; it is outside the validated/vendor UI range of 50–100. This fix bypasses that generic reset and leaves a preexisting 80% firmware limit intact during discovery, startup, shutdown and rollback. An explicit Steam request is the policy change.

The driver also exposes the existing upstream `charge_behaviour` interface. This fix does not change battery bypass, install fan policy, set TDP, or reset charging when a session starts. A battery reading of 80% is its present state of charge; use `charge_control_end_threshold` to read the programmed ceiling. A threshold below the current charge does not force the battery to discharge.

## Check the result

After installing the matching module, read the battery state without changing it:

```sh
cat /sys/class/power_supply/BAT0/charge_control_end_threshold
cat /sys/class/power_supply/BAT0/charge_behaviour
cat /sys/class/power_supply/BAT0/status
```

The first value should remain the previously programmed limit, such as `80`. Module and provider starts/stops should retain it. Only run an explicit write/restore test after confirming the original value and ensuring that the matching driver is active. Verify physical charging behavior over time; one successful sysfs readback alone does not establish that charging stops at the requested ceiling.

The provider's status command is read-only:

```sh
sudo /usr/bin/python3 /usr/local/lib/onex3-fixes/battery-charge-limit/charge-limit-provider.py status
systemctl status onex3-charge-limit.service
busctl --system introspect org.onex3.SteamOSManager.ChargeLimit /org/onex3/SteamOSManager/ChargeLimit
```

Steam capability discovery passed independently of the still-pending visual check in Settings → Power. Check the kernel threshold again after changing the Steam setting. No Decky plugin is required.

All **26** provider, private-bus and deployment tests passed. They use fake battery files and a private D-Bus daemon and do not change hardware:

```sh
python3 -m unittest discover -s fixes/battery-charge-limit/tests -v
```

Install `python-dbus-next` and provide `dbus-daemon` to run the D-Bus integration tests; those tests are skipped when either dependency is unavailable. Check the output for skips. Fixture tests cover sentinel translation, invalid values and passive lifecycle behavior; the [writeup](WRITEUP.md#validation-status-and-checks) lists the separate hardware checks.

## Rollback and kernel updates

From the repository root:

```sh
sudo bash fixes/battery-charge-limit/rollback.sh
```

Rollback restores recorded configuration/service state and removes this fix's on-disk module override, loading configuration and provider files where they have not been changed later. Later administrator edits are retained as conflicts for review. It does not disable an unrelated SteamOS Manager installation or automatically unload the passive `oxpec` module: other consumers may already use its interfaces. The loaded module remains until a deliberate unload or reboot. Removing the control does not reset the firmware limit; the tested final value is 80%.

Rollback does not restart the manager. Before refreshing it after removal, ensure the generic `acpi_sb` path will not select the still-visible threshold and issue its zero reset; removing the loaded module is a separate decision after checking its consumers. Keep the accepted kernel and boot entries. A kernel update requires a newly built and, where required, signed matching module; do not copy the old `.ko` into the new kernel's module directory. Prefer the distribution's native driver once it includes OXP3 recognition and enables `CONFIG_OXP_EC`.

See [WRITEUP.md](WRITEUP.md) for source attribution, the Steam reset issue and the validation boundary.
