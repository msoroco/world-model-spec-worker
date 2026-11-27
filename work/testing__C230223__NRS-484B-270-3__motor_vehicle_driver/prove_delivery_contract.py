"""CPU protocol proof for exact synthetic attempts and original-source rejection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cycle_lane_2703 import ASSIGNMENT, VIEWS
from cycle_lane_source_audit import audit, decode


def run(case_id: str, mode: str, attempt: Path) -> dict:
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    if case_id not in {case["case_id"] for case in plan["cases"]} or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact selected delivery case required")
    if mode == "delivery-negative":
        audit(attempt, {"site": "0" * 64, "participant": "0" * 64,
                        "context": "0" * 64}, case_id)
        raise ValueError("diagnostic source unexpectedly passed original audit")
    if mode != "diagnostic-positive":
        raise ValueError("unknown delivery protocol mode")
    receipt = json.loads((attempt / "compatibility.json").read_text())
    provenance = json.loads((attempt / "acquisition-provenance.json").read_text())
    required = {"selected_measurements", "negative_case_source", "four_camera_sources",
                "lean_decoder", "final_decode"}
    if (receipt.get("case_id") != case_id or receipt.get("passed") is not True or
            provenance.get("provenance_kind") != "synthetic_fixture" or
            provenance.get("diagnostic_fixture") is not True or
            not required <= set(receipt.get("checks", []))):
        raise ValueError("selected synthetic delivery proof incomplete")
    media = {view: decode(attempt / (view + ".mkv")) for view in VIEWS}
    if any(item["frame_count"] != 900 for item in media.values()):
        raise ValueError("full four-view synthetic decode required")
    return {"case_id": case_id, "scope": "synthetic CPU protocol only",
            "diagnostic_fixture": True, "four_view_full_decode": True,
            "original_delivery_claimed": False, "actual_pixels_claimed": False,
            "physical_completion_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.mode, args.attempt), sort_keys=True))


if __name__ == "__main__":
    main()
