"""Bind each selected statutory requirement to the saved original packet."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE / "case-plan.json").read_text())
OUTPUTS = ("nearest_view_location_observation", "yield_approach_observation",
           "through_traffic_crossing_observation", "signal_exception_observation")
SOURCES = ["nearest-view-original.json", "camera-frame-map.json",
           "camera-sources.json"]


def build() -> list[Path]:
    written = []
    for case in PLAN["cases"]:
        case_id = case["case_id"]
        suffix = case_id.rsplit("__", 1)[1]
        folder = HERE / "cases" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        requirements = []
        for index, disposition in enumerate(PLAN["requirement_dispositions"]):
            if case_id not in disposition["case_ids"]:
                continue
            requirements.append({"disposition_index": index,
                "requirement": disposition["requirement"],
                "source": disposition["source"],
                "output_key": OUTPUTS[index], "method": "report",
                "value_type": "object", "kind": "measured", "inputs": SOURCES})
        payload = {"format": "worker-measurement-contract", "requirements": requirements,
                   "negative": {"remove": ["nearest-view-original.json"],
                                "error_contains": "Missing required source: nearest-view-original.json"}}
        path = folder / "measurement-contract.json"
        path.write_text(json.dumps(payload, indent=2) + "\n")
        written.append(path)
    return written


if __name__ == "__main__":
    print("authored", len(build()), "exact case measurement contracts")
