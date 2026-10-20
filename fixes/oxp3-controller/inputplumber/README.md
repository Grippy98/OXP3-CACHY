# InputPlumber integration

These profiles combine the native Xbox controller, companion keyboard and OXP
vendor HID events into one virtual Xbox Elite controller. They accompany the
[pinned kernel driver](../kernel/SOURCES.md); both were present during the
successful OXP3/CachyOS physical test.

| Input | Tested route |
| --- | --- |
| ONEX | Ctrl + Alt + Meta -> QuickAccess -> Guide + A |
| Keyboard | Ctrl + Meta + O -> Keyboard -> Guide + North |
| Home | Companion HID `0x24` -> Keyboard -> Guide + North |
| Native Guide | Guide passes through |
| Left rear paddle | Companion HID `0x22` -> virtual Elite key `710` |
| Right rear paddle | Companion HID `0x23` -> virtual Elite key `708` |

## Source and changes

The original profiles in `pr660/` and `pr660.patch` come from
[InputPlumber PR 660](https://github.com/ShadowBlip/InputPlumber/pull/660), pinned
to [commit `1f2b129ab5e6ab314a9cc7af546b3119c95099da`](https://github.com/Grippy98/InputPlumber/tree/1f2b129ab5e6ab314a9cc7af546b3119c95099da).
That contribution was closed without merging. `local-config/` preserves the
tested profiles: the keyboard chord's target changes from `QuickAccess2` to
`Keyboard`, and the hwdb addition matches OXP3 only. `local-changes.patch`
documents these changes. No additional Home remap is included.

The review snapshot is InputPlumber v0.81.0, commit
[`ea60d873cca17edd1cb655ede26f557108135252`](https://github.com/ShadowBlip/InputPlumber/tree/ea60d873cca17edd1cb655ede26f557108135252).
`reference-v0.81.0/` retains schemas, default profile and relevant source for
[the filtering/chord review](CODE-REVIEW.md). The snapshot and these profiles are
GPL-3.0-or-later; the license is included as `LICENSE`.

## Install and verify

The [controller installer](../README.md) installs the DKMS driver and profiles
together. To install only the profiles on an OXP3 that already has InputPlumber:

```sh
sudo bash fixes/oxp3-controller/inputplumber/install.sh
systemctl is-active inputplumber.service
inputplumber devices list
```

The script checks DMI and saves prior files/service state under
`/var/lib/oxp3-fixes/inputplumber/`. It installs three administrator overrides:

```text
/etc/inputplumber/devices.d/50-onexplayer_3.yaml
/etc/inputplumber/capability_maps.d/onexplayer_type9.yaml
/etc/udev/hwdb.d/61-onexplayer3-inputplumber-autostart.hwdb
```

It updates the hwdb and enables/restarts InputPlumber. A matching already-active
setup is a no-op. Physical USB paths are the tested OXP3 topology; hardware
revisions can require profile changes. InputPlumber 0.81.0-1.1 was tested; newer
releases need schema/behavior review. The optional BMI260 sensor was not found
on the tested device. Simultaneous factory-button combinations were not tested.

Test each menu button and rear paddle separately in Steam Gaming Mode, then
reconnect and suspend/resume. Valid YAML and an active service do not establish
that a different firmware emits the expected vendor reports.

## Rollback and schema checks

Use the exact directory printed by the installer:

```sh
sudo bash fixes/oxp3-controller/inputplumber/rollback.sh /var/lib/oxp3-fixes/inputplumber/BACKUP
```

Rollback restores prior overrides/service enablement and activity. It refuses to
replace later file edits; save them before an intentional `--force` rollback.
Packages, the kernel driver and backups remain. The combined controller rollback
uses this script when the combined install created a profile backup.

For offline schema checks, use a Python environment with PyYAML and jsonschema:

```sh
python3 fixes/oxp3-controller/inputplumber/validate.py
```

The functional schema JSON files are source dependencies for this validator.
The original and tested YAMLs pass the pinned schemas. Revised installers have
host syntax/review checks; no device installation was performed for publication.
