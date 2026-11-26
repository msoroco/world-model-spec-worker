"""Bind explicit stop, stand and park action pairs to the full statute."""
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
PLAN = FOLDER / "case-plan.json"
ASSIGNMENT = FOLDER.name


def main():
    plan = json.loads(PLAN.read_text())
    park = [case for case in plan["cases"] if "__condition_" in case["case_id"] and
            "__stop_condition_" not in case["case_id"] and "__stand_condition_" not in case["case_id"]]
    if len(park) != 2:
        raise ValueError("Original angle pair missing")
    cases = list(park)
    comparisons = [item for item in plan["comparisons"] if item["comparison_id"].endswith("__comparison")]
    for action in ("stop", "stand"):
        ids = []
        for letter, original in zip("ab", park):
            clone = json.loads(json.dumps(original))
            clone["case_id"] = ASSIGNMENT + f"__selected_03f318de__{action}_condition_{letter}"
            clone["comparison_variable"] = "at_rest_heading_relative_to_device_angle"
            clone["source_action"] = action
            clone["action_source"] = "Native controller request, context and frame samples; original physical activity requires independent review"
            clone["condition_index"] = 0 if letter == "a" else 1
            cases.append(clone)
            ids.append(clone["case_id"])
        comparison = json.loads(json.dumps(comparisons[0]))
        comparison["comparison_id"] = ASSIGNMENT + f"__selected_03f318de__{action}_comparison"
        comparison["case_ids"] = ids
        comparison["deliberate_differences"] = ["at_rest_heading_relative_to_device_angle"]
        comparison["status"] = "constructed_cpu_proofs_pending"
        comparison["audit_gap"] = "Original activity, device and curb pixels require independent review."
        comparisons.append(comparison)
    plan["cases"] = cases
    plan["comparisons"] = comparisons
    for disposition in plan["requirement_dispositions"]:
        disposition["case_ids"] = [case["case_id"] for case in cases]
        disposition["evidence_or_gap"] = "Stop, stand and park 45-degree and 70-degree source-bound pairs prepared; original physical activity and device/curb pixels remain for review."
    PLAN.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"cases": len(cases), "comparisons": len(comparisons)}))


if __name__ == "__main__":
    main()
