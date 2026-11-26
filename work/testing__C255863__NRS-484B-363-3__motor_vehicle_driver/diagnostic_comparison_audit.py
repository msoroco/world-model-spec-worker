"""Verify exact school-zone diagnostic comparison isolation without legal claims."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from diagnostic_delivery_audit import diagnostic


FIXED = ("crossing_zone_rect_m",)
REQUESTED = ("children_present", "school_session", "operation_window",
             "beacon_operational", "beacon_flashing", "sign_limit_active")


def audit(comparison_id: str, left: Path, right: Path) -> dict:
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    pair = next((x for x in plan["comparisons"] if x["comparison_id"] == comparison_id), None)
    if pair is None:
        raise ValueError("unknown school-zone comparison")
    ids = pair["case_ids"]
    for case_id, attempt in zip(ids, (left, right)):
        diagnostic(case_id, attempt)
    a, b = (json.loads((Path(attempt) / "context.json").read_text())
            for attempt in (left, right))
    for key in FIXED:
        if a.get(key) != b.get(key):
            raise ValueError("fixed diagnostic geometry differs: " + key)
    differing = [key for key in REQUESTED if a.get(key) != b.get(key)]
    expected = {"children_presence": ["children_present"],
                "school_session": ["school_session", "operation_window"],
                "operation_half_hour": ["operation_window"],
                "beacon_class_flash": ["beacon_flashing"],
                "sign_without_beacon": ["beacon_operational", "beacon_flashing", "sign_limit_active"]}[comparison_id]
    if differing != expected:
        raise ValueError("diagnostic intervention differs from declared comparison")
    cameras = [json.loads((Path(attempt) / "cameras.json").read_text())
               for attempt in (left, right)]
    if cameras[0]["views"] != cameras[1]["views"] or cameras[0]["frame_count"] != cameras[1]["frame_count"]:
        raise ValueError("diagnostic camera protocol differs")
    return {"comparison_id": comparison_id, "case_ids": ids,
            "left_context_sha256": hashlib.sha256((Path(left) / "context.json").read_bytes()).hexdigest(),
            "right_context_sha256": hashlib.sha256((Path(right) / "context.json").read_bytes()).hexdigest(),
            "deliberate_difference_checked": differing,
            "fixed_diagnostic_context_and_camera_protocol_checked": True,
            "original_fixed_sources_unverified": True,
            "diagnostic_fixture": True, "physical_acceptance": "unverified",
            "legal_judgment": "unresolved"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.comparison, args.left, args.right),
                                      sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
