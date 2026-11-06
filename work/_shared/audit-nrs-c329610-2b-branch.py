"""Independent pending source and plan binding audit for NRS 484B.400(2)(b)."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAW = "NRS-484B-400-2b"
AID = "training__C329610__NRS-484B-400-2b__motor_vehicle_driver"
source = json.loads((ROOT / "inputs/coverage/branch-sources.json").read_text())["laws"][LAW]
matrix_path = ROOT / "work/_shared/branch-coverage.json"
entry = json.loads(matrix_path.read_text())["laws"][LAW]
plan = json.loads((ROOT / "work" / AID / "case-plan.json").read_text())
if len(entry["branches"]) != 1:
    raise ValueError("Expected one exact-clause branch")
branch = entry["branches"][0]
if set(branch["topic_ids"]) != set(source["topics"]):
    raise ValueError("Source topics differ")
if branch["status"] != "pending_review" or branch["assignment_id"] != AID:
    raise ValueError("Unproven branch was promoted or rebound")
cases = {c["case_id"] for c in plan["cases"]}
comparisons = {c["comparison_id"]: set(c["case_ids"]) for c in plan["comparisons"]}
if set(branch["case_ids"]) != cases or len(branch["comparison_ids"]) != 1 or comparisons[branch["comparison_ids"][0]] != cases:
    raise ValueError("Case or comparison binding differs")
text = source["law"]["text"]
if "After entering the intersection" not in text or "right of the centerline" not in text:
    raise ValueError("Exit-side duty source differs")
print(json.dumps({"passed": True, "law_id": LAW, "branches_mapped": 1,
                  "runnable_branches": 0, "coverage_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest()}, sort_keys=True))
