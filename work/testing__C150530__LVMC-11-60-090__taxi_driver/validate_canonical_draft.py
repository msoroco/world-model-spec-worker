"""Validate the source-hashed canonical package components now prepared."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main() -> None:
    destination = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    if not destination or not Path(destination).resolve().is_relative_to(REPO / ".runtime-work"):
        raise ValueError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
    sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))
    from worker_exchange.execution_manifest import validate as execution
    from worker_exchange.semantic_delivery import validate as semantic
    from worker_exchange.package_compatibility import check_receipts
    from worker_exchange.delivery_handoff import validate_case

    manifest = execution(REPO, ROOT.name)
    original = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    semantic_result = semantic(ROOT, original, manifest)
    if check_receipts(REPO, ROOT, manifest) is not True:
        raise ValueError("Pinned compatibility receipts not accepted")
    for entry in manifest["cases"]:
        validate_case(ROOT, entry, {"full-test"})
    print(json.dumps({"assignment_id": ROOT.name, "cases": len(manifest["cases"]),
                      "canonical_execution": "passed", "semantic_delivery": semantic_result,
                      "compatibility_receipts": "passed", "delivery_acceptance_contract": "passed",
                      "delivery_ready": False}, indent=2))


if __name__ == "__main__":
    main()
