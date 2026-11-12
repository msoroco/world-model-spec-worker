"""Stage a distinct exact crest alternative in the existing case plan."""

import hashlib
import json
import copy
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "case-plan.json"
PROPOSALS = HERE / "proposals/cases.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--placement", choices=("near_summit", "approach_to_crest"), default="approach_to_crest")
    parser.add_argument("--direction", choices=("approach_a", "approach_b"), default="approach_b")
    parser.add_argument("--probe", choices=("short_of_500ft", "at_500ft", "beyond_500ft"), default="at_500ft")
    args = parser.parse_args()
    suffix = {"short_of_500ft": "short", "at_500ft": "at", "beyond_500ft": "beyond"}[args.probe]
    name = "canonical-" + suffix + "-" + ("near" if args.placement == "near_summit" else "approach") + ("-a" if args.direction == "approach_a" else "-b")
    manifest_path = HERE / ("diagnostic-" + name + "-manifest.json")
    expected_case = HERE.name + "__crest__" + args.probe + "__" + args.placement + "__occluded_" + args.direction
    manifest = json.loads(manifest_path.read_text())
    entry = manifest["cases"][0]
    case = entry["case_id"]
    build = json.loads((HERE / ("branch-proof-" + name) / "build-receipt.json").read_text())
    if (case != expected_case or
            sha(HERE / entry["construction"]) != entry["construction_sha256"] or
            build["construction_sha256"] != entry["construction_sha256"] or
            build["case_id"] != case or build["probe"] != args.probe or
            build["placement"] != args.placement or
            build["occluded_direction"] != args.direction):
        raise ValueError("Distinct crest case is not source bound")
    plan = json.loads(PLAN.read_text())
    if not any(row["case_id"] == case for row in plan["cases"]):
        plan["cases"].append({
            "case_id": case, "feature": "crest", "probe": args.probe,
            "site_placement": args.placement, "occluded_direction": args.direction,
            "target_law_id": "NRS-484B-407", "gap_ids": ["new-sightline-evidence"],
            "description": "Distinct crest placement/direction sight diagnostic at the statutory boundary; physical outcome unverified.",
            "diagnostic_manifest": manifest_path.name,
            "diagnostic_manifest_sha256": sha(manifest_path),
        })
    for row in plan["requirement_dispositions"]:
        if row["requirement"].startswith("At the crest U-turn site") or row["requirement"].startswith(
                "Retain original vehicle body and heading reversal near a sourced grade crest"):
            if case not in row["case_ids"]:
                row["case_ids"].append(case)
    plan["runtime_uncertainties"] = [
        "Selected and staged diagnostic cases have CPU software proofs; actual Native capture, pixels and site review remain unverified.",
        "The pinned sight-distance proxy uses virtual observers 1.4 m above lane waypoints and ego center/corners; it does not establish an actual driver-eye view.",
    ]
    ids = {row["case_id"] for row in plan["cases"]}
    if args.probe == "at_500ft":
        pairs = (
            ("crest_at_b_placement", "approach_to_crest", "approach_b", "near_summit", "approach_b", "site_placement"),
            ("crest_at_approach_direction", "approach_to_crest", "approach_b", "approach_to_crest", "approach_a", "occluded_direction"),
            ("crest_at_a_placement", "approach_to_crest", "approach_a", "near_summit", "approach_a", "site_placement"),
            ("crest_at_near_direction", "near_summit", "approach_b", "near_summit", "approach_a", "occluded_direction"),
        )
    elif args.probe == "short_of_500ft":
        pairs = (
            ("crest_short_b_placement", "approach_to_crest", "approach_b", "near_summit", "approach_b", "site_placement"),
            ("crest_short_approach_direction", "approach_to_crest", "approach_b", "approach_to_crest", "approach_a", "occluded_direction"),
            ("crest_short_a_placement", "approach_to_crest", "approach_a", "near_summit", "approach_a", "site_placement"),
            ("crest_short_near_direction", "near_summit", "approach_b", "near_summit", "approach_a", "occluded_direction"),
        )
    else:
        pairs = (
            ("crest_beyond_b_placement", "approach_to_crest", "approach_b", "near_summit", "approach_b", "site_placement"),
            ("crest_beyond_approach_direction", "approach_to_crest", "approach_b", "approach_to_crest", "approach_a", "occluded_direction"),
            ("crest_beyond_a_placement", "approach_to_crest", "approach_a", "near_summit", "approach_a", "site_placement"),
            ("crest_beyond_near_direction", "near_summit", "approach_b", "near_summit", "approach_a", "occluded_direction"),
        )
    for cid, p1, d1, p2, d2, variable in pairs:
        left = HERE.name + "__crest__" + args.probe + "__" + p1 + "__occluded_" + d1
        right = HERE.name + "__crest__" + args.probe + "__" + p2 + "__occluded_" + d2
        if left in ids and right in ids and not any(row["comparison_id"] == cid for row in plan["comparisons"]):
            plan["comparisons"].append({
                "comparison_id": cid, "case_ids": [left, right],
                "fixed_conditions": ["same authored crest road, actor and U-turn controller", "same " + args.probe + " probe", "same 55-second 20 Hz source-camera profile", "same " + ("occluded_direction" if variable == "site_placement" else "site_placement")],
                "deliberate_differences": [variable],
            })
    PLAN.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    proposals = json.loads(PROPOSALS.read_text())
    if not any(row["case_id"] == case for row in proposals["cases"]):
        baseline = next(row for row in proposals["cases"] if row["case_id"] ==
                        HERE.name + "__crest__" + args.probe)
        proposal = copy.deepcopy(baseline)
        proposal["case_id"] = case
        proposal["rationale"] = "Crest U-turn at " + args.placement + " with " + args.direction + " source ray"
        proposal["variable_assignments"]["site_placement"] = {
            "kind": "world_setup", "value": args.placement, "unit": "categorical"}
        proposal["variable_assignments"]["occluded_direction"] = {
            "kind": "world_setup", "value": args.direction, "unit": "categorical"}
        proposal["deliberate_differences"] = ["site_placement", "occluded_direction"]
        proposals["cases"].append(proposal)
    PROPOSALS.write_text(json.dumps(proposals, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"staged_exact_case_id": case, "diagnostic_manifest_sha256": sha(manifest_path),
                      "comparison_count": len(plan["comparisons"])}))


if __name__ == "__main__":
    main()
