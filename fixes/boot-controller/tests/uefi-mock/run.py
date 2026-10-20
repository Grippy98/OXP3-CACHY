#!/usr/bin/env python3
"""Run patched Limine against a private QEMU USB IO fixture and inspect handoff."""
import argparse
from datetime import datetime
import json
import hashlib
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parent

CONFIG = """timeout: no
default_entry: 1
remember_last_entry: no
gamepad: yes
serial: yes
verbose: yes
interface_branding: OXP3 UEFI USB IO mock test

/Mock first (expected after Down then Up)
    protocol: efi
    path: boot():/EFI/TestTarget/TARGET.EFI
    cmdline: mock-selected-first

/Mock second
    protocol: efi
    path: boot():/EFI/TestTarget/TARGET.EFI
    cmdline: mock-selected-second

/Mock third
    protocol: efi
    path: boot():/EFI/TestTarget/TARGET.EFI
    cmdline: mock-selected-third
"""

TREE_CONFIG = """timeout: no
default_entry: Outer folder/Nested folder/Expected child
remember_last_entry: no
gamepad: yes
serial: yes
verbose: yes
interface_branding: OXP3 UEFI Back and Expand tree mock

/+Outer folder
//+Nested folder
///Expected child
    protocol: efi
    path: boot():/EFI/TestTarget/TARGET.EFI
    cmdline: mock-selected-first
///Wrong sibling
    protocol: efi
    path: boot():/EFI/TestTarget/TARGET.EFI
    cmdline: mock-selected-second
//Wrong outer child
    protocol: efi
    path: boot():/EFI/TestTarget/TARGET.EFI
    cmdline: mock-selected-third
/Wrong root entry
    protocol: efi
    path: boot():/EFI/TestTarget/TARGET.EFI
    cmdline: mock-selected-fourth
"""


class QMP:
    def __init__(self, path, deadline):
        self.socket = socket.socket(socket.AF_UNIX)
        while True:
            try:
                self.socket.connect(str(path))
                break
            except (FileNotFoundError, ConnectionRefusedError):
                if time.monotonic() > deadline:
                    raise TimeoutError("QEMU monitor did not start")
                time.sleep(0.05)
        self.socket.settimeout(5)
        self.stream = self.socket.makefile("rwb", buffering=0)
        self.read()
        self.command("qmp_capabilities")

    def read(self):
        line = self.stream.readline()
        if not line:
            raise RuntimeError("QEMU monitor closed")
        return json.loads(line)

    def command(self, operation, arguments=None):
        command = {"execute": operation}
        if arguments is not None:
            command["arguments"] = arguments
        self.stream.write(json.dumps(command).encode() + b"\r\n")
        while True:
            reply = self.read()
            if "error" in reply:
                raise RuntimeError(reply["error"])
            if "return" in reply:
                return reply["return"]

    def screenshot(self, path):
        self.command("screendump", {"filename": str(path), "format": "png"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limine", type=Path, required=True)
    parser.add_argument("--qemu", default=shutil.which("qemu-system-x86_64"))
    parser.add_argument("--ovmf-code", type=Path, default=Path("/opt/homebrew/share/qemu/edk2-x86_64-code.fd"))
    parser.add_argument("--ovmf-vars", type=Path, default=Path("/opt/homebrew/share/qemu/edk2-i386-vars.fd"))
    parser.add_argument("--timeout", type=float, default=45)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--gamepad-disabled", action="store_true",
                        help="negative control: gamepad:no must not submit USB input or boot")
    parser.add_argument("--autoboot-idle", action="store_true",
                        help="2-second countdown must boot despite neutral USB reports/timer ticks")
    parser.add_argument("--tree-back", action="store_true",
                        help="B collapses/selects nested parent; Right expands; Down+A selects child")
    args = parser.parse_args()
    if sum((args.gamepad_disabled, args.autoboot_idle, args.tree_back)) > 1:
        parser.error("disabled, idle autoboot, and tree are separate scenarios")
    output = (args.output or HERE / "results" / datetime.now().strftime("%Y%m%d-%H%M%S")).resolve()
    output.mkdir(parents=True, exist_ok=True)
    esp = output / "esp"
    for folder in ("EFI/BOOT", "EFI/LimineTest", "EFI/TestTarget"):
        (esp / folder).mkdir(parents=True, exist_ok=True)
    mock_binary = "BOOTX64-TREE.EFI" if args.tree_back else "BOOTX64-IDLE.EFI" if args.autoboot_idle else "BOOTX64.EFI"
    for source, target in ((HERE / "build" / mock_binary, esp / "EFI/BOOT/BOOTX64.EFI"),
                           (HERE / "build/TARGET.EFI", esp / "EFI/TestTarget/TARGET.EFI"),
                           (args.limine, esp / "EFI/LimineTest/BOOTX64.EFI")):
        shutil.copyfile(source, target)
    config = CONFIG.replace("gamepad: yes", "gamepad: no") if args.gamepad_disabled else CONFIG
    if args.autoboot_idle:
        config = config.replace("timeout: no", "timeout: 2")
    elif args.tree_back:
        config = TREE_CONFIG
    (esp / "limine.conf").write_text(config)
    shutil.copyfile(args.ovmf_vars, output / "vars.fd")
    debug = output / "debugcon.log"
    serial = output / "serial.log"
    snapshots = {}
    with tempfile.TemporaryDirectory(prefix="oxp3-qmp-") as td:
        monitor = Path(td) / "qmp.sock"
        command = [args.qemu, "-machine", "q35,accel=tcg", "-cpu", "qemu64", "-m", "256",
                   "-drive", "if=pflash,format=raw,readonly=on,file=" + str(args.ovmf_code),
                   "-drive", "if=pflash,format=raw,file=" + str(output / "vars.fd"),
                   "-drive", "format=raw,file=fat:rw:" + str(esp), "-display", "none",
                   "-serial", "file:" + str(serial), "-debugcon", "file:" + str(debug),
                   "-global", "isa-debugcon.iobase=0xe9", "-qmp", "unix:" + str(monitor) + ",server=on,wait=off",
                   "-net", "none", "-no-reboot"]
        (output / "qemu-command.json").write_text(json.dumps(command, indent=2) + "\n")
        deadline = time.monotonic() + args.timeout
        with (output / "qemu-stderr.log").open("wb") as error_log:
            process = subprocess.Popen(command, stdout=error_log, stderr=error_log)
            qmp = None
            try:
                qmp = QMP(monitor, deadline)
                while time.monotonic() < deadline and process.poll() is None:
                    text = debug.read_text(errors="replace") if debug.exists() else ""
                    scenes = (("MOCK:TREE:B_COLLAPSE", "after-b-collapse.png"),
                              ("MOCK:TREE:RIGHT_EXPAND", "after-right-expand.png"),
                              ("MOCK:TREE:DOWN_CHILD", "after-down-child.png"),
                              ("TARGET:", "target.png")) if args.tree_back else (
                                             ("MOCK:STAGE:DOWN", "after-down.png"),
                                             ("MOCK:STAGE:UP", "after-up.png"),
                                             ("TARGET:", "target.png"))
                    for marker, filename in scenes:
                        if marker in text and marker not in snapshots:
                            time.sleep(0.2)
                            qmp.screenshot(output / filename)
                            snapshots[marker] = filename
                    if "TARGET:" in text:
                        break
                    time.sleep(0.05)
                text = debug.read_text(errors="replace") if debug.exists() else ""
                required = ["MOCK:ENTER", "MOCK:USB_IO_INSTALLED", "MOCK:CHILD_START",
                            "MOCK:ASYNC_START", "MOCK:STAGE:DOWN", "MOCK:STAGE:UP", "MOCK:STAGE:A",
                            "MOCK:ASYNC_CANCEL", "TARGET:PASS:CLEANUP_BEFORE_CHAINLOAD",
                            "TARGET:PASS:SELECTED_FIRST_AFTER_DOWN_UP"]
                if args.gamepad_disabled:
                    required = required[:3]
                    qmp.screenshot(output / "controller-disabled.png")
                elif args.autoboot_idle:
                    required = required[:4] + ["MOCK:STAGE:NEUTRAL_INITIAL", "MOCK:ASYNC_CANCEL",
                                               "TARGET:PASS:CLEANUP_BEFORE_CHAINLOAD",
                                               "TARGET:PASS:SELECTED_FIRST_BY_AUTOBOOT"]
                elif args.tree_back:
                    required = required[:4] + ["MOCK:TREE:NEUTRAL_INITIAL", "MOCK:TREE:B_COLLAPSE",
                                               "MOCK:TREE:RIGHT_EXPAND", "MOCK:TREE:DOWN_CHILD",
                                               "MOCK:TREE:A_CHILD", "MOCK:ASYNC_CANCEL",
                                               "TARGET:PASS:CLEANUP_BEFORE_CHAINLOAD",
                                               "TARGET:PASS:SELECTED_CHILD_AFTER_BACK_EXPAND"]
                positions = [text.find(marker) for marker in required]
                passed = all(position >= 0 for position in positions) and positions == sorted(positions) and "TARGET:FAIL" not in text
                if args.gamepad_disabled:
                    passed = passed and "MOCK:ASYNC_START" not in text and "TARGET:" not in text and process.poll() is None
                elif args.autoboot_idle:
                    passed = passed and "MOCK:STAGE:A" not in text and "MOCK:STAGE:DOWN" not in text
                summary = {"passed": passed, "scope": "UEFI protocol fixture, navigation, and EFI chainload cleanup; not real USB hardware or ExitBootServices",
                           "scenario": "tree-back-expand" if args.tree_back else
                                       "disabled-negative-control" if args.gamepad_disabled else
                                       "idle-report-countdown" if args.autoboot_idle else "down-up-confirm",
                           "tree_back_scenario": args.tree_back,
                           "markers": {marker: position >= 0 for marker, position in zip(required, positions)},
                           "screenshots": snapshots, "limine": str(args.limine.resolve()),
                           "limine_sha256": hashlib.sha256((esp / "EFI/LimineTest/BOOTX64.EFI").read_bytes()).hexdigest()}
                (output / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
                print(("PASS" if passed else "FAIL") + ": UEFI mock runtime; artifacts: " + str(output))
                if not passed:
                    print(text[-6000:])
                return 0 if passed else 1
            finally:
                if qmp is not None:
                    try:
                        qmp.command("quit")
                    except (OSError, RuntimeError):
                        pass
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
