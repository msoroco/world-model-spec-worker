"""Independent partial statutory mapping audit for LVMC 11.52.130(A)(11)."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
LAW="LVMC-11-52-130-A11"
ASSIGNMENT="training__C110454__LVMC-11-52-130-A11__motor_vehicle_driver"
source=json.loads((ROOT/"inputs/coverage/branch-sources.json").read_text())["laws"][LAW]
matrix=json.loads((ROOT/"work/_shared/branch-coverage.json").read_text())["laws"][LAW]
plan=json.loads((ROOT/"work"/ASSIGNMENT/"case-plan.json").read_text())
cases={item["case_id"] for item in plan["cases"]}
comparisons={item["comparison_id"]:set(item["case_ids"]) for item in plan["comparisons"]}
branches=matrix["branches"]
if len(branches)!=5:raise ValueError("Five statutory mapping branches required")
if set().union(*(set(b["topic_ids"]) for b in branches))!=set(source["topics"]):
    raise ValueError("Source topics omitted or invented")
for branch in branches:
    if branch["status"]!="pending_review" or branch["assignment_id"]!=ASSIGNMENT:
        raise ValueError("Partial branch was misrepresented as runnable")
    selected=set(branch["case_ids"])
    if len(selected)<2 or not selected<=cases:raise ValueError("Mapped case IDs differ")
    if len(branch["comparison_ids"])!=1 or selected!=comparisons.get(branch["comparison_ids"][0]):
        raise ValueError("Mapped comparison does not hold branch cases")
print(json.dumps({"passed":True,"law_id":LAW,"source_topics":len(source["topics"]),
                  "branches_mapped":len(branches),"runnable_branches":0,
                  "coverage_sha256":hashlib.sha256((ROOT/"work/_shared/branch-coverage.json").read_bytes()).hexdigest()},sort_keys=True))
