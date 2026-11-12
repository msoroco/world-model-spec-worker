"""Independently check six selected CPU audit proofs and non-acceptance."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from source_join_audit import read, require, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline"))
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case  # noqa: E402


def audit() -> dict:
    manifest_path = HERE / "execution-manifest.json"
    manifest = read(manifest_path)
    require(len(manifest["cases"]) == 6 and
            {entry["case_id"].removeprefix(HERE.name + "__") for entry in manifest["cases"]} ==
            {"rail_reference", "rail_contrast", "oneway_absent", "oneway_present",
             "traversal_reference", "traversal_contrast"},
            "Selected delivery case set differs")
    results = []
    for entry in manifest["cases"]:
        contract = validate_case(HERE, entry, ["full-train"])
        positive = read(HERE / contract["test_log"])
        require(positive["case_id"] == entry["case_id"] and
                positive["construction_sha256"] == entry["construction_sha256"] and
                positive["auditor_sha256"] == sha(HERE / "delivery_audit.py") and
                positive["source_shape_passed"] is True and
                positive["delivery_accepted"] is False and
                contract["scope"].startswith("source-shaped CPU mechanics"),
                "Diagnostic audit claims physical acceptance")
        results.append({"case_id": entry["case_id"],
                        "positive_log_sha256": contract["test_log_sha256"],
                        "negative_log_sha256": contract["negative_log_sha256"],
                        "delivery_accepted": False})
    return {"format": "c110454-selected-delivery-acceptance-cpu-proof-v1",
            "manifest_sha256": sha(manifest_path), "case_count": len(results),
            "cases": results, "accepted_recordings": 0}


if __name__ == "__main__":
    proof = audit()
    path = HERE / "update024-selected-delivery-acceptance-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"case_count": proof["case_count"],
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
