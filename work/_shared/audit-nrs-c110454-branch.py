"""Independent partial source-topic audit for NRS 484B.213(2)(b)/(3)."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
LAW="NRS-484B-213-2b"
ASSIGNMENT="training__C110454__NRS-484B-213-2b__motor_vehicle_driver"
source=json.loads((ROOT/"inputs/coverage/branch-sources.json").read_text())["laws"][LAW]
matrix=json.loads((ROOT/"work/_shared/branch-coverage.json").read_text())["laws"][LAW]
plan=json.loads((ROOT/"work"/ASSIGNMENT/"case-plan.json").read_text())
branches=matrix["branches"]
if len(branches)!=4 or set().union(*(set(b["topic_ids"]) for b in branches))!=set(source["topics"]):
    raise ValueError("Four exact statutory alternatives do not cover source topics")
ids={c["case_id"] for c in plan["cases"]}
comparisons={c["comparison_id"]:set(c["case_ids"]) for c in plan["comparisons"]}
for branch in branches:
    if branch["status"]!="pending_review" or branch["assignment_id"]!=ASSIGNMENT:
        raise ValueError("Unproven branch was promoted")
first=branches[0]
if set(first["case_ids"])!=ids or first["comparison_ids"]!=list(comparisons) or comparisons[first["comparison_ids"][0]]!=ids:
    raise ValueError("Intersection approach comparison binding differs")
if set(branches[-1]["topic_ids"])!={"text-2"}:
    raise ValueError("One-way exception topic differs")
print(json.dumps({"passed":True,"law_id":LAW,"branches_mapped":4,
                  "source_topics":len(source["topics"]),"runnable_branches":0,
                  "coverage_sha256":hashlib.sha256((ROOT/"work/_shared/branch-coverage.json").read_bytes()).hexdigest()},sort_keys=True))
