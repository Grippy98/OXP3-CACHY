# OXP3 SteamOS fix-pack audit

Do not run the whole installer on this CachyOS setup. Use it as evidence of possible symptoms; independently validate and implement narrowly scoped fixes.

Audited 2026-10-07. Repository HEAD: [`ea371b357b8b`](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/tree/ea371b357b8ba6467e00c0be372e1c86c1ac523b). Release v1.6.1 resolves to `48848b9230cca4978545de35d8aa9d40a9fca3cb`; only README differs from HEAD. Scope includes the complete installer, standalone volume proxy, reference YAML, desktop entries, issue drafts, SSDT source, gyro patch and release contents. No installer, proxy, binary or MCU operation was executed.

The author’s logs are useful leads. They do not establish that the same symptom or cause is present on this unit. Findings marked source inference follow from code paths and upstream semantics; they have not been reproduced by installing the pack.

## Applicability

Use the independently maintained controller, bootloader, TDP/metrics and display folders in this collection. NVMe, gyro, battery, volume, firmware and HDR changes require their own exact hardware match and reproduced symptom. The reviewed SteamOS installer must not be run wholesale on CachyOS/Limine.

## Implementation findings

### A01 — Root services execute files owned by the desktop user (high)

Volume, battery and TDP units, and the gyro InputPlumber drop-in, execute scripts or a binary under ~/oxp3-fix as root. The installer writes these as the normal user. A user or compromised user process can edit those files and gain root when a service starts or restarts; initial download hashes do not protect later execution.

Recommended: Use root-owned executable paths with root-owned parent directories, verify ownership and symlink safety, and separate non-executable user settings. Limit each service to the permissions it needs.

Source: [oxp3-apply-fixes.sh:111–125](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L111-L125), [oxp3-apply-fixes.sh:371–375](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L371-L375), [oxp3-apply-fixes.sh:468–469](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L468-L469), [oxp3-apply-fixes.sh:670–671](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L670-L671), [oxp3-apply-fixes.sh:710](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L710), [oxp3-apply-fixes.sh:1290](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L1290). Verified by source inspection.

### A02 — Revert removes existing configuration and disables a shared controller service (high)

Apply overwrites named InputPlumber, gamescope and module files without saving prior contents, ownership or service state. Revert deletes these names and disables InputPlumber globally. On this device that can remove working controller support rather than restore the starting configuration. Firmware files, read-only-root state and MCU state are not restored.

Recommended: Snapshot existing files and service state before a transaction. Restore only owned changes, compare hashes before removal, and preserve the previously active controller service.

Source: [oxp3-apply-fixes.sh:1064–1081](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L1064-L1081), [oxp3-apply-fixes.sh:1392–1411](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L1392-L1411). Verified by source inspection.

### A03 — The flag needed for CachyOS also bypasses gyro hardware safeguards (high)

The OS guard rejects CachyOS. --force skips that guard and also accepts any BIOS version and InputPlumber series for the full SSDT override and 0.78 fork. These are distinct compatibility decisions. This machine has BIOS 5.08 and already uses InputPlumber 0.81.0, so both gyro compatibility checks fail.

Recommended: Do not run --force here. Port individual fixes with independent hardware and version checks.

Source: [oxp3-apply-fixes.sh:834–842](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L834-L842), [oxp3-apply-fixes.sh:870–875](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L870-L875). Verified by source inspection.

### A04 — The installer assumes SteamOS GRUB rather than this machine’s Limine setup (high)

Boot changes run update-grub and verify /efi/EFI/steamos/grub.cfg. They cannot configure the active custom Limine menu. An error can occur after other changes have already been installed, since no transaction rolls them back. Assigning GRUB_EARLY_INITRD_LINUX_CUSTOM can also replace an existing early-initrd list.

Recommended: Keep boot changes separate, identify the active loader, preserve existing entries and test a one-time recovery entry.

Source: [oxp3-apply-fixes.sh:104–110](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L104-L110), [oxp3-apply-fixes.sh:682–686](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L682-L686), [oxp3-apply-fixes.sh:1238–1253](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L1238-L1253), [oxp3-apply-fixes.sh:1364–1368](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L1364-L1368). Verified by source inspection.

### A05 — Firmware is extracted outside package verification and tracking (high)

The firmware branch trusts a cached or downloaded package because tar can read it; it does not verify the pacman signature or package digest before copying files and symlinks into /usr/lib/firmware as root. The copied files are untracked and cannot be individually reverted. Its pacman -Sy fallback refreshes databases without a full upgrade. Reloading iwlwifi can interrupt a network session.

Recommended: Use the distribution’s verified firmware package/update process. Diagnose the exact missing firmware from logs first. Do not run the branch when Wi-Fi already works.

Source: [oxp3-apply-fixes.sh:1159–1179](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L1159-L1179), [oxp3-apply-fixes.sh:1185–1218](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L1185-L1218). Verified by source inspection.

### A06 — Volume proxy still forwards the missing-release runaway as pulses (high)

Every raw press or repeat becomes a fresh volume pulse. Dropping EV_REP from the virtual device does not disable the physical keyboard’s timer or clear its held-key state. If the physical release is missing, Linux keeps sending value=2 and this code keeps stepping volume. It also grabs the entire keyboard and drops its scan, LED and repeat-control events.

Recommended: Capture raw events on this device first. Prefer an EC/atkbd fix that identifies fresh hardware make events and generates release correctly; a userspace workaround must distinguish source auto-repeat and preserve other keyboard behavior.

Source: [oxp3-volkey-fix.py:59–75](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-volkey-fix.py#L59-L75), [oxp3-volkey-fix.py:87–89](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-volkey-fix.py#L87-L89). Verified by source inspection.

### A07 — Battery workaround replaces the gauge’s learned energy_full globally (medium)

The service bind-mounts normal files over capacity and energy_full for every reader. It saves energy_full once and then inflates it to the highest energy_now observed, so later gauge learning is hidden. Other power-supply fields and uevent remain unchanged, producing inconsistent readings. The service is installed whenever BAT0 has energy attributes, regardless of an over-100% symptom.

Recommended: Clamp displayed percentages in readers, or fix the battery driver’s capacity range if reproduced. Keep the gauge’s actual energy_full untouched.

Source: [oxp3-apply-fixes.sh:405–418](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L405-L418), [oxp3-apply-fixes.sh:439–451](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L439-L451). Verified by source inspection.

### A08 — TDP synchronization trusts an unbounded power request and stale rollback value (high)

It copies any positive MMIO constraint_0 into MSR constraint_0 every two seconds. There is no maximum, PL1/PL2 relationship check, constraint-name discovery, hardware-range validation or verified readback. It can immediately overwrite a different sustained limit selected by firmware or a profile. Stop restores a value saved at the first start, potentially overriding a newer firmware/profile choice.

Recommended: Use an explicit bounded controller that discovers long_term constraints, updates both planes with readback and rollback, and preserves firmware safety limits. Treat the observed mismatch as evidence; measure workload throttling separately.

Source: [oxp3-apply-fixes.sh:632–650](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L632-L650). Verified by source inspection.

### A09 — Gyro installs a complete firmware SSDT using only a BIOS version string (high)

The 3,402-line SSDT contains many I2C devices and power resources, although the intended change is only the IMU ID. The installer checks BIOS 5.09 but does not compare the actual original table hash or board table contents. This unit has BIOS 5.08. Forcing a table from BIOS 5.09 is an additional incompatibility; a mismatched table can be replaced or the override appended by ACPI matching rules.

Recommended: Verify the device’s actual tables and sensor before any override. Prefer a narrowly scoped kernel/firmware correction. If an override is temporarily necessary, derive it from this device and retain the original loader entry.

Source: [gyro/SSDT26-oxp3-imu.dsl:21](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/gyro/SSDT26-oxp3-imu.dsl#L21), [gyro/SSDT26-oxp3-imu.dsl:561–562](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/gyro/SSDT26-oxp3-imu.dsl#L561-L562), [oxp3-apply-fixes.sh:870–875](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L870-L875). Verified by source inspection.

### A10 — Gyro patch changes generic BMI conversion and all Steam Deck target pacing (medium)

The fork changes the common BMI event translator and every deck-uhid write path, without an OXP3 gate in these code paths. It changes acceleration units, gyro scale and axes, report timing and frame counters. Source matching limits which OXP3 sensor is selected, but does not limit effects when other BMI devices or virtual Deck targets use the patched binary.

Recommended: Port independently justified conversion/pacing fixes to current InputPlumber with unit/axis/target tests. Keep OXP-specific mapping and optional steering policy outside generic sensor conversion.

Source: [gyro/inputplumber-0.78.0-oxp3-gyro.patch:298–334](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/gyro/inputplumber-0.78.0-oxp3-gyro.patch#L298-L334), [gyro/inputplumber-0.78.0-oxp3-gyro.patch:628–671](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/gyro/inputplumber-0.78.0-oxp3-gyro.patch#L628-L671). Verified by source inspection.

### A11 — Gyro stillness detection can absorb constant real rotation as bias (medium)

Both calibration layers judge stillness by variation, not the absolute mean rate. Constant rotation around gravity leaves gyro and accelerometer spans near zero and therefore qualifies as rest. The strict window moves bias halfway toward that real rotation every 400 samples, progressively subtracting intended motion. The high-pass steering filter also intentionally returns a sustained turn toward centre.

Recommended: Make steering relaxation an explicit user option, separate it from sensor correctness, and validate auto-bias with constant-rotation, rest, noisy-held and temperature-drift cases. Require plausible bias bounds or explicit rest calibration.

Source: [gyro/inputplumber-0.78.0-oxp3-gyro.patch:97–130](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/gyro/inputplumber-0.78.0-oxp3-gyro.patch#L97-L130), [gyro/inputplumber-0.78.0-oxp3-gyro.patch:528–539](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/gyro/inputplumber-0.78.0-oxp3-gyro.patch#L528-L539). Deterministic code inference; no hardware reproduction.

### A12 — Disabling gyro steering can leave a synthesized left-stick value latched (medium)

Hot reload clears the steering object’s output when disabled or when changing modes. Disabled/gyro mode then returns no stick update, while the target retains its previous l_stick_x. A nonzero value synthesized in stick mode can survive until a physical stick event arrives.

Recommended: Emit the physical stick state when exiting stick mode, reset steering state on target clear_state, and test transitions while steering is nonzero.

Source: [gyro/inputplumber-0.78.0-oxp3-gyro.patch:489–494](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/gyro/inputplumber-0.78.0-oxp3-gyro.patch#L489-L494), [gyro/inputplumber-0.78.0-oxp3-gyro.patch:515–519](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/gyro/inputplumber-0.78.0-oxp3-gyro.patch#L515-L519), [gyro/inputplumber-0.78.0-oxp3-gyro.patch:563](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/gyro/inputplumber-0.78.0-oxp3-gyro.patch#L563), [gyro/inputplumber-0.78.0-oxp3-gyro.patch:698–704](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/gyro/inputplumber-0.78.0-oxp3-gyro.patch#L698-L704). Deterministic code inference; no hardware reproduction.

### A13 — Gyro launcher fallback does not handle runtime failure (medium)

The launcher only checks the stock version, executable bit and ldd output, then execs the fork. If that binary starts and exits, crashes or fails initialization, it cannot fall back; a restart may choose the same failing binary repeatedly. The launch-time binary has no integrity recheck and remains user writable.

Recommended: Keep the stock controller service available independently. Use a root-owned reviewed build and a startup health check/explicit recovery mode rather than promising fallback from preflight checks.

Source: [oxp3-apply-fixes.sh:689–701](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L689-L701), [oxp3-apply-fixes.sh:1323–1342](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L1323-L1342). Verified by source inspection.

### A14 — HDR and full refresh range require panel-specific validation (medium)

The Lua forces gamma-2.2 HDR with fixed brightness/color values and generates every 30–144 Hz mode by interpolating two reported timings. Its panel vendor/model guard is useful, but two valid endpoints do not prove all generated timings, HDR brightness or VRR behavior on this unit. These are internal eDP changes and do not repair the LG TV dock hotplug issue.

Recommended: Match the actual EDID and base timing, validate a small set of refresh modes and brightness/HDR behavior, then stage a user-level gamescope profile with a rollback. Do not describe gamma-2.2 tone mapping as a verified native PQ/backlight fix.

Source: [oxp3-apply-fixes.sh:153–161](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L153-L161), [oxp3-apply-fixes.sh:179–229](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L179-L229). Verified by source inspection.

### A15 — Display-state-buffer disable is applied without checking symptoms or initramfs (medium)

Every apply writes xe enable_dsb=0. The source assumes xe is outside initramfs and labels the errors cosmetic without independent confirmation. On another kernel the parameter may require rebuilding initramfs, and disabling DSB changes driver behavior even if this device has no poll-error flood.

Recommended: Inspect this device’s journal and loaded parameter first. Investigate a driver fix; use the parameter only as a measured workaround with the actual boot/initramfs workflow.

Source: [oxp3-apply-fixes.sh:144–150](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L144-L150), [oxp3-apply-fixes.sh:1257–1265](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L1257-L1265). Verified by source inspection.

### A16 — Reference controller mapping disagrees with what the installer writes (low)

The reference file swaps the left/right paddles, while the embedded capability map deliberately removes that swap. A person copying the advertised reference files gets different behavior from normal install. This repo also chooses Home→Guide and deck-uhid, whereas this device already has a tested controller profile.

Recommended: Retain the working profile. Any future mapping change should be driven by captured events and the user’s desired Home behavior, and all source copies should agree.

Source: [reference/onexplayer_type3_oxp3.yaml:23–36](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/reference/onexplayer_type3_oxp3.yaml#L23-L36), [oxp3-apply-fixes.sh:544–562](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L544-L562). Verified by source inspection.

### A17 — Hidden MCU restore writes persistent state without readback or recovery (high)

The explicit --mcu-restore path writes a raw 64-byte guessed page-3 button table. The code itself warns that it persists across power-off, cannot be read back, and can disable chassis keys. --yes bypasses confirmation. This is separate from normal apply, and there is no evidence it is needed for our working controls.

Recommended: Do not run or bundle this operation as a normal fix. Only vendor-documented recovery with verified hardware identity, original data and an established recovery method could justify it.

Source: [oxp3-apply-fixes.sh:1025–1059](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L1025-L1059). Verified by source inspection.

### A18 — Check means pack installed, not fix needed; root read-only state is not restored (low)

--check marks absent desired files as differences even if the corresponding issue was never observed. In particular, it wants the NVMe file regardless of whether the SSD matches. Apply disables SteamOS read-only root without restoring its initial state. Broad repeat-apply guidance can consequently add unnecessary changes or overwrite local improvements.

Recommended: Report hardware applicability, reproduced symptom and install status separately. Restore the initial root protection state after a transaction.

Source: [oxp3-apply-fixes.sh:975–1014](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L975-L1014), [oxp3-apply-fixes.sh:1226–1230](https://github.com/HHHHanasak1/onexplayer3-steamos-setup/blob/ea371b357b8ba6467e00c0be372e1c86c1ac523b/oxp3-apply-fixes.sh#L1226-L1230). Verified by source inspection.

## Independent upstream checks

Linux input autorepeat is per source input device: a held key continues generating repeat events from the source timer. The proxy’s virtual-device release cannot clear that source state. Checked Linux commit `7b63ef2d55f24519e7e9e5f4d15dbea03f126e40`: [`input.c` autorepeat](https://github.com/torvalds/linux/blob/7b63ef2d55f24519e7e9e5f4d15dbea03f126e40/drivers/input/input.c#L2289-L2305).

`10EC5280` is intentionally matched by bmi160 for older hardware. bmi270’s `BMI0260` selects BMI260. A global additional match would compete with the former driver and could affect genuine BMI160 systems: [`bmi160_i2c.c`](https://github.com/torvalds/linux/blob/7b63ef2d55f24519e7e9e5f4d15dbea03f126e40/drivers/iio/imu/bmi160/bmi160_i2c.c#L45-L58), [`bmi270_i2c.c`](https://github.com/torvalds/linux/blob/7b63ef2d55f24519e7e9e5f4d15dbea03f126e40/drivers/iio/imu/bmi270/bmi270_i2c.c#L41-L46). The exact running CachyOS source/config still needs to be checked before designing a quirk.

`nvme.noacpi` is a driver-wide parameter affecting ACPI simple-suspend selection, not a per-SSD switch: [`nvme/pci.c`](https://github.com/torvalds/linux/blob/7b63ef2d55f24519e7e9e5f4d15dbea03f126e40/drivers/nvme/host/pci.c#L3715-L3725). ACPI initrd upgrades use table signature/OEM identity/revision matching: [kernel documentation](https://docs.kernel.org/admin-guide/acpi/initrd_table_override.html).

## What the pack does well, and what remains unproven

The normal gyro step is opt-in. The script has DMI/OS, BIOS and InputPlumber-series guards, refuses to overwrite an unrecognized ACPI override image, checks its downloaded gyro binary against a pinned SHA256, and limits its normal paddle changes to existing hid-oxp sysfs attributes. Those are useful precautions; the --force coupling and writable root payloads undermine them.

The gyro patch is documented GPL-3.0-or-later, unlike the rest of the pack’s MIT license. Preserve that distinction and the corresponding upstream source revision if any code is reused. The release’s MIT LICENSE does not change the derivative InputPlumber code’s license.

## Maintenance approach

Keep each justified change scoped to its hardware and distribution, install root payloads in root-owned paths, save the previous state, and test rollback. Preserve the separate licenses of reused components. The linked source is pinned; later upstream changes need a new review.
