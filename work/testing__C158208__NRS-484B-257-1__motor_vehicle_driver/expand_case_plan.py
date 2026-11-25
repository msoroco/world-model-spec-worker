"""Expand C158208's accepted case inventory into a provisional statutory plan.

This does not select production captures or treat accepted metadata as source proof.
"""
from __future__ import annotations

import json
from pathlib import Path

from build_semantic_proposals import KINDS, case_settings


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name


def expand(plan: dict, matrix: dict, frozen: dict) -> dict:
    expected = {ASSIGNMENT + "__" + kind for kind in KINDS}
    accepted = {row["case_id"] for row in
                frozen["local_snapshot"]["memberships"]["demo-test"]
                if row["status"] == "accepted"}
    if expected != accepted or expected != set(matrix["accepted_recordings"]):
        raise ValueError("accepted case inventory and statutory matrix differ")
    if plan.get("assignment_id") != ASSIGNMENT:
        raise ValueError("wrong assignment case plan")
    existing = {row["case_id"]: row for row in plan["cases"]}
    if not set(existing) <= expected:
        raise ValueError("case plan contains an unfrozen case")
    reference = existing[ASSIGNMENT + "__nearest_view_response"]
    for kind in KINDS:
        ident = ASSIGNMENT + "__" + kind
        if ident in existing:
            continue
        settings = case_settings(kind)
        row = json.loads(json.dumps(reference))
        row["case_id"] = ident
        row["purpose"] = ("Prospective source-bound observation of " + kind.replace("_", " ") +
                          "; record original stopping-reference geometry, through-traffic phase, "
                          "ego body response and full intersection time history.")
        row["measurement"] = ("Original stopping reference: " + settings["stopping_reference"] +
                              "; through-traffic phase: " + settings["through_traffic_phase"] +
                              "; measured ego speed/body, occupied or approaching through body, "
                              "first view and across-or-within time history. Legal priority unresolved.")
        row["physical_risk_assessment"] = {
            "status": "physical",
            "risk": "Original C158208 sign, road marking, sidewalk, through route, phase timing and camera pixels are unreviewed; realized motion may differ from configured branch.",
            "fallback_policy": "No source-reviewed alternate construction is selected before an exact Native failure trigger and compatible site survey are available.",
        }
        existing[ident] = row
    plan["cases"] = [existing[ASSIGNMENT + "__" + kind] for kind in KINDS]
    comparisons = {row["comparison_id"]: row for row in plan["comparisons"]}
    for branch in matrix["branches"]:
        ident = branch["branch_id"]
        if ident in comparisons:
            continue
        comparisons[ident] = {
            "comparison_id": ident,
            "case_ids": branch["case_ids"],
            "fixed_conditions": [branch["fixed_conditions"] +
                                 "; preserve original map, cameras, duration and actor role; verify these from source before acceptance"],
            "deliberate_differences": [branch["deliberate_differences"] +
                                     "; evaluate observed trajectories, not controller labels"],
        }
    plan["comparisons"] = list(comparisons.values())
    clauses = {row["requirement"] for row in plan["requirement_dispositions"]}
    for branch in matrix["branches"]:
        clause = "Observe NRS 484B.257(1) branch: " + branch["statutory_clause"]
        if clause in clauses:
            continue
        plan["requirement_dispositions"].append({
            "requirement": clause,
            "source": matrix["law_source"]["path"],
            "status": "alternative_pending",
            "case_ids": branch["case_ids"],
            "evidence_or_gap": "Accepted metadata identifies these cases but original site, Native traces, camera pixels and legal review are absent from this export.",
        })
    plan["planning_status"] = "full accepted case inventory planned; original source and selected production proofs pending"
    return plan


def build() -> dict:
    target = HERE / "case-plan.json"
    plan = json.loads(target.read_text())
    matrix = json.loads((HERE / "statutory-matrix.draft.json").read_text())
    frozen = json.loads((ROOT / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    result = expand(plan, matrix, frozen)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return {"cases": len(result["cases"]), "comparisons": len(result["comparisons"]),
            "requirement_dispositions": len(result["requirement_dispositions"])}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
