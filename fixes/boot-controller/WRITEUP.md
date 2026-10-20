# How the boot-menu fix works

Limine's normal UEFI keyboard/pointer paths do not decode the OXP3 controller's
wired Xbox 360 reports. The preserved patch adds an opt-in `gamepad: yes` path
using EFI USB IO. Its device/interface/endpoint match is deliberately limited to
the tested `045e:028e`, `ff/5d/01`, interrupt IN `0x81` interface.

The decoder requires neutral input before arming A/B, uses stick hysteresis,
queues short presses and repeats vertical navigation. The wait loop integrates
the controller timer with existing input and keeps the original autoboot timer.
The firmware driver uses ordinary driver ownership, skips occupied interfaces,
and cancels its asynchronous transfer before editor entry or image handoff.
Failure to cancel blocks handoff to avoid unloading a live callback. Transfer
errors disable input until reinitialization; automatic reconnection is absent.

The unchanged patch was physically tested on the owner's ONEXPLAYER 3: menu
navigation/selection and a successful Linux boot worked. Host suites and the
independent UEFI fixture cover report state, ownership/lifetime and menu timing;
see [tests](tests/README.md) and the [detailed proposal](upstream/PROPOSAL.md).
Firmware enumeration on other machines and Secure Boot remain unestablished.

Deployment is separate from the bootloader implementation. The revised reusable
scripts discover firmware entry IDs and preserve live kernel entries/countdowns.
They stage an opt-in sibling menu by default; promotion requires an explicit
separate command after physical testing. These portable-script changes have
host syntax and isolated state regressions, but no new device run. They do not
change the previously tested patch or assert that a newly rebuilt image is
byte-identical to the original.

The patch is pinned to Limine v12.9.0 and has no claimed upstream acceptance.
Stock package upgrades maintain the separate stock loader, so custom-image
updates require a rebase, rebuild and physical test. [Source pins/licenses](SOURCES.md),
[upstream review tasks](upstream/REVIEW-TODO.md), and the
[install/verify/rollback guide](README.md) provide the maintenance workflow.
