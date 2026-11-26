"""Exercise closure ordering with synthetic CPU files only."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "").endswith(".runtime-work/c394563-lifecycle-root"):
        raise ValueError("Set the CPU output root under .runtime-work")
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release

    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    for name, value in {
        "construction.json": "{}\n", "runner.py": "# synthetic lifecycle probe\n",
        "trace.jsonl": "{}\n", "video_frames.jsonl": "{}\n",
        "acquisition-provenance.json": json.dumps({"provenance_kind": "synthetic_fixture",
                                                     "diagnostic_fixture": True}) + "\n",
    }.items():
        (root / name).write_text(value)
    try:
        seal_capture(root, frames=1, restoration={"restored": False}, errors=[],
                     encoder_exit_codes={"overview": 0})
    except ValueError as error:
        if "verified restoration" not in str(error):
            raise
    else:
        raise ValueError("Unrestored synthetic capture was sealed")
    seal = seal_capture(root, frames=1, restoration={"restored": True}, errors=[],
                        encoder_exit_codes={"overview": 0})
    if seal["events"] != ["capture_finished", "encoders_closed", "restoration_verified"]:
        raise ValueError("Capture closure order differs")
    exited = record_native_exit(root)
    if exited["event"] != "native_exit":
        raise ValueError("Native process exit receipt missing")
    released = acknowledge_owner_release(root, root / "owner-release.json", True)
    if released["event"] != "owner_released":
        raise ValueError("Owner-release receipt missing")
    print("synthetic CPU lifecycle ordering passed; no physical Native capture claimed")
    print("capture_finished encoders_closed restoration_verified native_exit owner_released saved_processing_started")


if __name__ == "__main__":
    main()
