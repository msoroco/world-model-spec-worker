"""Diagnostic delivery protocol only; original source audit stays source-gated."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from cycle_lane_intersection import ASSIGNMENT
from cycle_lane_delivery import _checked_video
from cycle_lane_original import VIEWS, audit as audit_original


def run(case_id: str, mode: str, attempt: Path) -> dict:
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    if case_id not in {case["case_id"] for case in plan["cases"]} or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact selected delivery case required")
    if mode == "delivery-negative":
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch, prefix="c230223-delivery-negative-") as temporary:
            root = Path(temporary)
            (root / "attempt-source.json").write_text(json.dumps({
                "format": "cycle-lane-native-attempt-v1", "source_kind": "synthetic_fixture",
                "diagnostic_fixture": True, "case_id": case_id}) + "\n")
            audit_original(root, "0" * 64, "0" * 64, "0" * 64)
        raise ValueError("diagnostic source unexpectedly passed original audit")
    if mode != "diagnostic-positive":
        raise ValueError("unknown delivery protocol mode")
    attempt = attempt.resolve()
    receipt = json.loads((attempt / "compatibility.json").read_text())
    provenance = json.loads((attempt / "acquisition-provenance.json").read_text())
    if (receipt.get("case_id") != case_id or receipt.get("passed") is not True or
            provenance.get("provenance_kind") != "synthetic_fixture" or
            provenance.get("diagnostic_fixture") is not True or
            not {"selected_measurements", "negative_case_source", "four_camera_sources",
                 "lean_decoder", "final_decode"} - set(receipt.get("checks", [])) == set()):
        raise ValueError("selected synthetic delivery proof incomplete")
    media = {view: _checked_video(attempt / (view + ".mkv")) for view in VIEWS}
    if any(item["frame_count"] != 900 for item in media.values()):
        raise ValueError("full 900-frame four-view decode required")
    return {"case_id": case_id, "scope": "synthetic CPU protocol only",
            "diagnostic_fixture": True, "four_view_full_decode": True,
            "original_delivery_claimed": False, "actual_pixels_claimed": False,
            "physical_completion_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--attempt", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.mode, args.attempt), sort_keys=True))


if __name__ == "__main__":
    main()
