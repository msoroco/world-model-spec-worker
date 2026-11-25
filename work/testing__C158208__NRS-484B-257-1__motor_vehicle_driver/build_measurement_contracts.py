"""Bind the exact nearest-view witness to saved-source measurement methods."""
from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = "inputs/planning/focused-coverage-20261016-v1/coverage-witnesses.json"
KINDS = ("nearest_view_response", "nearest_view_uninterrupted")
INPUTS = ["capture-identity.json", "nearest-view-tick-seal.json",
          "nearest-view-original-ticks.jsonl", "nearest-view-saved-packet.json",
          "diagnostic-compatibility.json", "overview.mkv", "approach.mkv",
          "reference_corner.mkv", "driver_reference.mkv"]


def build() -> dict:
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    assignment = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
    if plan.get("law_id") != assignment["law_id"] or plan.get("cell_id") != assignment["cell_id"]:
        raise ValueError("exact plan identity changed")
    cases = [HERE.name + "__" + kind for kind in KINDS]
    if {item["case_id"] for item in plan["cases"]} != set(cases):
        raise ValueError("nearest-view selected case pair changed")
    dispositions = [
        {"requirement": "Observe the nearest-view fallback and original through-highway approach and crossing history.",
         "source": SOURCE, "status": "selected_required", "case_ids": cases,
         "evidence_or_gap": "Sealed original C158208 ticks and camera sources must still be acquired."},
        {"requirement": "Verify governing yield sign, absent stop line and near-side crosswalk, and exclude officer or signal control.",
         "source": SOURCE, "status": "selected_required", "case_ids": cases,
         "evidence_or_gap": "Reviewed original C158208 site and eight survey sources remain to be supplied."},
    ]
    if plan.get("requirement_dispositions") not in (None, dispositions):
        raise ValueError("existing requirement disposition differs")
    plan["requirement_dispositions"] = dispositions
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    output = []
    for kind, case in zip(KINDS, cases):
        rows = []
        for index, (key, method) in enumerate((
                ("nearest_view_history", "measure_nearest_view"),
                ("governing_control_context", "measure_governing_control"))):
            rows.append({"disposition_index": index,
                         "requirement": dispositions[index]["requirement"],
                         "source": dispositions[index]["source"],
                         "output_key": key, "method": method,
                         "value_type": "object", "kind": "measured" if index == 0 else "sourced_context",
                         "inputs": INPUTS})
        contract = {"format": "worker-measurement-contract", "case_id": case,
                    "requirements": rows,
                    "negative": {"remove": ["nearest-view-saved-packet.json"],
                                 "error_contains": "Missing required source: nearest-view-saved-packet.json"}}
        path = HERE / ("measurement-contract-" + kind + ".json")
        path.write_text(json.dumps(contract, indent=2) + "\n")
        output.append(path.name)
    return {"dispositions": len(dispositions), "contracts": output}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
