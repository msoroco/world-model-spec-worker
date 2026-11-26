"""Exercise the pinned synthetic capture closure and saved-only lifecycle."""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--validator", required=True)
    args = parser.parse_args()
    if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "").endswith("c329654-output"):
        raise ValueError("Set the assignment scratch output root before runtime import")
    repo = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo / "runtime"))
    sys.path.insert(0, str(repo / "runtime/scenario_pipeline"))
    sys.path.insert(0, str(repo / "runtime/python"))
    from scenario_pipeline.worker_exchange.native_output import seal_capture
    from scenario_pipeline.worker_exchange.saved_processing import (
        acknowledge_owner_release, record_native_exit, run)

    scratch = repo / ".runtime-work"
    with tempfile.TemporaryDirectory(dir=scratch, prefix="c329654-lifecycle-") as name:
        root = Path(name)
        attempt = root / "attempt"
        shutil.copytree(args.source, attempt)
        seal = seal_capture(attempt, frames=600,
                            restoration={"restored": True,
                                         "scope": "synthetic fixture with no CARLA server"},
                            errors=[], encoder_exit_codes={"overview": 0,
                            "approach": 0, "reference_corner": 0,
                            "driver_reference": 0})
        native_exit = record_native_exit(attempt)
        owner = acknowledge_owner_release(attempt, attempt / "owner-release.json", True)
        processed = run(args.manifest, args.case, attempt, root / "processed",
                        repo / "runtime/library", args.validator,
                        attempt / "owner-release.json")
        events = seal["events"] + [native_exit["event"], owner["event"]]
        events += [processed["events"][0]]
        expected = ["capture_finished", "encoders_closed", "restoration_verified",
                    "native_exit", "owner_released", "saved_processing_started"]
        if events != expected or processed["passed"] is not True:
            raise AssertionError((events, processed.get("passed")))
        print(json.dumps({"format": "c329654-synthetic-lifecycle-proof-v1",
                          "case_id": args.case, "events": events,
                          "recorded_only": processed["recorded_only"],
                          "originals_preserved": processed["originals_preserved"],
                          "synthetic_fixture": True,
                          "native_server_allocated": False}, sort_keys=True))


if __name__ == "__main__":
    main()
