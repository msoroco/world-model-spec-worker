"""Independent audit of source-bound synthetic approach measurements."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = Path("inputs/training__C111294__NRS-484B-603-1__motor_vehicle_driver/assignment.json")
PIN = "fdd355041381080ca2a7ca58c33857227647a6739b3b7310f7c6725fe97eccba"


def audit() -> dict:
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != PIN:
        raise AssertionError("Frozen assignment hash differs")
    assignment = json.loads(SOURCE.read_text())
    if assignment["law_record"]["text"] != json.loads((ROOT/"case-plan.json").read_text())["statutory_text"]:
        raise AssertionError("Statutory text differs")
    plan = json.loads((ROOT/"draft-candidates.json").read_text())
    proof = json.loads((ROOT/"approach-proof.json").read_text())
    branch = json.loads(Path("work/_shared/branch-coverage.json").read_text())["laws"]["NRS-484B-603-1"]
    if branch["source_topic_count"] != 2 or branch["branches"][0]["topic_ids"] != ["text-0", "reviewed-scope-0"]:
        raise AssertionError("Frozen statutory topics not mapped")
    if branch["branches"][0]["status"] != "pending_review":
        raise AssertionError("Draft branch misrepresented as runnable")
    if set(branch["branches"][0]["case_ids"]) != {c["case_id"] for c in plan["cases"]}:
        raise AssertionError("Statutory case linkage differs")
    if {c["case_id"] for c in plan["cases"]} != {c["case_id"] for c in json.loads((ROOT/"case-plan.json").read_text())["cases"]}:
        raise AssertionError("Case identity differs")
    if {c["target_relation"] for c in plan["cases"]} != {"measured_early_decrease_held", "measured_no_material_decrease"}:
        raise AssertionError("Controlled relations missing")
    for case in plan["cases"]:
        if [c["name"] for c in case["candidates"]] != ["primary", "fallback1", "fallback2", "fallback3"]:
            raise AssertionError("Four ordered construction targets required")
        if len({json.dumps(c, sort_keys=True) for c in case["candidates"]}) != 4:
            raise AssertionError("Construction targets duplicated")
        suffix = case["case_id"].split("__")[-1]
        contract = json.loads((ROOT/f"draft-measurement-contract-{suffix}.json").read_text())
        if contract["case_id"] != case["case_id"] or len(contract["requirements"]) != 1:
            raise AssertionError("Exact case measurement contract differs")
        requirement = contract["requirements"][0]
        if (requirement["requirement"], requirement["source"], requirement["method"],
                requirement["inputs"]) != ("NRS-484B-603-1", "NRS 484B.603(1)",
                    "measure_intersection_approach", ["native_samples.jsonl", "road.xodr"]):
            raise AssertionError("Statutory source measurement binding differs")
    contract_proof = json.loads((ROOT/"measurement-contract-proof.json").read_text())
    if not contract_proof["passed"] or len(contract_proof["cases"]) != 2:
        raise AssertionError("Pinned contract positives/negatives absent")
    if not all(row["positive"] and row["negative_missing_source"] and
               row["negative_changed_source"] for row in contract_proof["cases"]):
        raise AssertionError("Pinned contract negative missing")
    for name, expected in (("decrease", "measured_early_decrease_held"),
                           ("decrease_reflected", "measured_early_decrease_held"),
                           ("hold", "measured_no_material_decrease")):
        filename = "decrease-reflected" if name == "decrease_reflected" else name
        path = ROOT/"draft-fixtures"/f"{filename}-synthetic-native.jsonl"
        raw = path.read_bytes()
        rows = [json.loads(x) for x in raw.splitlines()]
        receipt = proof["positives"][name]
        if len(rows) != 480 or hashlib.sha256(raw).hexdigest() != receipt["source_sha256"]:
            raise AssertionError("Saved fixture source differs")
        direction = -1 if name == "decrease_reflected" else 1
        approach = [math.dist(r["ego_velocity_mps"], [0, 0, 0])*2.2369362920544
                    for r in rows if -60 <= direction*r["ego_position_m"][1] < -50]
        preentry = [math.dist(r["ego_velocity_mps"], [0, 0, 0])*2.2369362920544
                    for r in rows if -20 <= direction*r["ego_position_m"][1] < -7]
        reduction = sum(approach)/len(approach)-sum(preentry)/len(preentry)
        if abs(reduction-receipt["decrease_mph"]) > .001 or receipt["measured_relation"] != expected:
            raise AssertionError("Independent speed comparison differs")
    return {"passed": True, "frozen_assignment_sha256": PIN,
            "cases": 2, "construction_targets": 8, "synthetic_source_audits": 3,
            "selected_delivery_cases": 0, "physical_observations": 0}


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True))
