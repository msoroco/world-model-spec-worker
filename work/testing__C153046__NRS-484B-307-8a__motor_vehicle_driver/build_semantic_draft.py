"""Bind the eight requested red-left probes without assigning legal verdicts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    plan = json.loads((HERE / "case-plan.json").read_text())
    source = REPO / "inputs" / HERE.name / "assignment.json"
    assignment = json.loads(source.read_text())
    if (plan.get("assignment_id") != HERE.name or assignment.get("assignment_id") != HERE.name
            or plan.get("law_id") != assignment.get("law_id") or len(plan.get("cases", [])) != 8
            or len(plan.get("comparisons", [])) != 5):
        raise ValueError("exact assignment case or comparison roster differs")
    cases = []
    for row in plan["cases"]:
        variables = row["draft_variables"]
        if (not row["case_id"].startswith(HERE.name + "__")
                or variables.get("signal_request") != "steady_red_alone"
                or variables.get("receiving_direction") not in {"one_way_left", "two_way"}
                or variables.get("approach_position") not in {"extreme_left", "inner_lane"}):
            raise ValueError("red-left case variables differ")
        cases.append({
            "case_id": row["case_id"], "target_law_id": plan["law_id"],
            "requested_variables": variables,
            "applicability_probe": variables["receiving_direction"] != "one_way_left"
                or variables["approach_position"] != "extreme_left",
            "observations": [
                {"name": "official_steady_red_alone", "source": "official_signal",
                 "measurement": "original signal actor and per-frame state"},
                {"name": "stop_reference_hierarchy", "source": "stop_reference",
                 "measurement": "reviewed near-side crosswalk, sign or marking, else intersection boundary"},
                {"name": "actual_stop_before_entry", "source": "native_world_snapshot",
                 "measurement": "full ego body, speed and frame/time before first boundary entry"},
                {"name": "approach_and_receiving_lanes", "source": "one_way_routes or two_way_routes",
                 "measurement": "reviewed lane directions and original ego body/route"},
                {"name": "directed_conflict_and_yield", "source": "native_world_snapshot",
                 "measurement": "signal-directed pedestrian/traffic body history and ego entry order"},
            ],
            "physical_risk_assessment": row["physical_risk_assessment"],
            "original_source_status": "pending_review",
            "physical_acceptance_claimed": False, "legal_judgment": "unresolved",
        })
    ids = {case["case_id"] for case in cases}
    comparisons = []
    for row in plan["comparisons"]:
        if len(row["case_ids"]) != 2 or not set(row["case_ids"]) <= ids:
            raise ValueError("comparison references missing exact case")
        comparisons.append({"comparison_id": row["comparison_id"],
                            "case_ids": row["case_ids"],
                            "deliberate_differences": row["deliberate_differences"],
                            "realized_difference_claimed": False})
    result = {"format": "c153046-source-gated-semantic-draft-v1",
              "assignment_id": HERE.name, "law_id": plan["law_id"],
              "law_source_sha256": sha(source), "case_plan_sha256": sha(HERE / "case-plan.json"),
              "law_text": plan["law_text"],
              "red_alone_duty": "Stop at the applicable source-reviewed boundary and remain stopped until green, subject to stated exceptions.",
              "left_turn_exception": "After stopping, extreme-left one-way approach may turn left only into one-way road to left and must yield to pedestrians and signal-directed traffic.",
              "cases": cases, "comparisons": comparisons,
              "canonical_proposal_status": "pending original site and source-grounded recording descriptions",
              "legal_judgment": "unresolved", "physical_acceptance_claimed": False}
    target = HERE / "proposals" / "semantic-draft.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return {"cases": len(cases), "comparisons": len(comparisons), "sha256": sha(target)}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
