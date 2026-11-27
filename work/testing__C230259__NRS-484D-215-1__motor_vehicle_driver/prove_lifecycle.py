"""Exercise synthetic capture closure, Native exit, release and saved replay order."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import acknowledge_owner_release, copy_sources, record_native_exit


def main():
    parser = argparse.ArgumentParser()
    for name in ("case", "attempt", "output", "manifest", "validator"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    source = Path(args.attempt).resolve(strict=True)
    output = Path(args.output).resolve()
    if output.exists():
        raise ValueError("synthetic saved replay output must be fresh")
    attempt = output.with_name(output.name + "-capture")
    if attempt.exists():
        raise ValueError("synthetic capture closure input must be fresh")
    attempt.mkdir(parents=True)
    copy_sources(source, attempt)
    seal = seal_capture(attempt, frames=5,
                        restoration={"restored": True, "settings_readback": "synthetic lifecycle harness"},
                        errors=[], encoder_exit_codes={view: 0 for view in
                                                         ("overview", "approach", "reference_corner", "driver_reference")})
    if seal["events"] != ["capture_finished", "encoders_closed", "restoration_verified"]:
        raise ValueError("capture closure order differs")
    exit_receipt = record_native_exit(attempt)
    if exit_receipt["event"] != "native_exit":
        raise ValueError("Native exit receipt missing")
    owner = acknowledge_owner_release(attempt, attempt / "owner-release.json", True)
    if owner["event"] != "owner_released":
        raise ValueError("owner release receipt missing")
    command = [str(Path.cwd() / ".venv-cpu/bin/python"), "runtime.py", "process-saved",
               "--manifest", args.manifest, "--case", args.case,
               "--attempt", str(attempt), "--output", str(output),
               "--library", "runtime/library", "--validator", args.validator,
               "--owner-release-receipt", str(attempt / "owner-release.json")]
    subprocess.run(command, check=True, timeout=300)
    if not (output / "v0001" / "processing.json").is_file():
        raise ValueError("saved processing did not start after owner release")
    print("capture_finished\nencoders_closed\nrestoration_verified\n"
          "native_exit\nowner_released\nsaved_processing_started")


if __name__ == "__main__":
    main()
