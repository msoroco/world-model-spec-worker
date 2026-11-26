"""Prove the pinned capture/exit/release ordering on a zero-resource fixture."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
private = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
if not private or not Path(private).resolve().is_relative_to(REPO / ".runtime-work"):
    raise RuntimeError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    suffix = args.case.rsplit("__", 1)[-1]
    construction = ROOT / ("construction.json" if suffix == "business_sufficient" else "cases/" + suffix + "/construction.json")
    if json.loads(construction.read_text())["case_id"] != args.case:
        raise ValueError("lifecycle fixture case differs")
    Path(private).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lifecycle-", dir=private) as temp:
        root = Path(temp)
        (root / "construction.json").write_bytes(construction.read_bytes())
        (root / "runner.py").write_text("# synthetic zero-resource lifecycle protocol\n")
        (root / "trace.jsonl").write_text('{"frame":101,"time_s":0.0}\n')
        (root / "video_frames.jsonl").write_text('{"video_frame":0,"carla_frame":101,"time_s":0.0}\n')
        (root / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        }) + "\n")
        try:
            seal_capture(root, frames=1, restoration={"restored": False}, errors=[])
        except ValueError as error:
            if "verified restoration" not in str(error):
                raise
        else:
            raise AssertionError("unrestored source sealed")
        seal = seal_capture(root, frames=1, restoration={"restored": True}, errors=[],
                            encoder_exit_codes={"synthetic_overview": 0})
        if seal["events"] != ["capture_finished", "encoders_closed", "restoration_verified"]:
            raise AssertionError("capture event ordering differs")
        exit_receipt = record_native_exit(root)
        if exit_receipt["event"] != "native_exit":
            raise AssertionError("exit event absent")
        owner = root / "owner-release.json"
        release = acknowledge_owner_release(root, owner, True)
        if release["event"] != "owner_released":
            raise AssertionError("zero-resource owner release absent")
        _closure(root, owner, "synthetic_fixture", True)
        try:
            seal_capture(root, frames=1, restoration={"restored": True}, errors=[])
        except ValueError as error:
            if "Retain existing" not in str(error):
                raise
        else:
            raise AssertionError("duplicate capture seal accepted")
        print(args.case, "capture_finished encoders_closed restoration_verified native_exit owner_released saved_processing_started")
        print("synthetic zero-resource lifecycle protocol only; no original Native capture or owner release claimed")


if __name__ == "__main__":
    main()
