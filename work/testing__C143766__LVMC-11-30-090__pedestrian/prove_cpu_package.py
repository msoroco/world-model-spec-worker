"""Recheck exact construction, semantic and compatibility receipts together."""
from __future__ import annotations

import json
import hashlib
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
safe = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
if not safe.is_relative_to(REPO/".runtime-work"):
    raise RuntimeError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime imports")
sys.path.insert(0, str(REPO/"runtime/scenario_pipeline"))
from worker_exchange.execution_manifest import validate as execution_validate
from worker_exchange.semantic_delivery import validate as semantic_validate
from worker_exchange.package_compatibility import check_receipts
from worker_exchange.delivery_handoff import validate_case


def main():
    assignment = json.loads((REPO/"inputs"/HERE.name/"assignment.json").read_text())
    manifest = execution_validate(REPO, HERE.name)
    semantic = semantic_validate(HERE, assignment, manifest)
    check_receipts(REPO, HERE, manifest)
    for entry in manifest["cases"]:
        validate_case(HERE, entry, assignment["selection_targets"])
    paired = json.loads((HERE/"comparison-audit-specs.json").read_text())["pairs"]
    for pair in paired:
        for field, checksum in (("script", "script_sha256"),
                                ("receipt", "receipt_sha256"),
                                ("positive_log", "positive_log_sha256"),
                                ("negative_log", "negative_log_sha256")):
            path = HERE/pair[field]
            if hashlib.sha256(path.read_bytes()).hexdigest() != pair[checksum]:
                raise ValueError("paired audit proof source changed: "+str(path))
        if pair["negative_expected_error"] not in (HERE/pair["negative_log"]).read_text():
            raise ValueError("paired audit rejection proof differs")
    print(json.dumps({"assignment_id": HERE.name,
                      "primary_and_fallback_constructions": len(manifest["cases"])*2,
                      "positive_negative_compatibility_receipts": len(manifest["cases"])*2,
                      "semantic_stages": semantic["stage_count"],
                      "selected_cases": semantic["selected_cases"],
                      "synthetic_physical_preparation_checked": True,
                      "delivery_acceptance_checked": True,
                      "diagnostic_paired_audits_checked": len(paired),
                      "native_or_legal_acceptance_claimed": False}, indent=2))


if __name__ == "__main__":
    main()
