"""Write source-bound measurement contracts for every selected exact case."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    for case in plan["cases"]:
        case_id = case["case_id"]
        requirements = []
        for disposition in plan["requirement_dispositions"]:
            if case_id not in disposition["case_ids"]:
                continue
            index = disposition["disposition_index"]
            inputs = ["original-attempt/motion.jsonl",
                      "original-attempt/motion-seal.json",
                      "original-attempt/frame-map.json"]
            if index in (0, 1, 3):
                inputs += ["original-attempt/site.json",
                           "original-attempt/site-sources/private_way_ownership.source",
                           "original-attempt/site-sources/private_way_access.source",
                           "original-attempt/site-sources/highway_status.source",
                           "original-attempt/site-sources/boundary_map.source",
                           "original-attempt/site-sources/connection_map.source",
                           "original-attempt/site-sources/native_opendrive_map.source"]
            if index == 2:
                inputs += ["original-attempt/actors.json"]
            requirements.append({
                "disposition_index": index,
                "requirement": disposition["requirement"],
                "source": disposition["source"],
                "kind": "sourced_context" if index == 3 else "measured",
                "method": "measure_original_private_way",
                "output_key": "private_way_requirement_" + str(index),
                "value_type": "object",
                "inputs": inputs,
            })
        contract = {
            "format": "worker-measurement-contract",
            "case_id": case_id,
            "requirements": requirements,
            "negative": {
                "remove": ["original-attempt/motion.jsonl"],
                "error_contains": "Missing required source: original-attempt/motion.jsonl",
            },
        }
        filename = ROOT / ("measurement-" + case["variant"] + ".json")
        filename.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    print(len(plan["cases"]))


if __name__ == "__main__":
    main()
