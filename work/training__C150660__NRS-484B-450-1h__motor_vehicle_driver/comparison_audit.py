"""Independent CPU review of selected contrast isolation and source bindings."""

import argparse
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
POSITION = ("position_request", "requested_setting")
ACTIVITY = ("activity_request",)
EXCEPTION = ("exception_request",)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(comparison_id, negative=False):
    plan = json.loads((FOLDER / "case-plan.json").read_text())
    comparison = next(c for c in plan["comparisons"] if c["comparison_id"] == comparison_id)
    cases = {c["case_id"]: c for c in plan["cases"]}
    members = [cases[case_id] for case_id in comparison["case_ids"]]
    suffix = comparison_id.removeprefix(FOLDER.name + "__")
    varied = EXCEPTION if suffix.endswith("_exception") else (
        ACTIVITY if suffix == "stop_stand_park" else POSITION)
    fixed = {"fixed_conditions", "camera_plan", "target_law_id", "source_topic_ids"}
    for member in members:
        if member["target_law_id"] != plan["law_id"] or member["planning_status"] != "selected_pending_original_source_review":
            raise ValueError("Comparison includes wrong law or unselected source")
        case_suffix = member["case_id"].removeprefix(FOLDER.name + "__")
        recipe = json.loads((FOLDER / "native/diagnostic" / case_suffix / "fixture-recipe.json").read_text())
        for source in recipe["sources"]:
            if sha(ROOT / source["source"]) != source["sha256"]:
                raise ValueError("Comparison fixture source changed")
    if negative:
        members = [dict(member) for member in members]
        members[-1]["camera_plan"] = {"duration_seconds": 1}
    for key in fixed:
        if any(member[key] != members[0][key] for member in members[1:]):
            raise ValueError("Comparison fixed condition changed: " + key)
    if all(tuple(member[key] for key in varied) ==
           tuple(members[0][key] for key in varied) for member in members[1:]):
        raise ValueError("Comparison lacks deliberate selected variable")
    if suffix in ("end_boundary", "start_boundary") and [member["requested_setting"] for member in members] != [25.0, 30.0, 35.0]:
        raise ValueError("Exact curb-end threshold probe missing")
    return {"format": "worker-comparison-isolation", "comparison_id": comparison_id,
            "passed": True, "case_ids": comparison["case_ids"],
            "varied_keys": varied, "fixed_keys": sorted(fixed),
            "original_native_outcomes_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.comparison, args.negative)))
