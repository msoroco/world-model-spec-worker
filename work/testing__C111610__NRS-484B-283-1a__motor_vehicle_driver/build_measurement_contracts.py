"""Bind the six frozen C111610 requirements to named saved measurements."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / "case-plan.json").read_text())
ROWS = {
    0: ("device_condition", "measure_device", "text", "measured",
        ["capture/site.json"]),
    1: ("directional_half_geometry", "measure_geometry", "object", "sourced_context",
        ["capture/site.json"]),
    2: ("destination_occupancy_frames", "measure_destination", "number", "measured",
        ["capture/site.json", "capture/ego.json", "capture/pedestrian.json"]),
    3: ("opposite_approach_context", "measure_opposite", "object", "measured",
        ["capture/site.json", "capture/ego.json", "capture/pedestrian.json"]),
    4: ("exception_applicability_review", "measure_exceptions", "object", "sourced_context",
        ["capture/exception_review.json"]),
    5: ("operating_device_context", "measure_governing", "object", "sourced_context",
        ["capture/site.json"]),
}


def build():
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        requirements = []
        for index, disposition in enumerate(PLAN["requirement_dispositions"]):
            if (disposition["status"] != "selected_required" or
                    case_id not in disposition.get("case_ids", [case_id])):
                continue
            key, method, value_type, kind, inputs = ROWS[index]
            requirements.append({"disposition_index": index,
                                 "requirement": disposition["requirement"],
                                 "source": disposition["source"],
                                 "output_key": key, "method": method,
                                 "value_type": value_type, "kind": kind,
                                 "inputs": inputs})
        if not requirements:
            raise ValueError("Selected crosswalk requirements missing")
        contract = {"format": "worker-measurement-contract",
                    "case_id": case_id,
                    "requirements": requirements,
                    "negative": {"remove": ["capture/exception_review.json"],
                                 "error_contains":
                                     "Missing required source: capture/exception_review.json"}}
        path = ROOT / "cases" / suffix / "measurement-contract.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(contract, indent=2) + "\n")
        entry["measurement_contract"] = str(path.relative_to(ROOT))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    result = build()
    print(len(result["cases"]), "case-specific selected measurement contracts")
