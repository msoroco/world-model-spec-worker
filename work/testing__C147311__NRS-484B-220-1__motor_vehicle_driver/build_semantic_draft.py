"""Bind four exact one-way probes to the frozen law and unresolved source needs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from one_way_direction import CASES
from reviewed_source import FIELDS

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    plan = json.loads((HERE / "case-plan.json").read_text())
    assignment_path = REPO / "inputs" / HERE.name / "assignment.json"
    assignment = json.loads(assignment_path.read_text())
    if (plan.get("assignment_id") != HERE.name or assignment.get("assignment_id") != HERE.name
            or plan.get("law_text") != "Upon a highway designated and signposted for one-way traffic a vehicle shall be driven only in the direction designated."):
        raise ValueError("frozen one-way law or assignment differs")
    expected = {HERE.name + "__" + case.name: case for case in CASES}
    if {row["case_id"] for row in plan["cases"]} != set(expected):
        raise ValueError("exact four-case roster differs")
    comparisons = plan.get("comparisons", [])
    if len(comparisons) != 4 or any(len(row.get("case_ids", [])) != 2 or
                                    not set(row["case_ids"]) <= set(expected)
                                    for row in comparisons):
        raise ValueError("exact comparison roster differs")
    cases = []
    for row in plan["cases"]:
        case = expected[row["case_id"]]
        if row["lane"] != case.lane or row["travel_probe"] != case.direction:
            raise ValueError("lane or direction probe differs")
        cases.append({"case_id": row["case_id"], "target_law_id": plan["law_id"],
                      "requested_lane": case.lane, "requested_direction": case.direction,
                      "original_source_fields": list(FIELDS),
                      "observables": ["source-reviewed designated road vector",
                                      "original ego position and velocity at 20 Hz",
                                      "authorized sign governance over selected route",
                                      "selected same-direction lane and original camera frame joins"],
                      "physical_risk_assessment": row["physical_risk"],
                      "existing_recording_policy": row["recording_policy"],
                      "source_review_status": "pending_original_bytes",
                      "physical_acceptance_claimed": False, "legal_judgment": "unresolved"})
    result = {"format": "c147311-source-gated-semantic-draft-v1",
              "assignment_id": HERE.name, "law_id": plan["law_id"],
              "law_text": plan["law_text"],
              "assignment_sha256": sha(assignment_path),
              "case_plan_sha256": sha(HERE / "case-plan.json"),
              "cases": cases,
              "comparisons": [{"comparison_id": row["comparison_id"],
                               "case_ids": row["case_ids"],
                               "deliberate_differences": row["deliberate_differences"],
                               "realized_difference_claimed": False}
                              for row in comparisons],
              "canonical_proposal_status": "pending reviewed source and selected recording descriptions",
              "physical_acceptance_claimed": False, "legal_judgment": "unresolved"}
    target = HERE / "proposals" / "semantic-draft.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return {"cases": len(cases), "comparisons": len(comparisons), "sha256": sha(target)}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
