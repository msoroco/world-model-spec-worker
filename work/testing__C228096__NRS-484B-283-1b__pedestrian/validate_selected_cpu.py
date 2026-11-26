"""Run pinned selected CPU validators while preserving source-gated partial status.

The optional in-memory sweep probe checks downstream manifest structure. It
does not expand or persist a legal judgment sweep and is not a readiness proof.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

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
    proposal_path = ROOT / "proposals/cases.json"
    original_read = execution.read

    def probe_read(path):
        value = original_read(path)
        if Path(path).resolve() == proposal_path.resolve():
            value = dict(value)
            value["sweeps_expanded"] = True
        return value

    with patch.object(execution, "read", probe_read):
        downstream = checked(lambda: execution.validate(REPO, ASSIGNMENT))
    return {"format": "c228096-selected-cpu-validator-report",
            "assignment_id": ASSIGNMENT, "status": "partial",
            "outcomes": outcomes, "downstream_structure_probe": downstream,
            "probe_scope": "in-memory diagnostic only; judgment sweeps remain source-gated",
            "original_source_acceptance_claimed": False}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
