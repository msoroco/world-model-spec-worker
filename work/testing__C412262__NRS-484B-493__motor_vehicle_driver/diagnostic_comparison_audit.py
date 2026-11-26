"""CPU comparison isolation on explicitly synthetic nine-frame packages."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import VARIABLES
from diagnostic_delivery_audit import audit_diagnostic
from street_scene_construction import ASSIGNMENT, load_case


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(comparison: str, left: Path, right: Path) -> dict:
    if comparison not in VARIABLES:
        raise ValueError("unknown exact one-way comparison")
    ids = [ASSIGNMENT + "__park_left_notice", ASSIGNMENT + "__" + comparison]
    cases = [load_case(cid) for cid in ids]
    attempts = [Path(left), Path(right)]
    for cid, attempt in zip(ids, attempts):
        audit_diagnostic(cid, attempt)
    contexts = [json.loads((attempt / "context.json").read_text()) for attempt in attempts]
    cameras = [json.loads((attempt / "cameras.json").read_text()) for attempt in attempts]
    if cameras[0] != cameras[1] or cameras[0].get("frame_count") != 9:
        raise ValueError("fixed diagnostic camera protocol differs")
    if comparison != "park_left_notice_reverse_geometry":
        if contexts[0].get("permitted_direction_centerline_xy_m") != contexts[1].get(
                "permitted_direction_centerline_xy_m"):
            raise ValueError("fixed diagnostic permitted-direction geometry differs")
    variable = VARIABLES[comparison][0]
    if cases[0][variable] == cases[1][variable]:
        raise ValueError("declared comparison intervention did not differ")
    for key in ("activity_request", "vehicle_side_request", "notice_request",
                "street_direction_request"):
        for context, case in zip(contexts, cases):
            if context.get(key) != case[key]:
                raise ValueError("diagnostic context intervention differs: " + key)
        if key != variable and contexts[0][key] != contexts[1][key]:
            raise ValueError("undeclared diagnostic intervention differs: " + key)
    return {"assignment_id": ASSIGNMENT, "comparison_id": comparison,
            "case_ids": ids, "diagnostic_fixture": True,
            "source_context_sha256": [sha(attempt / "context.json") for attempt in attempts],
            "fixed_diagnostic_context_and_camera_protocol_checked": True,
            "deliberate_difference_checked": True,
            "original_fixed_sources_unverified": True,
            "physical_acceptance": "unverified", "legal_judgment": "unresolved"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True, choices=tuple(VARIABLES))
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.comparison, args.left, args.right),
                                      sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
