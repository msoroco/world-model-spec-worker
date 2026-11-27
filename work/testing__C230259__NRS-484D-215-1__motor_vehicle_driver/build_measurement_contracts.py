"""Bind every selected law requirement to the executed saved finalizer."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / "case-plan.json").read_text())
SPEC = {
    0: ("measure_qualifying", ["site-packet.json", "actor-state.jsonl", "camera-frame-map.jsonl"]),
    1: ("measure_revelation", ["actor-state.jsonl", "roi-frames.jsonl", "approach.mkv", "camera-frame-map.jsonl"]),
    2: ("measure_oncoming_distance", ["actor-state.jsonl", "camera-frame-map.jsonl", "site-packet.json"]),
    3: ("measure_glare", ["roi-frames.jsonl", "driver_reference.mkv", "camera-frame-map.jsonl", "actor-state.jsonl"]),
    4: ("measure_lowermost", ["site-packet.json", "actor-state.jsonl", "roi-frames.jsonl"]),
}


def build(case):
    case_id = case["case_id"]
    requirements = []
    for disposition in PLAN["requirement_dispositions"]:
        if case_id not in disposition["case_ids"]:
            continue
        index = disposition["disposition_index"]
        method, inputs = SPEC[index]
        requirements.append({"disposition_index": index,
                             "requirement": disposition["requirement"],
                             "source": disposition["source"],
                             "kind": "measured" if index in (1, 2, 3) else "sourced_context",
                             "method": method,
                             "output_key": "beam_requirement_" + str(index),
                             "inputs": inputs, "value_type": "object"})
    return {"format": "worker-measurement-contract", "case_id": case_id,
            "requirements": requirements,
            "negative": {"remove": ["roi-frames.jsonl"],
                         "error_contains": "Missing required source: roi-frames.jsonl"}}


if __name__ == "__main__":
    for case in PLAN["cases"]:
        suffix = case["case_id"].split("__")[-1]
        (ROOT / ("measurement-contract-" + suffix + ".json")).write_text(
            json.dumps(build(case), indent=2) + "\n")
