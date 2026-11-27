"""Bind every selected statutory requirement to a named saved-only measurement."""

from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE / "case-plan.json").read_text())
SOURCES = ["context.json", "original-trace.jsonl", "receipt.json", "cameras.json"]
METHODS = ["measure_pass_activation", "measure_calendar_session", "measure_operation_window",
           "measure_beacon_class", "measure_sign_only"]
KEYS = ["pass_activation", "calendar_session", "operation_window", "beacon_class", "sign_only"]


def main() -> None:
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        name = entry["case_id"].rsplit("__", 1)[1]
        path = HERE / "cases" / name / "measurement-contract.json"
        requirements = []
        for index, disposition in enumerate(PLAN["requirement_dispositions"]):
            requirements.append({"disposition_index": index,
                                 "requirement": disposition["requirement"],
                                 "source": disposition["source"],
                                 "output_key": KEYS[index], "method": METHODS[index],
                                 "value_type": "object", "kind": "measured" if index == 0 else "sourced_context",
                                 "inputs": SOURCES})
        contract = {"format": "worker-measurement-contract", "assignment_id": HERE.name,
                    "case_id": entry["case_id"], "requirements": requirements,
                    "negative": {"remove": ["context.json"],
                                 "error_contains": "Missing required source: context.json"}}
        path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
        entry["measurement_contract"] = str(path.relative_to(HERE))
        entry["measurement_procedure"] = {"entrypoint": "analysis.py",
                                            "method": "saved source-bound school-zone pass and exception measurement"}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(len(manifest["cases"]), "measurement contracts")


if __name__ == "__main__":
    main()
