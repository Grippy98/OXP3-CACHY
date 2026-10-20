These host tests exercise the actual controller decoder, USB driver and UEFI
input wait implementation. They do not prove that the OXP3 firmware exposes
USB IO for the native controller or that navigation works on hardware.

Run from this fix folder:

```sh
sh tests/run-state-tests.sh
sh tests/run-firmware-tests.sh
sh tests/run-wait-tests.sh
```

The decoder suite requires a C99 compiler. The firmware and input wait suites
require a GNU11 compiler and the baseline PicoEFI headers. Their default path
is `reference-headers/picoefi/inc`; set
`PICOEFI_INCLUDE` to use a different checkout of the same dependency.

For address and undefined-behaviour checks, prefix each command with
`CC='clang -fsanitize=address,undefined -fno-omit-frame-pointer'`.

Coverage includes malformed and short reports, startup-held confirmation,
rapid press/release delivery, dead zone and hysteresis, direction repeat,
confirmation/back without repeat, bounded queues, and disconnect reset.
Firmware mocks check exact descriptors, occupied interfaces, partial
initialisation rollback, ownership arguments, callback errors, shutdown order,
and refusing handoff when cancelling an outstanding callback fails. Input
wait mocks check controller-only input, keyboard/Escape handling, 16 mouse
events plus controller input, removal of a disconnected controller timer,
and retaining the original countdown timer across idle controller ticks.

Mocks use the actual source with only the surrounding firmware environment
replaced. Firmware ownership, event and callback behaviour still need a test
boot of the experimental EFI image, followed by successful OS/controller
handoff. The stock EFI entry should remain available during that test.

Deployment-helper regressions run without firmware access:

```sh
python3 tests/test-controller-state.py
python3 tests/test-promotion-state-independent.py
```
