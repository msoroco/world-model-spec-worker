"""Bind selected parked-departure requirement to original source files."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / "case-plan.json").read_text())


def build():
    for case in PLAN["cases"]:
        rows = []
        for disposition in PLAN["requirement_dispositions"]:
            if case["case_id"] not in disposition["case_ids"]:
                continue
            rows.append({"disposition_index": disposition["disposition_index"],
                         "requirement": disposition["requirement"],
                         "source": disposition["source"],
                         "kind": "measured", "method": "measure_parked_departure",
                         "output_key": "parked_requirement_0", "value_type": "object",
                         "inputs": ["original-attempt/" + name for name in
                                    ("activity.jsonl", "activity-seal.json",
                                     "frame-map.json", "site.json", "actors.json")]})
        contract = {"format": "worker-measurement-contract", "case_id": case["case_id"],
                    "requirements": rows,
                    "negative": {"remove": ["original-attempt/activity.jsonl"],
                                 "error_contains": "Missing required source: original-attempt/activity.jsonl"}}
        (ROOT / ("measurement-" + case["variant"] + ".json")).write_text(
            json.dumps(contract, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    build()
