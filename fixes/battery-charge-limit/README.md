# OXP3 battery charge limit and bypass

Exposes the Intel ONEXPLAYER 3 firmware's battery charge ceiling through Linux's standard battery interface and SteamOS Manager's native battery-limit API. A separate optional **OXP3 Charge Controls** Decky panel selects charging behavior: Auto, Bypass while awake or Bypass always. Loading the module or starting/stopping either control does not change the existing ceiling or bypass mode.

**Status: installed and backend-tested; visual confirmation pending.** The signed module loaded on `7.2.9-onex3-vrr-test`, preserved the Windows-programmed 80% limit, and passed sysfs and real session-bus write/readback tests. Steam discovered the 50–100% ceiling control without restarting. The service, module override, boot-loading configuration and Decky panel are installed. The live Decky backend reads the selected mode and ceiling, rejects invalid modes, and successfully reselects the existing awake-only bypass without changing either setting. Settings → Power and panel visibility, physical charging behavior, suspend/resume and reboot verification remain separate checks.

**Current requested state: 100% ceiling with Bypass while awake retained.** Raising the ceiling does not cancel bypass: this combination still inhibits charging while the device is awake. The two settings are independent.

The kernel change follows the accepted platform-x86 [OXP3 quirk](https://github.com/kernelorg-mirror/linux_kernel_git_pdx86_platform-drivers-x86/commit/493f34eacd779e6551e5405440008ea5488c22b0), rather than an inferred EC map. No bypass, fan or turbo settings were written during the backend test.

## Components and requirements

| Component | Purpose |
| --- | --- |
| Matching `oxpec` kernel module | Adds OXP3 recognition to the Linux 7.2.9 driver and exposes `charge_control_end_threshold` on the existing battery. |
| `BatteryChargeLimit1` remote provider | Lets native SteamOS Manager relay the control to Steam, with a 50% minimum and correct handling of Steam's disabled-limit value. |
| Optional OXP3 Charge Controls panel | Selects a supported bypass mode through a separate provider interface; the native Steam ceiling control remains independent. |

This targets the Intel OXP3 with board vendor `ONE-NETBOOK` and board name `ONEXPLAYER 3`, native CachyOS/Deckify, systemd, SteamOS Manager and `python-dbus-next`. The backend test used BIOS **5.08** and the accepted custom Linux 7.2.9 kernel. No full-kernel replacement is required. The module must match the exact running kernel's configuration, generated headers, symbol versions and release; a generic upstream 7.2.9 build or another CachyOS kernel is insufficient.

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

The module argument also accepts `.ko.zst`. Use the generated module from the matching build, not a downloaded module for another release. The installer supplies the root-owned provider, system service, D-Bus policy, SteamOS Manager remote configuration and module-loading configuration. It records previous files and service state beneath `/var/lib/onex3-fixes/charge-limit-install/` and checks that the threshold and any available bypass mode survive module/provider startup. An unexpected change aborts installation without issuing a firmware restore write. It does not restart Steam or the manager automatically.

As the session user, refresh the manager to load the new static remote:

```sh
systemctl --user restart steamos-manager.service
```

The live manager then exposed an 80% battery limit with a 50% suggested minimum while retaining the existing TDP interface. The running Steam client discovered charge limiting and TDP availability without restarting; its charge-limit state reported 50–100% with an 80% default.

## Behavior

Steam's **no limit** value is `-1`; the firmware's normal full-charge value is `100`. The dedicated provider translates between these values. It accepts ordinary limits from 50 through 100 and rejects unsupported values. It does not write zero to represent disabled limiting.

This distinction matters because the generic SteamOS Manager `acpi_sb` path resets the threshold by writing `0`, and `oxpec` passes that byte to the EC unchanged rather than converting it to 100. Zero's firmware behavior was not tested; it is outside the validated/vendor UI range of 50–100. This fix bypasses that generic reset and leaves the existing firmware limit intact during discovery, startup, shutdown and rollback. An explicit Steam request is the policy change.

The driver also exposes the existing upstream `charge_behaviour` interface. The ceiling API never changes it. The optional panel offers only modes reported by the kernel:

| Mode | Kernel value | Behavior |
| --- | --- | --- |
| Auto | `auto` | Allow firmware-controlled charging up to the selected ceiling when charging conditions permit. |
| Bypass while awake | `inhibit-charge-awake` | Inhibit charging while awake; charging can resume during sleep/shutdown according to firmware policy. |
| Bypass always | `inhibit-charge` | Request charging inhibition across the firmware's supported power states. |

Choosing a mode is an explicit action. Starting, reloading or removing the panel/provider does not select Auto, change the ceiling or restore a guessed mode. Auto permits charging; it does not guarantee an immediate charging rate. Physical behavior across power states has not been independently verified here. No fan policy or TDP changes are part of this fix.

A battery reading of 80% is its present state of charge; use `charge_control_end_threshold` to read the programmed ceiling. A threshold below the current charge does not force the battery to discharge. At a 100% ceiling, no charging while awake can be expected if Bypass while awake remains selected.

## Optional Decky bypass panel

The native Steam ceiling control works without this panel. Install the provider from this folder first; its D-Bus introspection must include `org.onex3.ChargeBehaviour1`. The panel also requires Decky Loader, Python 3 and `busctl` on the target. Its backend runs without Decky's root flag and requests only a supported mode from the provider.

Build with Node.js and pnpm from the panel source directory:

```sh
cd fixes/battery-charge-limit/decky
pnpm install --frozen-lockfile --ignore-scripts
pnpm typecheck
pnpm test
pnpm build
python3 package.py /absolute/new/OXP3-Charge-Controls.zip
```

Choose a new absolute ZIP filename outside the source directory. The archive contains the complete `OXP3-Charge-Controls` plugin, including its built frontend and Python backend. On the target, use Decky's **Install Plugin from ZIP/URL** action to select that ZIP. Keep any existing same-name plugin backup outside Decky's plugin directory before replacing it.

Open **Decky → OXP3 Charge Controls** to select **Auto**, **Bypass while awake** or **Bypass always**. The panel displays the ceiling read-only; change that separately in Steam Settings → Power. It reports an unavailable provider/mode rather than silently enabling charging. Installing, opening, reloading or removing it does not change either setting.

To remove only the panel, uninstall **OXP3 Charge Controls** in Decky. Leave the provider, module and native ceiling integration installed. If deploying by manual extraction instead of Decky's installer, reload the plugin through Decky after replacing its complete payload; do not restart Steam merely to update this panel. The panel's **10 backend tests, TypeScript check and production build passed**. The installed plugin was reloaded independently, and its real Decky callable returned all three modes, the awake-only selection, a 100% ceiling and the battery's separate 80% charge reading. Visual confirmation remains pending; live selection of Auto/Bypass always and physical charging were not tested through the panel.

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

Steam capability discovery passed independently of the still-pending visual check in Settings → Power. Check the kernel threshold again after changing the Steam setting. The native ceiling control does not require Decky; the optional panel supplies the separate bypass selector.

All **44** provider, private-bus and deployment tests passed, including seven private-bus tests. They use fake battery files and a private D-Bus daemon and do not change hardware:

```sh
python3 -m unittest discover -s fixes/battery-charge-limit/tests -v
```

Install `python-dbus-next` and provide `dbus-daemon` to run the D-Bus integration tests; those tests are skipped when either dependency is unavailable. Check the output for skips. Fixture tests cover sentinel translation, invalid values and passive lifecycle behavior; the [writeup](WRITEUP.md#validation-status-and-checks) lists the separate hardware checks.

## Rollback and kernel updates

From the repository root:

```sh
sudo bash fixes/battery-charge-limit/rollback.sh
```

Rollback restores recorded configuration/service state and removes this fix's on-disk module override, loading configuration and provider files where they have not been changed later. Later administrator edits are retained as conflicts for review. It does not disable an unrelated SteamOS Manager installation or automatically unload the passive `oxpec` module: other consumers may already use its interfaces. The loaded module remains until a deliberate unload or reboot. Removing the control does not reset either firmware setting; the current requested state is 100% with Bypass while awake.

A recorded provider rollback and reinstall were exercised on the device, retaining the loaded module and preserving 100% plus awake-only bypass before and after installation.

Rollback does not restart the manager. Before refreshing it after removal, ensure the generic `acpi_sb` path will not select the still-visible threshold and issue its zero reset; removing the loaded module is a separate decision after checking its consumers. Keep the accepted kernel and boot entries. A kernel update requires a newly built and, where required, signed matching module; do not copy the old `.ko` into the new kernel's module directory. Prefer the distribution's native driver once it includes OXP3 recognition and enables `CONFIG_OXP_EC`.

See [WRITEUP.md](WRITEUP.md) for source attribution, the Steam reset issue and the validation boundary.
