# Independent UEFI Xbox USB IO runtime fixture

This test runs only in a private QEMU/OVMF VM. It does not install anything on
the OneXPlayer, change host EFI files, or change production Limine sources.
The USB IO ABI is declared independently from the production implementation.
PicoEFI supplies only standard EFI types/services. USB protocol and descriptor
sizes/offsets have compile-time assertions against the UEFI ABI.

Run from this fix folder. Build with your existing Clang 19/LLD container and
the included release headers:

```sh
python3 tests/uefi-mock/build.py --container YOUR_CLANG19_CONTAINER
python3 tests/uefi-mock/run.py --limine build/BOOTX64.EFI
python3 tests/uefi-mock/run.py --limine build/BOOTX64.EFI --gamepad-disabled --timeout 12
python3 tests/uefi-mock/run.py --limine build/BOOTX64.EFI --autoboot-idle --timeout 15
python3 tests/uefi-mock/run.py --limine build/BOOTX64.EFI --tree-back --timeout 20
```

The mock parent installs an Xbox360-compatible USB IO protocol, then loads the
patched EFI child through an actual firmware filesystem device path and
LoadImage/StartImage. It accepts asynchronous IN submissions and calls the
production callback at TPL_NOTIFY every 20 ms. Reports begin neutral, pulse
D-pad Down at 1 s, pulse Up at 3 s, then press A at 5 s. Direction pulses are
60 ms to avoid repeat affecting the expected selected entry. The menu has
three entries and starts on the first; Down must select the second, Up must
return to the first, and A must chainload the separate target application.

The target checks that there was exactly one asynchronous start and cancellation,
no active input transfer remains, and the first entry's actual EFI LoadOptions
arrived. It prints pass/fail to QEMU debugcon port 0xe9 and the EFI console.
The runner checks ordered markers, saves screenshots after Down and Up and
at the target, and exits QEMU. Generated firmware variables, ESP, logs, images,
and machine-readable result live in an ignored results directory.

Screenshots are needed to independently confirm both intermediate highlighted
entries: returning to the first after Down/Up is also possible if neither arrow
was delivered. The automatic assertions prove callback delivery, selection/A,
and cancellation before EFI chainload, not both intermediate visual positions.

This fixture cannot prove firmware USB enumeration, physical endpoint timing,
real controller report compatibility, disconnect/suspend behaviour, or cleanup
through ExitBootServices. Use the separate experimental hardware entry for
those checks. The mock is deliberately not a full USB bus emulator.

The timeout defaults to 45 seconds. QEMU and OVMF paths can be overridden with
`--qemu`, `--ovmf-code`, and `--ovmf-vars`; build container/header paths are
also configurable. Only disposable local VM artifacts are written.

The disabled negative control uses `gamepad: no` and requires the mock child
to start while no USB input request or target chainload occurs for the entire
timeout. It confirms the enable flag gates the adapter and that A selection
in the main scenario depends on controller integration.

The idle autoboot scene uses a separate mock build that supplies neutral reports
continuously at 20 ms, and a 2-second menu countdown. It requires selection of
the first target with successful cancellation and without any A/arrow report.
That tests whether either USB reports or the adapter's timer accidentally reset
the original countdown timeout. Result JSON records the copied child EFI hash.

The tree scene begins on a child inside two expanded directory levels. B must
collapse/select its immediate parent; Right must re-expand that parent; Down
must select the expected child and A must boot it. Wrong siblings and entries
have different EFI LoadOptions so a misplaced selection fails. Screenshots
show the collapsed selected parent, expanded selected parent, and selected child.
