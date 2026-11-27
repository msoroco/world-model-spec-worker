"""Independent two-case arm-method contrast on saved diagnostic sources."""
import argparse
import json
from pathlib import Path
import sys


FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(FOLDER / "native"))
from audit_arm_cases import audit_comparison


def audit(root_a, root_b, case_a, case_b, comparison):
    result = audit_comparison({case_a: Path(root_a), case_b: Path(root_b)},
                              [case_a, case_b], diagnostic_fixture=True)
    methods = [item["requested_method"] for item in result["case_source_audits"]]
    if comparison.endswith("__comparison"):
        expected = ["right_horizontal", "none"]
    elif comparison.endswith("__general_vs_exception"):
        expected = ["right_horizontal", "left_upward"]
    else:
        raise ValueError("Unknown exact comparison")
    if methods != expected:
        raise ValueError("Comparison arm methods differ from selected pair")
    result.update({"comparison_id": comparison,
                   "measured_methods": methods,
                   "physical_acceptance": False,
                   "legal_verdict": None})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for option in ("root-a", "root-b", "case-a", "case-b", "comparison", "output"):
        parser.add_argument("--" + option, required=True)
    args = parser.parse_args()
    result = audit(args.root_a, args.root_b, args.case_a, args.case_b, args.comparison)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"comparison_id": args.comparison,
                      "measured_methods": result["measured_methods"],
                      "diagnostic_fixture": True,
                      "physical_acceptance": False}))
