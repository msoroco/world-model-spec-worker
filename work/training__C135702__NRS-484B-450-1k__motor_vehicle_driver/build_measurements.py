"""Bind each selected source requirement to a recorded-only finalizer output."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPECS = (
    ("source_exceptions", "exception_context_measurement", "sourced_context",
     ["exception-context.json", "native_samples.jsonl"]),
    ("source_obstruction", "obstruction_measurement", "measured",
     ["native_samples.jsonl", "obstruction-inventory.json",
      "video_frames.jsonl", "camera-frames.jsonl"]),
    ("source_traffic_response", "traffic_comparison_measurement", "measured",
     ["native_samples.jsonl", "video_frames.jsonl"]),
)


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    if len(plan["requirement_dispositions"]) != len(SPECS):
        raise ValueError("Revisit measurement contract after statutory branch expansion")
    for case in plan["cases"]:
        rows = []
        for index, (key, method, kind, sources) in enumerate(SPECS):
            disposition = plan["requirement_dispositions"][index]
            if disposition["status"] != "selected_required" or case["case_id"] not in disposition["case_ids"]:
                raise ValueError("Selected requirement is not bound to exact case")
            rows.append({"disposition_index": index,
                         "requirement": disposition["requirement"],
                         "source": disposition["source"],
                         "output_key": key, "method": method,
                         "value_type": "object", "kind": kind, "inputs": sources})
        contract = {"format": "worker-measurement-contract",
                    "case_id": case["case_id"], "requirements": rows,
                    "negative": {"remove": ["obstruction-inventory.json"],
                                 "error_contains": "Missing required source: obstruction-inventory.json"},
                    "limitations": ["No statutory transverse-width or delay cutoff is asserted.",
                                    "Physical cause and exception applicability need original review."]}
        suffix = case["case_id"].rsplit("__", 1)[-1]
        (ROOT / ("measurement-" + suffix + ".json")).write_text(
            json.dumps(contract, indent=2) + "\n")


if __name__ == "__main__":
    build()
