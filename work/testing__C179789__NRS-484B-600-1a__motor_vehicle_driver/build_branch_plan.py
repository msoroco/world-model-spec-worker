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
RISK = {
    "reference": ("The reviewed lane and leader spawn may not sustain a 900-frame, four-view travel window.",
                  "A Native spawn fails, the controller stops progress, or a required view misses either participant."),
    "faster": ("The requested higher ego speed may close the fixed leader gap and trigger safety braking before the steady window.",
               "The original steady ego-speed mean misses its request or emergency braking dominates frames 180-899."),
    "nearer_traffic": ("The smaller authored leader gap may prevent a safe same-lane spawn or trigger sustained emergency braking.",
                      "Native spawn fails, measured leader clearance is absent, or the brake remains active in the steady window."),
    "wet_surface": ("Native wetness and optional wheel friction may not produce a distinct measured paved-surface condition.",
                    "Original wetness or friction readback does not differ from the reference, or the road material cannot be verified."),
    "narrower": ("A narrower OpenDRIVE driving section may lack the requested width or enough forward same-lane route for both vehicles.",
                 "OpenDRIVE width readback differs, the leader route changes lane, or either spawn fails."),
    "rain": ("Native precipitation may impair required four-view participant visibility without a distinct retained weather readback.",
             "The original precipitation readback matches the reference or a required view loses the vehicle bodies."),
    "fog": ("Native fog may obscure the leader or roadway in the required views before the planned observation ends.",
            "The original fog readback matches the reference or a required view loses the leader or road context."),
}


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
                          "physical_risk_assessment": {
                              "risk": RISK[cid.rsplit("__", 1)[-1]][0],
                              "failure_trigger": RISK[cid.rsplit("__", 1)[-1]][1],
                              "fallback_candidates": [],
                              "fallback_decision": "No alternate construction selected before a reviewed roadway and camera source packet identifies a feasible alternate."},
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
    plan["requirement_dispositions"] = [{
        "requirement": "NRS-484B-600-1a",
        "source": {"path": "inputs/" + HERE.name + "/assignment.json",
                   "sha256": hashlib.sha256((REPO / "inputs" / HERE.name /
                                            "assignment.json").read_bytes()).hexdigest()},
        "status": "selected_required",
        "case_ids": list(cases),
        "method": "Measure original speed, traffic, roadway width, surface, weather and visibility; legal reasonableness remains unresolved.",
        "evidence_or_gap": "Source law and frozen witness are identified; original Native measurements and legal judgment remain pending.",
    }]
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
