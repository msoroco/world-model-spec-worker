"""Verify the two distinct short-of-500-foot crest exact cases against original sources."""

import json

from crest_branch_comparison import HERE, audit_canonical_short_pair

ROOT = HERE.parents[1]
NAMES = ("canonical-short-approach-b", "canonical-short-near-b",
         "canonical-short-approach-a", "canonical-short-near-a")


def main():
    attempts = {name: ROOT / (".runtime-work/c129731-" + name + "-compat-v1") for name in NAMES}
    report = audit_canonical_short_pair(attempts)
    plan = json.loads((HERE / "case-plan.json").read_text())
    declared = {row["comparison_id"]: row for row in plan["comparisons"]}
    for cid, row in zip(("crest_short_b_placement", "crest_short_approach_direction",
                         "crest_short_a_placement", "crest_short_near_direction"), report["comparisons"]):
        if declared[cid]["case_ids"] != row["case_ids"] or declared[cid]["deliberate_differences"] != [row["deliberate_difference"]]:
            raise ValueError("Short comparison declaration/source pair differs")
    swapped = dict(attempts)
    swapped[NAMES[0]], swapped[NAMES[1]] = swapped[NAMES[1]], swapped[NAMES[0]]
    try:
        audit_canonical_short_pair(swapped)
    except ValueError as error:
        report["negative_identity_rejection"] = str(error)
    else:
        raise ValueError("Swapped short exact case identity was accepted")
    (HERE / "canonical-short-comparison-proof.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"software_checks_passed": True, "physical_acceptance_claimed": False,
                      "negative_identity_rejection": report["negative_identity_rejection"]}))


if __name__ == "__main__":
    main()
