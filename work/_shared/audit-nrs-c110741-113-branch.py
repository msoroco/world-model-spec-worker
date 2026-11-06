"""Independent pending source/cell audit for three backing prohibitions."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAW = "NRS-484B-113-2"
matrix_path = ROOT / "work/_shared/branch-coverage.json"
branches = json.loads(matrix_path.read_text())["laws"][LAW]["branches"]
source = json.loads((ROOT / "inputs/coverage/branch-sources.json").read_text())["laws"][LAW]
review = json.loads((ROOT / "work/training__C110741__NRS-484B-113-2__motor_vehicle_driver/statutory-review.json").read_text())
expected = {"back_on_or_over_crosswalk": "C110741", "back_into_intersection": "C110763",
            "back_around_street_corner": "C110812"}
if len(branches) != 3 or set().union(*(set(b["topic_ids"]) for b in branches)) != set(source["topics"]):
    raise ValueError("Three exact source branches required")
for branch in branches:
    name = branch["branch_id"].removesuffix("__" + LAW)
    aid = "training__" + expected[name] + "__" + LAW + "__motor_vehicle_driver"
    if branch["status"] != "pending_review" or branch["assignment_id"] != aid:
        raise ValueError("Branch promoted or rebound")
    record = next(x for x in review["assignments"] if x["assignment_id"] == aid)
    assignment = ROOT / "inputs" / aid / "assignment.json"
    if hashlib.sha256(assignment.read_bytes()).hexdigest() != record["input_sha256"]:
        raise ValueError("Frozen assignment differs")
crosswalk = next(b for b in branches if b["branch_id"].startswith("back_on_or_over_crosswalk"))
plan = json.loads((ROOT / "work" / crosswalk["assignment_id"] / "case-plan.json").read_text())
cases = {x["case_id"] for x in plan["cases"]}
comparisons = {x["comparison_id"]: set(x["case_ids"]) for x in plan["comparisons"]}
if set(crosswalk["case_ids"]) != cases or len(crosswalk["comparison_ids"]) != 1 or comparisons[crosswalk["comparison_ids"][0]] != cases:
    raise ValueError("Crosswalk comparison binding differs")
print(json.dumps({"passed": True, "law_id": LAW, "branches_mapped": 3,
                  "runnable_branches": 0, "coverage_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest()}, sort_keys=True))
