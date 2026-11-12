"""Stage a source-bound exact curve approach direction and controlled pair."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "case-plan.json"
PROPOSALS = HERE / "proposals/cases.json"
SHORT = {"short_of_500ft": "short", "at_500ft": "at", "beyond_500ft": "beyond"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(probe, direction):
    short = SHORT[probe]
    name = "canonical-curve-" + short + "-" + ("a" if direction == "approach_a" else "b")
    case_id = HERE.name + "__curve__" + probe + "__occluded_" + direction
    manifest_path = HERE / ("diagnostic-" + name + "-manifest.json")
    entry = json.loads(manifest_path.read_text())["cases"][0]
    receipt = json.loads((HERE / ("branch-proof-" + name) / "build-receipt.json").read_text())
    if (entry["case_id"] != case_id or receipt["case_id"] != case_id or
            sha(HERE / entry["construction"]) != entry["construction_sha256"] or
            receipt["construction_sha256"] != entry["construction_sha256"] or
            receipt["probe"] != probe or receipt["occluded_direction"] != direction):
        raise ValueError("Distinct curve construction not source bound")
    plan = json.loads(PLAN.read_text())
    if not any(row["case_id"] == case_id for row in plan["cases"]):
        plan["cases"].append({
            "case_id": case_id, "feature": "curve", "probe": probe,
            "occluded_direction": direction, "target_law_id": "NRS-484B-407",
            "gap_ids": ["new-sightline-evidence"],
            "description": "Distinct curve approach sight diagnostic; physical outcome unverified.",
            "diagnostic_manifest": manifest_path.name,
            "diagnostic_manifest_sha256": sha(manifest_path),
        })
    for row in plan["requirement_dispositions"]:
        if row["requirement"].startswith("At the U-turn site") or row["requirement"].startswith(
                "Retain original vehicle body and heading reversal at a sourced curve"):
            if case_id not in row["case_ids"]:
                row["case_ids"].append(case_id)
    ids = {row["case_id"] for row in plan["cases"]}
    left = HERE.name + "__curve__" + probe + "__occluded_approach_a"
    right = HERE.name + "__curve__" + probe + "__occluded_approach_b"
    comparison_id = "curve_" + short + "_approach_direction"
    if left in ids and right in ids and not any(
            row["comparison_id"] == comparison_id for row in plan["comparisons"]):
        plan["comparisons"].append({
            "comparison_id": comparison_id, "case_ids": [left, right],
            "fixed_conditions": ["same authored curve road, actor and U-turn controller",
                                 "same " + probe + " probe",
                                 "same 55-second 20 Hz source-camera profile"],
            "deliberate_differences": ["occluded_direction"],
        })
    PLAN.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    proposals = json.loads(PROPOSALS.read_text())
    if not any(row["case_id"] == case_id for row in proposals["cases"]):
        baseline = next(row for row in proposals["cases"] if row["case_id"] ==
                        HERE.name + "__curve__" + probe)
        proposal = copy.deepcopy(baseline)
        proposal["case_id"] = case_id
        proposal["rationale"] = "Curve U-turn with " + direction + " sight source"
        proposal["variable_assignments"]["occluded_direction"] = {
            "kind": "world_setup", "value": direction, "unit": "categorical"}
        proposal["deliberate_differences"] = ["occluded_direction"]
        proposals["cases"].append(proposal)
    PROPOSALS.write_text(json.dumps(proposals, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"staged_exact_case_id": case_id,
                      "comparison_count": len(plan["comparisons"])}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", choices=tuple(SHORT), required=True)
    parser.add_argument("--direction", choices=("approach_a", "approach_b"), required=True)
    arguments = parser.parse_args()
    main(arguments.probe, arguments.direction)
