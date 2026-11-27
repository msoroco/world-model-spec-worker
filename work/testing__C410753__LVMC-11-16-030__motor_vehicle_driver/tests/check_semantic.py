"""Validate source-hashed exact railway semantic stages against selected cases."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))
from worker_exchange.semantic_delivery import validate


def main():
    assignment = json.loads((REPO / "inputs" / HERE.name / "assignment.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    entries = []
    for case in plan["cases"]:
        key = case["case_id"].removeprefix(HERE.name + "__")
        entries.append({"case_id": case["case_id"],
                        "construction": "cases/" + key + "/construction.json"})
    result = validate(HERE, assignment, {"cases": entries})
    if result["selected_cases"] != 7 or result["stage_count"] != 6:
        raise ValueError("rail exact semantic stages differ")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
