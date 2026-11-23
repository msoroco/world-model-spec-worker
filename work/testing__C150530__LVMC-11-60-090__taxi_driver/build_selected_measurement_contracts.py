"""Emit one pinned-schema measurement contract per exact case."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    specifications = (
        ("cab_stand_context", "measure_cab_stand_context", "sourced_context",
         ["reviewed-context.json", "original-trace.jsonl", "original-trace-seal.json"]),
        ("posted_notice_context", "measure_posted_notice_context", "sourced_context",
         ["reviewed-context.json"]),
        ("first_intersection_maneuver", "measure_first_intersection_maneuver", "measured",
         ["reviewed-context.json", "original-trace.jsonl", "original-trace-seal.json"]),
    )
    for case in plan["cases"]:
        rows = []
        for disposition, (key, method, kind, inputs) in zip(
                plan["requirement_dispositions"], specifications):
            rows.append({"disposition_index": disposition["disposition_index"],
                         "requirement": disposition["requirement"],
                         "source": disposition["source"], "output_key": key,
                         "method": method, "kind": kind, "value_type": "object",
                         "inputs": inputs})
        contract = {"format": "worker-measurement-contract",
                    "case_id": case["case_id"], "requirements": rows,
                    "negative": {"remove": ["reviewed-context.json"],
                                 "error_contains": "Missing required source: reviewed-context.json"}}
        suffix = case["case_id"].removeprefix(plan["assignment_id"] + "__")
        path = ROOT / "cases" / suffix / "selected-measurement-contract.json"
        path.write_text(json.dumps(contract, indent=2) + "\n")


if __name__ == "__main__":
    build()
