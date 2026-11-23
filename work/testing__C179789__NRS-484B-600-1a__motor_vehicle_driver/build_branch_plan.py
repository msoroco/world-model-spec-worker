"""Bind the six frozen basic-speed comparisons without assigning legal labels."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REVIEW = REPO / "inputs" / HERE.name / "review-context" / "review.json"
CHANGES = {
    "speed": "ego_speed_request_mps",
    "traffic": "leader_initial_gap_m",
    "surface": "surface_wetness_request",
    "width": "highway_width_m",
    "weather": "native_precipitation_request",
    "visibility": "native_fog_request",
}
FIXED = ["same paved roadway and travel direction", "same motor vehicle actor",
         "same observation window and four-view camera profile",
         "all authored setup variables except the declared comparison variable"]


def build() -> dict:
    review_bytes = REVIEW.read_bytes()
    review = json.loads(review_bytes)
    if review["law_id"] != "NRS-484B-600-1a" or review["cell_id"] != "C179789":
        raise ValueError("frozen review law or cell differs")
    if {c["id"] for c in review["comparisons"]} != set(CHANGES):
        raise ValueError("frozen comparison inventory differs")
    source_ref = {"path": str(REVIEW.relative_to(REPO)),
                  "sha256": hashlib.sha256(review_bytes).hexdigest()}
    cases = {}
    comparisons = []
    for comparison in review["comparisons"]:
        case_ids = [case["case_id"] for case in comparison["cases"]]
        if len(case_ids) != 2 or case_ids[0] == case_ids[1]:
            raise ValueError("expected one exact paired review comparison")
        for case in comparison["cases"]:
            cid = case["case_id"]
            if not cid.startswith(HERE.name + "__"):
                raise ValueError("foreign case identity")
            if cid in cases and cases[cid]["accepted_recording_id"] != case["recording_id"]:
                raise ValueError("shared reference changed recording identity")
            cases[cid] = {"case_id": cid, "target_law_id": "NRS-484B-600-1a",
                          "target_type": "judgment_sweep_member",
                          "accepted_recording_id": case["recording_id"],
                          "review_description": case["description"],
                          "source_ref": source_ref,
                          "preparation_status": "source_measurement_pending",
                          "legal_judgment": "unresolved",
                          "physical_acceptance_claimed": False}
        comparisons.append({"comparison_id": comparison["id"], "case_ids": case_ids,
            "fixed_conditions": FIXED,
            "deliberate_differences": [CHANGES[comparison["id"]]],
            "source_ref": source_ref, "measurement_status": "original_bytes_unavailable",
            "legal_judgment": "unresolved"})
    if len(cases) != 7 or len(comparisons) != 6:
        raise ValueError("seven unique cases and six pairs required")
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    plan["cases"] = list(cases.values())
    plan["comparisons"] = comparisons
    plan["observations"] = [
        {"name": "ego_speed_mps", "source": "original actor velocity at each Native frame", "unit": "m/s"},
        {"name": "leader_gap_m", "source": "original ego and leader body polygons", "unit": "m"},
        {"name": "highway_width_m", "source": "original OpenDRIVE lane bounds at sampled position", "unit": "m"},
        {"name": "surface_wetness", "source": "original road-surface material and Native wetness", "unit": "native fraction"},
        {"name": "precipitation_strength", "source": "original Native weather snapshot per frame", "unit": "CARLA percent"},
        {"name": "fog_density", "source": "original Native weather snapshot per frame", "unit": "CARLA percent"},
        {"name": "tire_friction", "source": "original wheel physics readback per frame", "unit": "dimensionless"},
    ]
    plan["planning_status"] = "seven_exact_cases_six_comparisons_original_measurement_pending"
    plan["runtime_uncertainties"] = [
        "Accepted metadata and authored review settings do not supply original speed, traffic, surface, width, weather or wheel samples.",
        "Actual CARLA motion, road material, weather readback and four-view pixels need later original capture or retained source review.",
    ]
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return plan


if __name__ == "__main__":
    result = build()
    print(f"bound {len(result['cases'])} exact cases and {len(result['comparisons'])} comparisons")
