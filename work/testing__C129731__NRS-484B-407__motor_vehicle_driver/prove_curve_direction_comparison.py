"""Verify the curve direction source pair and reject swapped exact identities."""

import argparse
import json
from pathlib import Path

from curve_direction_comparison import HERE, ROOT, SHORT, audit


def main(probe):
    short = SHORT[probe][0]
    attempts = {direction: ROOT / ".runtime-work" /
                ("c129731-canonical-curve-" + short + "-" + suffix + "-compat-v1")
                for direction, suffix in (("approach_a", "a"), ("approach_b", "b"))}
    report = audit(probe, attempts)
    plan = json.loads((HERE / "case-plan.json").read_text())
    declared = next(row for row in plan["comparisons"] if
                    row["comparison_id"] == report["comparison_id"])
    if (declared["case_ids"] != report["case_ids"] or
            declared["deliberate_differences"] != [report["deliberate_difference"]]):
        raise ValueError("Curve comparison declaration differs")
    swapped = {"approach_a": attempts["approach_b"], "approach_b": attempts["approach_a"]}
    try:
        audit(probe, swapped)
    except ValueError as error:
        report["negative_identity_rejection"] = str(error)
    else:
        raise ValueError("Swapped curve exact identities accepted")
    output = HERE / ("canonical-curve-" + short + "-comparison-proof.json")
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"comparison_id": report["comparison_id"],
                      "software_checks_passed": True,
                      "negative_identity_rejection": report["negative_identity_rejection"],
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", choices=tuple(SHORT), required=True)
    args = parser.parse_args()
    main(args.probe)
