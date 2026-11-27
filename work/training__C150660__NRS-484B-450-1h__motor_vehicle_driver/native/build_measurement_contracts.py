"""Bind every selected statutory clause to original saved measurements."""

import json
from pathlib import Path

from case_specs import CASES
from finalize import SOURCES

FOLDER = Path(__file__).resolve().parents[1]
PLAN = json.loads((FOLDER / "case-plan.json").read_text())
OUTPUTS = (("curb_and_exception_context", "source_review", "sourced_context"),
           ("safety_zone_geometry", "measure_safety_zone", "measured"),
           ("safety_zone_designation", "source_review", "sourced_context"))


def build(suffix):
    case = FOLDER.name + "__" + suffix
    rows = []
    for index, disposition in enumerate(PLAN["requirement_dispositions"]):
        output, method, kind = OUTPUTS[index]
        rows.append({"disposition_index": index,
                     "requirement": disposition["requirement"],
                     "source": disposition["source"],
                     "kind": kind, "method": method,
                     "output_key": output, "value_type": "object",
                     "inputs": list(SOURCES)})
    contract = {"format": "worker-measurement-contract", "case_id": case,
                "status": "draft", "requirements": rows,
                "negative": {"remove": ["zone_raw.json"],
                             "error_contains": "Missing required source: zone_raw.json"}}
    path = FOLDER / "cases" / suffix / "measurement-contract.json"
    path.write_text(json.dumps(contract, indent=2) + "\n")
    return path


if __name__ == "__main__":
    for suffix in CASES:
        print(build(suffix).relative_to(FOLDER))
