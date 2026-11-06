"""Independent pending source and controlled-comparison bindings for center turn lanes."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
matrix_path = ROOT / "work/_shared/branch-coverage.json"
matrix = json.loads(matrix_path.read_text())["laws"]
sources = json.loads((ROOT / "inputs/coverage/branch-sources.json").read_text())["laws"]
counts = {}
for law, count in (("NRS-484B-223-3b", 2), ("NRS-484B-223-3c", 1)):
    aid = "training__C394300__" + law + "__motor_vehicle_driver"
    plan = json.loads((ROOT / "work" / aid / "case-plan.json").read_text())
    branches = matrix[law]["branches"]
    if len(branches) != count:
        raise ValueError("Center-lane branch count differs: " + law)
    cases = {c["case_id"] for c in plan["cases"]}
    comparisons = {c["comparison_id"]: set(c["case_ids"]) for c in plan["comparisons"]}
    covered = set()
    for branch in branches:
        if branch["status"] != "pending_review" or branch["assignment_id"] != aid:
            raise ValueError("Unproven branch promoted or rebound")
        if set(branch["topic_ids"]) != set(sources[law]["topics"]):
            raise ValueError("Source topics differ")
        if len(branch["comparison_ids"]) != 1:
            raise ValueError("Comparison binding count differs")
        cid = branch["comparison_ids"][0]
        if set(branch["case_ids"]) != comparisons[cid]:
            raise ValueError("Branch case comparison differs")
        covered.update(branch["case_ids"])
    if covered != cases:
        raise ValueError("Case missing from source branch map")
    counts[law] = count
print(json.dumps({"passed": True, "pending_branches": counts, "runnable_branches": 0,
                  "coverage_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest()}, sort_keys=True))
