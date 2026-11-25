"""Bind each exact C111278 law observation to saved original sources."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEYS = ("qualifying_intersection_context", "last_100ft_sight_observation",
        "traversal_speed_observation", "through_street_exception",
        "traffic_control_exception")
INPUTS = ("site.json", "native-sight.json", "native-sight-receipt.json")


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    dispositions = plan["requirement_dispositions"]
    if len(dispositions) != len(KEYS):
        raise ValueError("exact C111278 requirement inventory changed")
    for case in plan["cases"]:
        rows = [{"disposition_index": index, "requirement": disposition["requirement"],
                 "source": disposition["source"], "output_key": KEYS[index],
                 "method": "report", "value_type": "object", "kind": "measured",
                 "inputs": list(INPUTS)} for index, disposition in enumerate(dispositions)
                if disposition["status"] == "selected_required" and
                case["case_id"] in disposition["case_ids"]]
        if len(rows) != len(KEYS):
            raise ValueError("case lacks selected C111278 requirement")
        path = ROOT / "cases" / case["case_key"] / "measurement-contract.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"format": "worker-measurement-contract",
            "requirements": rows,
            "negative": {"remove": ["site.json"],
                         "error_contains": "Missing required source: site.json"}}, indent=2) + "\n")
    print("built", len(plan["cases"]), "exact measurement contracts")


if __name__ == "__main__":
    build()
