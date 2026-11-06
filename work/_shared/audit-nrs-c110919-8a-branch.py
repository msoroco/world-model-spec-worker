"""Independent pending-branch mapping audit for NRS 484B.307(8)(a)."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
LAW="NRS-484B-307-8a"
ASSIGNMENT="training__C110919__NRS-484B-307-8a__motor_vehicle_driver"
source=json.loads((ROOT/"inputs/coverage/branch-sources.json").read_text())["laws"][LAW]
matrix=json.loads((ROOT/"work/_shared/branch-coverage.json").read_text())["laws"][LAW]
plan=json.loads((ROOT/"work"/ASSIGNMENT/"case-plan.json").read_text())
branches=matrix["branches"]
if len(branches)!=6 or set().union(*(set(b["topic_ids"]) for b in branches))!=set(source["topics"]):
    raise ValueError("Six source-grounded branches required")
if any(b["status"]!="pending_review" or b["assignment_id"]!=ASSIGNMENT for b in branches):
    raise ValueError("Partial branch was promoted or rebound")
ids={c["case_id"] for c in plan["cases"]}
comparisons={c["comparison_id"]:set(c["case_ids"]) for c in plan["comparisons"]}
right=next(b for b in branches if b["branch_id"].startswith("right_turn_after_stop"))
if set(right["case_ids"])!=ids or len(right["comparison_ids"])!=1 or comparisons[right["comparison_ids"][0]]!=ids:
    raise ValueError("Right-turn controlled case binding differs")
print(json.dumps({"passed":True,"law_id":LAW,"source_topics":len(source["topics"]),
                  "branches_mapped":6,"runnable_branches":0,
                  "coverage_sha256":hashlib.sha256((ROOT/"work/_shared/branch-coverage.json").read_bytes()).hexdigest()},sort_keys=True))
