"""Independent pending source/case audit for motorcycle red-signal exception."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAW = "NRS-484B-307-8d"
AID = "training__C110919__NRS-484B-307-8d__motorcycle_or_moped_operator"
source = json.loads((ROOT / "inputs/coverage/branch-sources.json").read_text())["laws"][LAW]
matrix_path = ROOT / "work/_shared/branch-coverage.json"
branches = json.loads(matrix_path.read_text())["laws"][LAW]["branches"]
review = json.loads((ROOT / "work" / AID / "statutory-review.json").read_text())
plan = json.loads((ROOT / "work" / AID / "case-plan.json").read_text())
expected = {b["id"]: set(b["source_topics"]) for b in review["branches"]}
actual = {b["branch_id"].removesuffix("__" + LAW): set(b["topic_ids"]) for b in branches}
if actual != expected or set().union(*actual.values()) != set(source["topics"]):
    raise ValueError("Six source branches differ")
if any(b["status"] != "pending_review" or b["assignment_id"] != AID for b in branches):
    raise ValueError("Unproven branch promoted or rebound")
cases = {c["case_id"] for c in plan["cases"]}
comparisons = {c["comparison_id"]: set(c["case_ids"]) for c in plan["comparisons"]}
for name in ("two_complete_cycles_and_signal_nonresponse", "motorcycle_right_turn_failed_detection_witness"):
    branch = next(b for b in branches if b["branch_id"].startswith(name))
    if set(branch["case_ids"]) != cases or len(branch["comparison_ids"]) != 1 or comparisons[branch["comparison_ids"][0]] != cases:
        raise ValueError("Motorcycle comparison binding differs")
if review["physical_observation_claimed"] or review["cpu_readiness"]:
    raise ValueError("Synthetic cycles cannot certify physical fault or delivery")
print(json.dumps({"passed": True, "law_id": LAW, "branches_mapped": len(branches),
                  "runnable_branches": 0, "coverage_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest()}, sort_keys=True))
