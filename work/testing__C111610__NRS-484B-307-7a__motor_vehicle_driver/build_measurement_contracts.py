"""Bind each selected 7(a) requirement to exact saved original inputs."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE / "case-plan.json").read_text())
KEYS = ("arrow_display_observation", "ego_movement_observation",
        "participant_region_observation", "camera_decode_observation")
INPUTS = ("site.json", "arrow-aspect-original.json", "arrow-events-original.json",
          "arrow-camera-receipt.json")


def build():
    dispositions = PLAN["requirement_dispositions"]
    if len(dispositions) != len(KEYS):
        raise ValueError("exact 7(a) requirement inventory changed")
    for case in PLAN["cases"]:
        case_id = case["case_id"]
        rows = [{"disposition_index": index,
                 "requirement": disposition["requirement"],
                 "source": disposition["source"],
                 "output_key": KEYS[index], "method": "report",
                 "value_type": "object", "kind": "measured",
                 "inputs": list(INPUTS)}
                for index, disposition in enumerate(dispositions)
                if disposition["status"] == "selected_required" and
                   case_id in disposition["case_ids"]]
        if len(rows) != len(KEYS):
            raise ValueError("exact case lacks selected measurement")
        path = HERE / "cases" / case["case_suffix"] / "measurement-contract.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"format": "worker-measurement-contract",
            "requirements": rows,
            "negative": {"remove": ["site.json"],
                         "error_contains": "Missing required source: site.json"}},
            indent=2) + "\n")
    print("built", len(PLAN["cases"]), "exact arrow measurement contracts")


if __name__ == "__main__":
    build()
