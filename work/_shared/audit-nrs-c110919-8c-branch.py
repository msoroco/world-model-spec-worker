"""Independent pending statutory mapping audit for NRS 484B.307(8)(c)."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAW = "NRS-484B-307-8c"
AID = "training__C110919__NRS-484B-307-8c__motor_vehicle_driver"
source = json.loads((ROOT / "inputs/coverage/branch-sources.json").read_text())["laws"][LAW]
matrix_path = ROOT / "work/_shared/branch-coverage.json"
branches = json.loads(matrix_path.read_text())["laws"][LAW]["branches"]
plan = json.loads((ROOT / "work" / AID / "case-plan.json").read_text())
review = json.loads((ROOT / "work" / AID / "statutory-review.json").read_text())
expected = {item["id"]: set(item["source_topics"]) for item in review["branches"]}
actual = {b["branch_id"].removesuffix("__" + LAW): set(b["topic_ids"]) for b in branches}
if actual != expected or set().union(*actual.values()) != set(source["topics"]):
    raise ValueError("Source branches differ")
if any(b["status"] != "pending_review" or b["assignment_id"] != AID for b in branches):
    raise ValueError("Unproven branch was promoted or rebound")
turn = next(b for b in branches if b["branch_id"].startswith("right_turn_after_stop"))
cases = {c["case_id"] for c in plan["cases"]}
comparisons = {c["comparison_id"]: set(c["case_ids"]) for c in plan["comparisons"]}
if set(turn["case_ids"]) != cases or len(turn["comparison_ids"]) != 1 or comparisons[turn["comparison_ids"][0]] != cases:
    raise ValueError("Right-turn comparison binding differs")
print(json.dumps({"passed": True, "law_id": LAW, "branches_mapped": len(branches),
                  "runnable_branches": 0, "coverage_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest()}, sort_keys=True))
