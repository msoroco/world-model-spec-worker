"""Bind each selected requirement to source-hashed saved measurements."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    descriptions = [
        ("covered_bus", "measure_covered_bus", "sourced_context",
         ["bus_context.json", "bus_motion.jsonl", "bus_body.jsonl"]),
        ("emergency_and_loading_context", "measure_exception", "sourced_context",
         ["bus_context.json", "road.xodr", "passenger_body.jsonl", "video_frames.jsonl"]),
        ("actual_loading_place", "measure_loading_place", "measured",
         ["bus_context.json", "road.xodr", "bus_body.jsonl", "passenger_body.jsonl"]),
    ]
    for case in plan["cases"]:
        slug = case["case_id"].removeprefix(plan["assignment_id"] + "__")
        requirements = []
        for index, ((key, method, kind, sources), disposition) in enumerate(
                zip(descriptions, plan["requirement_dispositions"])):
            requirements.append({"disposition_index": index,
                                 "requirement": disposition["requirement"],
                                 "source": disposition["source"],
                                 "output_key": key, "method": method,
                                 "value_type": "object", "kind": kind,
                                 "inputs": sources})
        contract = {"format": "worker-measurement-contract", "case_id": case["case_id"],
                    "requirements": requirements,
                    "negative": {"remove": ["bus_context.json"],
                                 "error_contains": "Missing required source: bus_context.json"},
                    "physical_limit": "synthetic fixture does not establish authority, emergency, class, pixels or passenger exchange"}
        (ROOT / ("measurement-" + slug + ".json")).write_text(
            json.dumps(contract, indent=2, ensure_ascii=False) + "\n")
    return len(plan["cases"])


if __name__ == "__main__":
    print(build())
