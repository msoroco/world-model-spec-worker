"""Bind the four selected witness rows to exact saved source measurements."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUTS = ["case-scope.json", "analytic_sight.jsonl", "curve_context.json"]
OUTPUTS = {0: "crest_grade_and_two_direction_sight",
           1: "crest_demo_681ce_geometry", 2: "crest_demo_fa163_geometry",
           3: "curve_or_crest_two_direction_sight"}


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    rows = plan["requirement_dispositions"]
    if len(rows) != 4 or any(row["status"] != "selected_required" for row in rows):
        raise ValueError("all four exact witness requirements must be selected")
    for suffix in ("probe_01", "probe_02", "probe_03"):
        case_id = HERE.name + "__" + suffix
        required = []
        for index, row in enumerate(rows):
            if case_id not in row["case_ids"]:
                continue
            required.append({"disposition_index": index,
                "requirement": row["requirement"], "source": row["source"],
                "output_key": OUTPUTS[index],
                "method": "measure_curve_or_crest" if index == 3 else "measure_crest_grade",
                "value_type": "object", "kind": "measured", "inputs": INPUTS})
        if not required:
            raise ValueError("selected case has no witness measurements")
        contract = {"format": "worker-measurement-contract", "case_id": case_id,
                    "requirements": required,
                    "negative": {"remove": ["analytic_sight.jsonl"],
                                 "error_contains": "Missing required source: analytic_sight.jsonl"},
                    "scope": "source-bound diagnostic measurements; original physical outcome unverified"}
        target = HERE / "selected-contracts" / (suffix + ".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(contract, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"cases": 3, "selected_requirements": 4}))


if __name__ == "__main__":
    main()
