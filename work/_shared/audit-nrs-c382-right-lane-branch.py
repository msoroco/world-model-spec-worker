"""Independent source and comparison binding audit for right-only lane duties."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
matrix_path = ROOT / "work/_shared/branch-coverage.json"
matrix = json.loads(matrix_path.read_text())["laws"]
sources = json.loads((ROOT / "inputs/coverage/branch-sources.json").read_text())["laws"]
mapping = {"NRS-484B-400-1": "C382355", "NRS-484B-223-4a": "C382355",
           "NRS-484B-223-4b": "C382389"}
runnable = 0
for law, cell in mapping.items():
    aid = "training__" + cell + "__" + law + "__motor_vehicle_driver"
    plan = json.loads((ROOT / "work" / aid / "case-plan.json").read_text())
    branches = matrix[law]["branches"]
    if len(branches) != 1:
        raise ValueError("Expected one exact clause branch: " + law)
    branch = branches[0]
    expected_status = "pending_review" if law == "NRS-484B-400-1" else "runnable"
    if branch["status"] != expected_status or branch["assignment_id"] != aid:
        raise ValueError("Branch status or assignment binding differs")
    runnable += branch["status"] == "runnable"
    if set(branch["topic_ids"]) != set(sources[law]["topics"]):
        raise ValueError("Source topics differ")
    cases = {c["case_id"] for c in plan["cases"]}
    comparisons = {c["comparison_id"]: set(c["case_ids"]) for c in plan["comparisons"]}
    if set(branch["case_ids"]) != cases or len(branch["comparison_ids"]) != 1 or comparisons[branch["comparison_ids"][0]] != cases:
        raise ValueError("Case or comparison binding differs")
print(json.dumps({"passed": True, "laws_mapped": list(mapping), "runnable_branches": runnable,
                  "coverage_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest()}, sort_keys=True))
