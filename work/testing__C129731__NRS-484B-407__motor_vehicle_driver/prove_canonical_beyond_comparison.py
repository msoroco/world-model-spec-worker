"""Verify four distinct beyond-500-foot crest exact cases and their comparisons."""

import json

from crest_branch_comparison import HERE, audit_canonical_beyond_pairs

ROOT = HERE.parents[1]
NAMES = ("canonical-beyond-approach-b", "canonical-beyond-near-b",
         "canonical-beyond-approach-a", "canonical-beyond-near-a")


def main():
    attempts = {name: ROOT / (".runtime-work/c129731-" + name + "-compat-v1") for name in NAMES}
    report = audit_canonical_beyond_pairs(attempts)
    plan = json.loads((HERE / "case-plan.json").read_text())
    declared = {row["comparison_id"]: row for row in plan["comparisons"]}
    for cid, row in zip(("crest_beyond_b_placement", "crest_beyond_approach_direction",
                         "crest_beyond_a_placement", "crest_beyond_near_direction"), report["comparisons"]):
        if declared[cid]["case_ids"] != row["case_ids"] or declared[cid]["deliberate_differences"] != [row["deliberate_difference"]]:
            raise ValueError("Beyond comparison declaration/source pair differs")
    swapped = dict(attempts)
    swapped[NAMES[0]], swapped[NAMES[1]] = swapped[NAMES[1]], swapped[NAMES[0]]
    try:
        audit_canonical_beyond_pairs(swapped)
    except ValueError as error:
        report["negative_identity_rejection"] = str(error)
    else:
        raise ValueError("Swapped beyond exact case identity was accepted")
    (HERE / "canonical-beyond-comparison-proof.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"software_checks_passed": True, "physical_acceptance_claimed": False,
                      "negative_identity_rejection": report["negative_identity_rejection"]}))


if __name__ == "__main__":
    main()
