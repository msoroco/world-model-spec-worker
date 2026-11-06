"""Independent pending source/case bindings for three short exact clauses."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
matrix_path = ROOT / "work/_shared/branch-coverage.json"
matrix = json.loads(matrix_path.read_text())["laws"]
sources = json.loads((ROOT / "inputs/coverage/branch-sources.json").read_text())["laws"]
mapping = (("C10316", "NRS-484B-293", "pedestrian", "right half of crosswalks"),
           ("C102304", "NRS-484B-127-1", "motor_vehicle_driver", "reasonable and prudent"),
           ("C10014", "NRS-484B-477-2", "motor_vehicle_driver", "within an alley"))
for cell, law, actor, source_phrase in mapping:
    aid = "training__" + cell + "__" + law + "__" + actor
    plan = json.loads((ROOT / "work" / aid / "case-plan.json").read_text())
    branches = matrix[law]["branches"]
    if len(branches) != 1 or source_phrase not in sources[law]["law"]["text"]:
        raise ValueError("Exact source branch differs: " + law)
    branch = branches[0]
    if branch["status"] != "pending_review" or branch["assignment_id"] != aid:
        raise ValueError("Unproven branch promoted or rebound")
    if set(branch["topic_ids"]) != set(sources[law]["topics"]):
        raise ValueError("Source topics differ")
    cases = {c["case_id"] for c in plan["cases"]}
    comparisons = {c["comparison_id"]: set(c["case_ids"]) for c in plan["comparisons"]}
    if set(branch["case_ids"]) != cases or len(branch["comparison_ids"]) != 1 or comparisons[branch["comparison_ids"][0]] != cases:
        raise ValueError("Comparison binding differs")
print(json.dumps({"passed": True, "laws_mapped": [item[1] for item in mapping],
                  "runnable_branches": 0, "coverage_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest()}, sort_keys=True))
