#!/usr/bin/env python3
"""Build independent UEFI mock/target with Clang + LLD in a local container."""
import argparse
from pathlib import Path
import subprocess
import uuid

HERE = Path(__file__).resolve().parent


def run(*arguments):
    subprocess.run(arguments, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", required=True, help="Existing container with clang-19 and lld-link-19")
    parser.add_argument("--headers", type=Path,
                        default=HERE.parents[1] / "reference-headers")
    args = parser.parse_args()
    remote = "/tmp/oxp3-uefi-mock-" + uuid.uuid4().hex
    destination = HERE / "build"
    destination.mkdir(exist_ok=True)
    run("docker", "exec", args.container, "mkdir", "-p", remote)
    try:
        for file in ("mock_usb.h", "mock.c", "target.c"):
            run("docker", "cp", str(HERE / file), args.container + ":" + remote + "/" + file)
        run("docker", "cp", str(args.headers / "picoefi/inc"), args.container + ":" + remote + "/picoefi")
        run("docker", "cp", str(args.headers / "freestanding-c-hdrs/include"), args.container + ":" + remote + "/headers")
        for source, output, extra in (("mock", "BOOTX64.EFI", []),
                                      ("mock", "BOOTX64-IDLE.EFI", ["-DMOCK_IDLE=1"]),
                                      ("mock", "BOOTX64-TREE.EFI", ["-DMOCK_TREE=1"]),
                                      ("target", "TARGET.EFI", [])):
            run("docker", "exec", args.container, "clang-19",
                "--target=x86_64-pc-windows-msvc", "-std=c11", "-ffreestanding",
                "-fshort-wchar", "-mno-red-zone", "-fno-stack-protector", "-fno-builtin",
                "-nostdinc", "-I" + remote + "/picoefi", "-I" + remote + "/headers",
                "-O2", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
                *extra,
                "-c", remote + "/" + source + ".c", "-o", remote + "/" + source + ".obj")
            run("docker", "exec", args.container, "lld-link-19", "/entry:efi_main",
                "/subsystem:efi_application", "/nodefaultlib", "/machine:x64",
                "/opt:ref", "/opt:icf", "/out:" + remote + "/" + output,
                remote + "/" + source + ".obj")
            run("docker", "cp", args.container + ":" + remote + "/" + output,
                str(destination / output))
        print("Built independent mock and target in", destination)
    finally:
        run("docker", "exec", args.container, "rm", "-rf", remote)


if __name__ == "__main__":
    main()
