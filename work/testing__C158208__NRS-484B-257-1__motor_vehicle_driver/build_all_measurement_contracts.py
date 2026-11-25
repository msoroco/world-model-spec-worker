"""Bind all selected C158208 statutory requirements to saved observations.

These contracts apply to diagnostic CPU proofs and later original capture. They
do not promote a synthetic fixture to physical or legal acceptance.
"""
from __future__ import annotations

import json
from pathlib import Path

from build_semantic_proposals import KINDS


HERE = Path(__file__).resolve().parent
INPUTS = ["capture-identity.json", "nearest-view-tick-seal.json",
          "nearest-view-original-ticks.jsonl", "nearest-view-saved-packet.json",
          "diagnostic-compatibility.json", "overview.mkv", "approach.mkv",
          "reference_corner.mkv", "driver_reference.mkv"]


def build() -> dict:
    plan = json.loads((HERE / "case-plan.json").read_text())
    dispositions = plan["requirement_dispositions"]
    if any(row["status"] != "selected_required" for row in dispositions):
        raise ValueError("all accepted branch requirements must be selected")
    output = []
    for kind in KINDS:
        case_id = HERE.name + "__" + kind
        rows = []
        for index, disposition in enumerate(dispositions):
            if case_id not in disposition["case_ids"]:
                continue
            if index == 0:
                key, method, row_kind = "nearest_view_history", "measure_nearest_view", "measured"
            elif index == 1:
                key, method, row_kind = "governing_control_context", "measure_governing_control", "sourced_context"
            else:
                key, method, row_kind = (f"statutory_requirement_{index}_history",
                                         "measure_statutory_requirement", "measured")
            rows.append({"disposition_index": index,
                         "requirement": disposition["requirement"],
                         "source": disposition["source"],
                         "output_key": key, "method": method,
                         "value_type": "object", "kind": row_kind, "inputs": INPUTS})
        if not rows:
            raise ValueError("accepted branch lacks selected requirement: " + case_id)
        contract = {"format": "worker-measurement-contract", "case_id": case_id,
                    "requirements": rows,
                    "negative": {"remove": ["nearest-view-saved-packet.json"],
                                 "error_contains": "Missing required source: nearest-view-saved-packet.json"}}
        target = HERE / f"measurement-contract-{kind}.json"
        target.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n")
        output.append(target.name)
    return {"selected_requirements": len(dispositions), "contracts": output}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
