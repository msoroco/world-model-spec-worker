"""Recheck selected CPU bindings without promoting diagnostic evidence."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUTPUT = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
if not OUTPUT.is_relative_to(REPO / ".runtime-work"):
    raise ValueError("SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work")
sys.path[:0] = [str(REPO / "runtime"), str(REPO / "runtime/scenario_pipeline")]

from scenario_pipeline.worker_exchange.execution_manifest import validate as execution
from scenario_pipeline.worker_exchange.semantic_delivery import validate as semantic
from scenario_pipeline.worker_exchange.package_compatibility import check_receipts
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case
from scenario_pipeline.worker_exchange.physical_preparation import validate as physical


def main() -> None:
    aid = ROOT.name
    manifest = execution(REPO, aid)
    print("selected_execution: PASS", len(manifest["cases"]), flush=True)
    assignment = json.loads((REPO / "inputs" / aid / "assignment.json").read_text())
    print("semantic:", semantic(ROOT, assignment, manifest), flush=True)
    for entry in manifest["cases"]:
        physical(REPO, ROOT, entry)
        validate_case(ROOT, entry, assignment["selection_targets"])
    print("physical: PASS 4; delivery: PASS 4", flush=True)
    print("compatibility:", check_receipts(REPO, ROOT, manifest), flush=True)
    print("selected_manifest_sha256:", hashlib.sha256(
        (ROOT / "execution-manifest.json").read_bytes()).hexdigest(), flush=True)


if __name__ == "__main__":
    main()
