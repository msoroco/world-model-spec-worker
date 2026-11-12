"""Independently compare the distinct exact crest placement/direction cases."""

import json
from pathlib import Path

from crest_branch_comparison import HERE, audit_canonical_pairs

ROOT = HERE.parents[1]
NAMES = ("canonical-at-approach-b", "canonical-at-near-b", "canonical-at-approach-a", "canonical-at-near-a")


def main():
    attempts = {
        name: ROOT / (".runtime-work/c129731-" + name + "-compat-v" + ("3" if name.endswith("approach-b") else "1"))
        for name in NAMES
    }
    report = audit_canonical_pairs(attempts)
    plan = json.loads((HERE / "case-plan.json").read_text())
    declared = {row["comparison_id"]: row for row in plan["comparisons"]}
    for comparison_id, row in zip(("crest_at_b_placement", "crest_at_approach_direction",
                                   "crest_at_a_placement", "crest_at_near_direction"), report["comparisons"]):
        item = declared[comparison_id]
        if item["case_ids"] != row["case_ids"] or item["deliberate_differences"] != [row["deliberate_difference"]]:
            raise ValueError("Exact comparison declaration/source pair differs")
    swapped = dict(attempts)
    swapped[NAMES[0]], swapped[NAMES[1]] = swapped[NAMES[1]], swapped[NAMES[0]]
    try:
        audit_canonical_pairs(swapped)
    except ValueError as error:
        report["negative_identity_rejection"] = str(error)
    else:
        raise ValueError("Swapped exact case identity was accepted")
    (HERE / "canonical-at-comparison-proof.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"software_checks_passed": True, "negative_identity_rejection": report["negative_identity_rejection"],
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
