# Battery charge control: firmware, kernel and Steam

## Why the Windows setting survives but Linux has no control

The OXP3 firmware can retain a charge ceiling set by OneXConsole across operating-system changes. That does not require a Linux control service to keep rewriting it. The missing Linux `charge_control_end_threshold` attribute is a driver-support problem, separate from the current battery percentage or the persistence of that firmware setting.

The accepted custom CachyOS kernel is based on Linux 7.2.9 and has `CONFIG_OXP_EC` disabled. Its existing controller HID driver handles a different interface; loading `hid_oxp` does not expose the motherboard's battery charge control. HHD/Adjustor also expects the standard kernel battery attributes and cannot create them by itself.

## Source and backport scope

The upstream platform-x86 change is [commit `493f34eacd779e6551e5405440008ea5488c22b0`](https://github.com/kernelorg-mirror/linux_kernel_git_pdx86_platform-drivers-x86/commit/493f34eacd779e6551e5405440008ea5488c22b0), **platform/x86: oxpec: Add OneXPlayer 3 quirk**. Antheas Kapenekakis authored it; Derek J. Clark and Ilpo Järvinen reviewed it; Ilpo signed it into the maintainer integration tree. The [original submission](https://patch.msgid.link/20260920190438.3444923-2-lkml@antheas.dev) reports battery bypass, capacity limits, fan curves, fan tachometer and turbo override confirmed on OXP3.

The patch adds seven lines: a `ONE-NETBOOK` board-vendor match and exact `ONEXPLAYER 3` board-name match selecting the existing `oxp_g1_i` handling. [source/oxpec.c](source/oxpec.c) retains the unpatched Linux 7.2.9 driver, whose SHA256 is `161fa21f5bd4e332914880dff780224a17a0ee4a0c94c467069b6555885974e3`, and [the quirk patch](patches/0001-oxpec-add-onexplayer3-quirk.patch) carries this recognition change. The build helper applies it to a separate build copy. This integration does not import a new family-wide EC map, replace the full kernel or add a raw EC userspace writer. The retained Linux source carries its GPL-2.0-or-later notice and original author credits.

The existing G1 Intel handler reads/writes the limit at EC offset `0xA3`. The bypass register is `0xA4`: 0 means automatic charging, 1 inhibits charging while awake, and 3 inhibits it in all states supported by that firmware. The kernel exposes these through a battery power-supply extension, using `charge_control_end_threshold` and `charge_behaviour`. Device registration and removal do not set a limit or install a fan curve. No policy daemon is needed merely to preserve an already programmed 80% ceiling.

Windows reverse-engineering documentation for OneXConsole's Intel G3E family corroborates `0xA3`/`0xA4`, but its direct tests were on a related X2 Mini. This backport relies on the maintainer-reviewed OXP3 quirk rather than treating a shared product-family table as hardware validation. Banked Windows WMI addresses must not be copied directly into Linux's 8-bit EC API.

## Standalone module and build identity

Build `oxpec.ko` against the exact prepared tree that produced the running kernel: matching configuration, generated files, exported symbol versions and kernel release are all necessary. This allows a module-only change while preserving the accepted graphics, controller and boot configuration. An arbitrary 7.2.9 source archive or headers from the distribution's current kernel do not reproduce that ABI.

`build-module.sh KERNEL_BUILD_DIR OUTPUT_DIR` builds a standalone module without rebuilding or replacing the kernel. The reusable helper successfully compiled the real matching module in a Linux container with `LLVM=-19`. The module must also meet the running kernel's signature policy. Sign with an appropriately trusted build key when required; do not publish that private key or disable enforcement as part of this fix. `install.sh --module /absolute/oxpec.ko --user SESSION_USER` deploys the matching artifact and userspace integration. Retain the source identity and build instructions alongside the module deployment record. Compiled `.ko` files and private build/signing material are excluded from this repository.

## Dedicated native Steam provider

`charge-limit-provider.py` implements SteamOS Manager's `BatteryChargeLimit1` interface with `MaxChargeLevel` and `SuggestedMinimumLimit` properties; the suggested minimum is 50%. Steam uses `-1` to disable a limit; the OXP3 firmware uses a 100% threshold for normal full charging. The provider translates `-1` to `100` on an explicit write and reports a raw `100` as `-1`. Ordinary values below 50% or above 100% are rejected.

The root-owned system service is `onex3-charge-limit.service`. It owns the system-bus name `org.onex3.SteamOSManager.ChargeLimit` and object `/org/onex3/SteamOSManager/ChargeLimit`; SteamOS Manager consumes it through the dedicated `remotes.d/onex3-charge-limit.toml` configuration. The D-Bus policy is rendered for the selected session user. Deploy through the installer rather than copying unrendered `rootfs` templates over the live system. The provider's `status` and `check` commands inspect state without setting a threshold; `serve` runs the D-Bus service.

The generic SteamOS Manager `acpi_sb` reset path writes `0` to the kernel threshold. The `oxpec` setter accepts and passes that value directly to the EC; it does not translate it into a 100% reset. Firmware handling of zero remains untested, and zero lies outside the validated/vendor UI range of 50–100. This fix routes Steam through the dedicated remote instead of that unvalidated reset path. Starting, discovering, stopping or removing the provider does not write an initial default, restore a guessed value, or undo the owner's existing Windows setting. A deliberate user request changes the ceiling.

The integration uses Steam's native control rather than another overlay. SteamOS Manager's user daemon must restart to read a new static remote configuration. The running Steam client discovered this deployment without restarting. Changes to the native manager, its remote protocol or startup sequence require another integration check, particularly to ensure that a generic provider does not write zero before the dedicated remote is selected.

## Validation status and checks

**The kernel backend passed a live read/write/restore test on BIOS 5.08.** A signed module built from the pinned 7.2.9 source plus the accepted quirk loaded on the running `7.2.9-onex3-vrr-test` kernel. The new `BAT0/charge_control_end_threshold` attribute immediately read **80**, preserving the setting previously programmed in Windows. An explicit write of **75** read back **75**; cleanup restored **80**, which read back **80**. The existing `charge_behaviour` selection stayed `inhibit-charge-awake`, and `hid_oxp` remained loaded. No bypass, fan or turbo writes were made.

The installer subsequently deployed the matching on-disk module override, module-loading configuration and root-owned provider/configuration, and enabled `onex3-charge-limit.service`, without changing 80%. After the session's SteamOS Manager restarted, its native session-bus interface exposed `BatteryChargeLimit1` with `MaxChargeLevel=80` and `SuggestedMinimumLimit=50`. The preexisting `TdpLimit1` interface remained at 25 W with its 8–40 W range.

Real writes through that session-bus battery interface were verified: a request for 75 produced firmware/API readbacks of 75; a request for `-1` produced firmware 100 and API `-1`; cleanup restored firmware/API 80. The awake-only bypass selection remained unchanged. This establishes the native manager relay and sentinel translation, rather than only a direct call to the private provider. The final configured limit is **80%**.

The installed Steam client's own native power-state query subsequently reported charge limiting available, minimum 50, maximum 100 and default 80, with TDP also available. No Steam client restart was needed. This verifies Steam capability discovery separately from the D-Bus checks; the owner's visual confirmation of the Settings → Power control is still pending.

Persistent deployment is installed, but reboot persistence has not yet been tested. Physical charging-stop behavior and suspend/resume also remain unverified. Attribute/API readback and Steam capability discovery do not establish those separate results.

Remaining checks:

1. Confirm Settings → Power displays the native control and the existing value. Steam's capability discovery and the manager's live API are already verified independently of this visual check.
2. Recheck after suspend/resume and reboot; firmware can independently affect persistence.
3. Observe charging-stop/resume behavior separately. The existing awake-only bypass inhibits charging while awake, so retain it unless a separate deliberate test requires changing it; do not conflate bypass with the charge-ceiling result.
4. Verify a full live rollback without changing the selected threshold or unrelated Steam, controller, display, fan and TDP behavior.

All **26** automated tests passed: 20 provider/private-bus tests with `dbus-next` and `dbus-daemon` available, plus six deployment fixtures. The fixtures cover range handling, sentinel translation, explicit D-Bus writes, passive lifecycle behavior, deployment baselines and preservation of later administrator edits. The native session-bus relay was tested separately on hardware as described above. Neither fixture tests nor API readback replace a physical charging stop/resume test.

Rollback restores recorded files and service state from `/var/lib/onex3-fixes/charge-limit-install/`, preserves later edits as conflicts, and removes this fix's on-disk module override and loading configuration. It deliberately retains an already loaded passive `oxpec` module to avoid disrupting unknown consumers. Unloading it is a separate deliberate action, or it disappears on reboot when no remaining configuration/consumer loads it. Rollback does not write a threshold, restore a guessed factory default or restart the manager. Before a later manager refresh, account for the generic `acpi_sb` zero-reset behavior if the threshold remains visible without its dedicated remote. Keep raw firmware captures, device identifiers, logs, keys and compiled modules outside this source folder.

## Long-term direction

CachyOS should enable `CONFIG_OXP_EC` and include the accepted OXP3 DMI quirk, making the standalone backport unnecessary. Preserve the standard power-supply API so existing battery-control software can consume it. The generic SteamOS Manager reset behavior also needs an OXP-compatible correction or a properly selected remote backend; merely adding the kernel attribute must not introduce an unvalidated automatic zero write. Upstream model recognition, distribution configuration and userspace reset semantics are separate changes with separate validation.
