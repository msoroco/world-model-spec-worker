"""Bind each selected requirement to a concrete saved source measurement."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def build() -> list[str]:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    bindings = (
        (0, "school_marking_context", "measure_marking_context",
         ["road_geometry.json", "native_samples.jsonl"], "sourced_context"),
        (1, "signed_school_crossing_entry", "measure_signed_entry",
         ["road_geometry.json", "native_samples.jsonl", "video_frames.jsonl"], "measured"),
        (2, "reviewed_school_entry", "measure_reviewed_scope",
         ["native_samples.jsonl", "video_frames.jsonl"], "measured"),
    )
    paths = []
    for case in plan["cases"]:
        rows = []
        for index, output, method, inputs, kind in bindings:
            disposition = plan["requirement_dispositions"][index]
            rows.append({"disposition_index": index,
                         "requirement": disposition["requirement"],
                         "source": disposition["source"],
                         "output_key": output, "method": method,
                         "value_type": "object", "kind": kind,
                         "inputs": inputs})
        contract = {"format": "worker-measurement-contract",
                    "case_id": case["case_id"],
                    "requirements": rows,
                    "negative": {"remove": ["road_geometry.json"],
                                 "error_contains": "Missing required source: road_geometry.json"},
                    "physical_acceptance_claimed": False}
        suffix = case["case_id"].rsplit("_", 1)[-1]
        path = ROOT / ("measurement-contract-condition-" + suffix + ".json")
        path.write_text(json.dumps(contract, indent=2) + "\n")
        paths.append(str(path))
    return paths


if __name__ == "__main__":
    print(json.dumps(build()))
