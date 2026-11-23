"""Run the pinned manifest, semantic, delivery and receipt gates together."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
private = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
if not private or not Path(private).resolve().is_relative_to(REPO / ".runtime-work"):
    raise RuntimeError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
sys.path.insert(0, str(REPO / "runtime/python"))
from worker_exchange.execution_manifest import validate as manifest_check
from worker_exchange.semantic_delivery import validate as semantic_check
from worker_exchange.delivery_handoff import validate_case
from worker_exchange.package_compatibility import check_receipts


def main() -> None:
    assignment_id = ROOT.name
    manifest = manifest_check(REPO, assignment_id)
    assignment = json.loads((REPO / "inputs" / assignment_id / "assignment.json").read_text())
    semantic_check(ROOT, assignment, manifest)
    for entry in manifest["cases"]:
        validate_case(ROOT, entry, assignment["selection_targets"])
    check_receipts(REPO, ROOT, manifest)
    print("canonical manifest, semantic delivery, independent delivery protocols, primary receipts and fallbacks passed", len(manifest["cases"]))


if __name__ == "__main__":
    main()
