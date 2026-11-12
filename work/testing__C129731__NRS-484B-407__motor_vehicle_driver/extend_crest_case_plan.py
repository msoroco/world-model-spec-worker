"""Stage a distinct exact crest alternative in the existing case plan."""

import hashlib
import json
import copy
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = "canonical-at-approach-b"
MANIFEST = HERE / ("diagnostic-" + NAME + "-manifest.json")
PLAN = HERE / "case-plan.json"
PROPOSALS = HERE / "proposals/cases.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    entry = manifest["cases"][0]
    case = entry["case_id"]
    build = json.loads((HERE / ("branch-proof-" + NAME) / "build-receipt.json").read_text())
    if (case != HERE.name + "__crest__at_500ft__approach_to_crest__occluded_approach_b" or
            sha(HERE / entry["construction"]) != entry["construction_sha256"] or
            build["construction_sha256"] != entry["construction_sha256"] or
            build["placement"] != "approach_to_crest" or
            build["occluded_direction"] != "approach_b"):
        raise ValueError("Distinct crest case is not source bound")
    plan = json.loads(PLAN.read_text())
    if not any(row["case_id"] == case for row in plan["cases"]):
        plan["cases"].append({
            "case_id": case, "feature": "crest", "probe": "at_500ft",
            "site_placement": "approach_to_crest", "occluded_direction": "approach_b",
            "target_law_id": "NRS-484B-407", "gap_ids": ["new-sightline-evidence"],
            "description": "Distinct approach-to-crest/B sight diagnostic at the 500-foot boundary; physical outcome unverified.",
            "diagnostic_manifest": MANIFEST.name,
            "diagnostic_manifest_sha256": sha(MANIFEST),
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
    PLAN.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    proposals = json.loads(PROPOSALS.read_text())
    if not any(row["case_id"] == case for row in proposals["cases"]):
        baseline = next(row for row in proposals["cases"] if row["case_id"] ==
                        HERE.name + "__crest__at_500ft")
        proposal = copy.deepcopy(baseline)
        proposal["case_id"] = case
        proposal["rationale"] = "Approach-to-crest U-turn with approach B 500-foot source ray"
        proposal["variable_assignments"]["site_placement"] = {
            "kind": "world_setup", "value": "approach_to_crest", "unit": "categorical"}
        proposal["variable_assignments"]["occluded_direction"] = {
            "kind": "world_setup", "value": "approach_b", "unit": "categorical"}
        proposal["deliberate_differences"] = ["site_placement", "occluded_direction"]
        proposals["cases"].append(proposal)
    PROPOSALS.write_text(json.dumps(proposals, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"staged_exact_case_id": case, "diagnostic_manifest_sha256": sha(MANIFEST),
                      "canonical_comparison_pending": True}))


if __name__ == "__main__":
    main()
