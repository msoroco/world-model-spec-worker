"""Exercise pinned capture closure ordering on an exact diagnostic source copy."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("nearest_view_hold", "nearest_view_continue",
                                           "nearest_view_clear", "active_signal_exception"),
                        required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    stage = args.scratch / ("lifecycle-" + args.case)
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    source = args.scratch / ("compat-hold-v5" if args.case == "nearest_view_hold"
                             else "compat-" + args.case + "-v5")
    for name in ("config.json", "trace.jsonl", "video_frames.jsonl",
                 "construction.json", "runner.py", "acquisition-provenance.json"):
        shutil.copyfile(source / name, stage / name)
    sys.path.insert(0, str(Path("runtime/scenario_pipeline").resolve()))
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import (
        record_native_exit, acknowledge_owner_release, _closure)
    seal = seal_capture(stage, frames=900, restoration={"restored": True},
                        errors=[], encoder_exit_codes={"diagnostic": 0})
    assert seal["events"] == ["capture_finished", "encoders_closed",
                              "restoration_verified"]
    rejected = False
    try:
        acknowledge_owner_release(stage, stage / "owner-release.json", True)
    except ValueError:
        rejected = True
    assert rejected, "Premature owner release was accepted"
    record_native_exit(stage)
    acknowledge_owner_release(stage, stage / "owner-release.json", True)
    _closure(stage, stage / "owner-release.json", "synthetic_fixture", True)
    events = seal["events"] + ["native_exit", "owner_released",
                               "saved_processing_started"]
    print(json.dumps({"case": args.case, "events": events,
                      "premature_owner_release_rejected": rejected,
                      "diagnostic_fixture": True,
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
