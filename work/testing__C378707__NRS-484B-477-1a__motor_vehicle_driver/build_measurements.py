"""Bind exact selected law requirements to original activity source files."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / "case-plan.json").read_text())
INPUTS = {
    0: ("activity.jsonl", "activity-seal.json", "frame-map.json"),
    1: ("activity.jsonl", "activity-seal.json", "actors.json"),
    2: ("activity.jsonl", "site.json"),
}


def build():
    for case in PLAN["cases"]:
        case_id = case["case_id"]
        rows = []
        for disposition in PLAN["requirement_dispositions"]:
            if case_id not in disposition["case_ids"]:
                continue
            index = disposition["disposition_index"]
            rows.append({"disposition_index": index,
                         "requirement": disposition["requirement"],
                         "source": disposition["source"],
                         "kind": "measured" if index != 2 else "sourced_context",
                         "method": "measure_business_alley",
                         "output_key": "business_alley_requirement_" + str(index),
                         "value_type": "object",
                         "inputs": ["original-attempt/" + name for name in INPUTS[index]]})
        contract = {"format": "worker-measurement-contract", "case_id": case_id,
                    "requirements": rows,
                    "negative": {"remove": ["original-attempt/activity.jsonl"],
                                 "error_contains": "Missing required source: original-attempt/activity.jsonl"}}
        path = ROOT / ("measurement-" + case["variant"] + ".json")
        path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    build()
