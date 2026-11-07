"""Bind each planned C111294 case to the four inventoried source topics."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUTS = ("subject_operation", "speed_relation", "unconditional_scope",
           "other_vehicle_context")
METHODS = ("measure_subject_operation", "measure_speed_relation",
           "measure_unconditional_scope", "measure_other_vehicle_context")


def main() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    if len(plan["requirement_dispositions"]) != 4:
        raise ValueError("Four source topics required")
    for case in plan["cases"]:
        case_id = case["case_id"]
        rows = []
        for index, disposition in enumerate(plan["requirement_dispositions"]):
            if case_id not in disposition["case_ids"] or disposition["status"] != "selected_required":
                raise ValueError("Case does not cover the inventoried topic")
            rows.append({"disposition_index": index,
                         "requirement": disposition["requirement"],
                         "source": disposition["source"],
                         "output_key": OUTPUTS[index], "method": METHODS[index],
                         "value_type": "object",
                         "kind": "measured" if index != 2 else "sourced_context",
                         "inputs": ["native_samples.jsonl", "road.xodr"]
                         if index == 2 else ["native_samples.jsonl"]})
        contract = {"format": "worker-measurement-contract-v1",
                    "case_id": case_id, "requirements": rows,
                    "negative": {"remove": ["native_samples.jsonl"],
                                 "error_contains": "Missing required source: native_samples.jsonl"}}
        suffix = case_id.split("__")[-1]
        (ROOT / f"draft-measurement-contract-{suffix}.json").write_text(
            json.dumps(contract, indent=2) + "\n")
    print(json.dumps({"contracts": len(plan["cases"]),
                      "requirements_per_contract": 4,
                      "selected": False}, sort_keys=True))


if __name__ == "__main__":
    main()
