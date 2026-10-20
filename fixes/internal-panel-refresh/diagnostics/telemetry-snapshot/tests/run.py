#!/usr/bin/env python3
"""Compile the actual output-update function in an isolated regression harness."""
import argparse
from pathlib import Path
import subprocess
import tempfile


def run_case(source: Path, harness: Path, baseline: bool) -> None:
    text = source.read_text()
    start = text.index("void mangoapp_output_update(")
    with tempfile.TemporaryDirectory(prefix="oxp3-telemetry-test-") as temp:
        work = Path(temp)
        (work / "mangoapp_output_update.inc").write_text(text[start:])
        binary = work / "telemetry-test"
        command = ["clang++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                   "-I", str(work), str(harness), "-o", str(binary)]
        if baseline:
            command.insert(1, "-DLEGACY_BASELINE")
        subprocess.run(command, check=True)
        subprocess.run([str(binary)], check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-source", type=Path,
                        help="Optional unmodified src/mangoapp.cpp for the counterexample")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    harness = root / "tests/telemetry_snapshot_test.cpp"
    if args.baseline_source:
        run_case(args.baseline_source.resolve(), harness, True)
    run_case(root / "source/src/mangoapp.cpp", harness, False)


if __name__ == "__main__":
    main()
