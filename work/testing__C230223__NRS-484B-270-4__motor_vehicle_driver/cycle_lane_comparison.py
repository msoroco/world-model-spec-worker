"""Independent exact-pair audit over source-verified original measurements.

The source audit runs first. These joins check isolation of each planned
change, then report observations without assigning legal or physical verdicts.
"""
from __future__ import annotations

import json
from pathlib import Path

from cycle_lane_intersection import ASSIGNMENT
from cycle_lane_original import audit


def audit_pairs(attempts: dict, reviews: dict) -> dict:
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    required = {case["case_id"] for case in plan["cases"]}
    if set(attempts) != required or set(reviews) != required:
        raise ValueError("all four exact original attempts and independent reviews required")
    measures = {}
    for case_id in sorted(required):
        review = reviews[case_id]
        if not isinstance(review, dict):
            raise ValueError("independent review hashes required")
        measures[case_id] = audit(attempts[case_id], review.get("site"),
                                  review.get("subsection_3"), review.get("vehicle"))
    if len({value["attempt_source_sha256"] for value in measures.values()}) != 4:
        raise ValueError("four distinct source attempts required")
    out = []
    for comparison in plan["comparisons"]:
        ids = comparison["case_ids"]
        if len(ids) != 2 or any(case_id not in measures for case_id in ids):
            raise ValueError("invalid planned comparison")
        a, b = (measures[case_id] for case_id in ids)
        if (a["site_sha256"] != b["site_sha256"] or
                a["vehicle_sha256"] != b["vehicle_sha256"] or
                a["capture_profile_sha256"] != b["capture_profile_sha256"] or
                a["exception_clause_sha256"] != b["exception_clause_sha256"]):
            raise ValueError("comparison fixed source conditions changed: " + comparison["comparison_id"])
        pair = comparison["comparison_id"]
        overlap_a = a["intersection_cycle_lane_overlap_frames"]
        overlap_b = b["intersection_cycle_lane_overlap_frames"]
        if pair in ("intersection_overlap", "lane_designation"):
            if (overlap_a <= 0 or overlap_b != 0 or
                    a["subsection_3_status"] != "does_not_apply" or
                    b["subsection_3_status"] != "does_not_apply"):
                raise ValueError("controlled overlap observations missing: " + pair)
        elif pair == "subsection_3_exception":
            if (overlap_a <= 0 or overlap_b <= 0 or
                    a["subsection_3_status"] != "does_not_apply" or
                    b["subsection_3_status"] != "unresolved"):
                raise ValueError("controlled subsection 3 observations missing")
        else:
            raise ValueError("unrecognized exact comparison: " + pair)
        out.append({"comparison_id": pair, "case_ids": ids,
                    "overlap_frames": [overlap_a, overlap_b],
                    "subsection_3_status": [a["subsection_3_status"], b["subsection_3_status"]],
                    "fixed_source_verified": True, "legal_verdict": None,
                    "physical_acceptance_claimed": False})
    return {"format": "cycle-lane-comparison-audit-v1", "assignment_id": ASSIGNMENT,
            "source_kind": "original_native", "measurements": measures,
            "comparisons": out, "legal_verdict": None,
            "physical_acceptance_claimed": False}
