# Draft: Add opt-in wired Xbox 360 input to the UEFI menu

This is a review draft, not a submitted pull request or a claim of upstream
acceptance.

## Problem and resulting behaviour

The ONEXPLAYER 3's built-in controller exposes USB `045e:028e`, interface zero
`ff/5d/01`, with a 32-byte interrupt IN endpoint at `0x81`. Its firmware exposes
that interface through `EFI_USB_IO_PROTOCOL`, but Limine's existing keyboard and
pointer paths do not decode its native reports. The handheld's controller can
therefore operate Steam after boot while being unable to select a boot menu entry
without a keyboard or a change to the controller's operating mode.

With the global `gamepad: yes` option, the proposed adapter accepts this native
interface before Linux starts. D-pad Up/Down and the left stick's vertical axis
move the selection; A selects; B or Left collapses the selected directory or its
parent; Right expands a directory. Right on an OS entry does not boot it. The
option defaults to disabled, keyboard and mouse input remain available, and
entry editing uses a keyboard.

## Implementation

The adapter validates the complete tested device/interface/endpoint signature,
opens an available interface by driver ownership, and starts asynchronous input.
It leaves an interface already owned by firmware alone, without disconnecting
that driver or taking exclusive ownership. USB protocol declarations are kept
in owned source because the pinned PicoEFI dependency does not provide them.
The protocol layout and descriptor sizes have static ABI checks.

The report decoder requires neutral mapped input when the menu opens, applies a
stick dead zone with hysteresis, buffers brief presses, and repeats only vertical
navigation. A and B are edge-triggered and simultaneous A/B is rejected. The
input wait path combines the controller timer with existing keyboard/pointer
events without restarting the original autoboot deadline on neutral reports.

The static context survives the menu's memory rewind. The transfer is cancelled
before editor entry, menu rewind, EFI chainload, or ExitBootServices. Callback
errors disable controller input while keyboard input remains available. A failed
cancellation refuses handoff because unloading callback code with an outstanding
transfer would be unsafe. These ownership and failure choices need maintainer
review.

## Validation already recorded

| Check | Result and scope |
| --- | --- |
| x86-64 EFI build | Clang/LLD 19, NASM 2.16.03 in an ARM64 Debian container on the Mac; no patched-build warnings recorded |
| Three host suites | Decoder/state, USB ownership/lifetime, and input wait tests passed, including ASan/UBSan |
| Four QEMU/OVMF scenes | Native navigation/selection, disabled negative control, neutral-report autoboot, and nested Back/Expand selection passed |
| Physical OXP3 | User confirmed menu/controller operation; the patched EFI was verified as the booted loader, then booted production CachyOS successfully |
| OS handoff | InputPlumber, Steam Gaming Mode, and the expected OXP3 HID driver remained active after the physical boot |
| Configuration deployment | Normal firmware default was promoted while keeping stock fallback; live kernel entries and the five-second menu timeout were preserved |
| Historical source compatibility | Application and whitespace checks passed on observed `v12.x` HEAD; no build or hardware run on that revision |

The UEFI fixture supplies an independent USB IO protocol implementation; it is
not a real USB bus emulator. It demonstrates callback delivery and cancellation
before EFI chainload, but not physical enumeration or a real ExitBootServices
path. The successful physical Linux boot provides one hardware handoff test,
rather than full disconnect, error, firmware, or architecture coverage.

The public bundle retains the actual test harnesses and a concise test-status
writeup in the [main README](../README.md). Test captures are not distributed.

## Intended upstream scope

The proposed patch contains the bootloader adapter, report state, input/menu
integration, cleanup hooks, and option documentation. Device-specific installers,
firmware entry numbers, CachyOS configuration scripts, and built EFI binaries
belong to the local testing bundle. Tests should be adapted to the upstream test
layout if maintainers wish to carry them.

The first supported signature is deliberately narrow. This is not general USB
HID gamepad support, wireless Xbox support, controller firmware modification, or
a Linux input driver. The adapter does not reconnect automatically after a
transfer failure, and the tested image was unsigned with Secure Boot disabled.

## Primary references

- [UEFI 2.11 USB support and USB IO interface](https://uefi.org/specs/UEFI/2.11/17_Protocols_USB_Support.html).
- [Linux wired Xbox 360 report handling](https://github.com/torvalds/linux/blob/master/drivers/input/joystick/xpad.c).
- [ONEXPLAYER 3 operating-mode and preboot controls](https://www.onexplayer.com/manual/onexplayer3).
- [Tested Limine source](https://github.com/Limine-Bootloader/Limine/tree/v12.9.0)
  and [observed current source](https://github.com/Limine-Bootloader/Limine/tree/e3aa138d383ca4fe061f05931b5a54497cd502f2).
