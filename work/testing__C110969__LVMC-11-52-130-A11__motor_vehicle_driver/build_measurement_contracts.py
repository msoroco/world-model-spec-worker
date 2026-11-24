"""Bind each selected statutory phrase to its saved original observation files."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
METHODS = (
    ("observed_activity", "measure_activity", ["original-attempt/attempt.json", "original-attempt/pose.jsonl"]),
    ("observed_intersection_gap", "measure_boundary", ["original-attempt/attempt.json", "original-attempt/map-geometry.json"]),
    ("observed_traffic", "measure_traffic", ["original-attempt/attempt.json", "original-attempt/context.jsonl"]),
    ("observed_police_direction", "measure_police", ["original-attempt/attempt.json", "original-attempt/context.jsonl"]),
    ("observed_device_direction", "measure_device", ["original-attempt/attempt.json", "original-attempt/context.jsonl"]),
)


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    dispositions = plan["requirement_dispositions"]
    if len(dispositions) != len(METHODS):
        raise ValueError("Exact statutory disposition list differs")
    for case in plan["cases"]:
        suffix = case["case_id"].removeprefix(HERE.name + "__")
        rows = []
        for disposition, (key, method, inputs) in zip(dispositions, METHODS):
            if case["case_id"] not in disposition["case_ids"]:
                raise ValueError("Missing exact case disposition")
            rows.append({"disposition_index": disposition["disposition_index"],
                         "requirement": disposition["requirement"],
                         "source": disposition["source"], "output_key": key,
                         "method": method, "kind": "measured" if method in
                         ("measure_activity", "measure_boundary") else "sourced_context",
                         "value_type": "object", "inputs": inputs})
        contract = {"format": "worker-measurement-contract", "case_id": case["case_id"],
                    "requirements": rows,
                    "negative": {"remove": ["original-attempt/context.jsonl"],
                                 "error_contains": "Missing required source: original-attempt/context.jsonl"},
                    "legal_necessity": "unresolved"}
        path = HERE / "cases" / suffix / "measurement-contract.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(contract, indent=2) + "\n")
    print("built", len(plan["cases"]), "source-bound measurement contracts")


if __name__ == "__main__":
    main()
