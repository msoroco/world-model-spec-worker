"""Run pinned selected CPU validators for the expanded exact cases."""
from __future__ import annotations

import json
from pathlib import Path

import scenario_pipeline.worker_exchange.execution_manifest as execution
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case
from scenario_pipeline.worker_exchange.package_compatibility import check_receipts
from scenario_pipeline.worker_exchange.physical_preparation import validate as physical
from scenario_pipeline.worker_exchange.semantic_delivery import validate as semantic

from delivery_audit import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent


def checked(fn):
    try:
        fn()
        return {"passed": True}
    except Exception as error:
        return {"passed": False, "error_type": type(error).__name__,
                "error": str(error)}


def run() -> dict:
    assignment = json.loads((REPO / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    outcomes = {
        "selected_execution": checked(lambda: execution.validate(REPO, ASSIGNMENT)),
        "semantic": checked(lambda: semantic(ROOT, assignment, manifest)),
        "compatibility": checked(lambda: check_receipts(REPO, ROOT, manifest)),
        "physical": checked(lambda: [physical(REPO, ROOT, entry) for entry in manifest["cases"]]),
        "delivery": checked(lambda: [validate_case(ROOT, entry, assignment.get("selection_targets"))
                                     for entry in manifest["cases"]]),
    }
    return {"format": "c227824-selected-cpu-validator-report",
            "assignment_id": ASSIGNMENT,
            "status": "passed" if all(value["passed"] for value in outcomes.values()) else "partial",
            "outcomes": outcomes,
            "probe_scope": "selected expanded exact cases; original source acceptance is later local review",
            "original_source_acceptance_claimed": False}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
