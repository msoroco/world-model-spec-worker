"""Bind the five selected statutory witness requirements to saved measurements."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / "case-plan.json").read_text())
SPECS = (
    ("crossing_highways", "measure_crossing_highways", "sourced_context",
     ["scene.json", "opendrive.xodr", "highway_identity.json"]),
    ("other_entry", "measure_other_entry", "measured",
     ["native_trace.json", "crossing_history.jsonl", "scene.json"]),
    ("ego_response", "measure_ego_response", "measured",
     ["native_trace.json", "crossing_history.jsonl", "scene.json"]),
    ("device_context", "measure_device_context", "sourced_context",
     ["native_trace.json", "scene.json", "device_inventory.json"]),
    ("opposing_turn_context", "measure_opposing_turn_context", "sourced_context",
     ["scene.json", "native_trace.json"]),
)


def build():
    for case in PLAN["cases"]:
        rows = []
        for index, (key, method, kind, inputs) in enumerate(SPECS):
            disposition = PLAN["requirement_dispositions"][index]
            if disposition["status"] != "selected_required":
                raise ValueError("selected disposition order changed")
            rows.append({"disposition_index": index,
                         "requirement": disposition["requirement"],
                         "source": disposition["source"],
                         "output_key": key, "method": method,
                         "value_type": "object", "kind": kind,
                         "inputs": inputs})
        suffix = case["case_id"].rsplit("__", 1)[1]
        contract = {"format": "worker-measurement-contract",
                    "case_id": case["case_id"], "requirements": rows,
                    "negative": {"remove": ["native_trace.json"],
                                 "error_contains": "Missing required source: native_trace.json"}}
        (ROOT / ("measurement-" + suffix + ".json")).write_text(
            json.dumps(contract, indent=2) + "\n")


if __name__ == "__main__":
    build()
