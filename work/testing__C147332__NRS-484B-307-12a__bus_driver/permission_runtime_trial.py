"""Isolated trial of a permission-aware semantic coverage branch.

This is a worker-owned candidate for local review, not a runtime modification.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

from permission_semantic_validation import validate as validate_permission


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
output_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
if not output_root.is_relative_to((REPO / ".runtime-work").resolve()):
    raise ValueError("pipeline output root must remain under .runtime-work")
sys.path.insert(0, str((REPO / "runtime/scenario_pipeline").resolve()))
from batch_pipeline import validation
from worker_exchange.semantic_delivery import validate as validate_delivery


def permission_aware_coverage(cases, binding, templates, sweep_specs, *, template,
                              proposal, plan, assignment):
    """Keep pinned global/ordinary checks, then validate this exact permission case set."""
    permission = [item for item in templates if
                  item.get("structure", {}).get("obligation", {}).get("type") == "permission"]
    ordinary = [item for item in templates if item not in permission]
    validation.coverage(cases, binding, ordinary, sweep_specs)
    if len(permission) != 1 or len(templates) != 1 or permission[0] != template or (
            cases != proposal["cases"]):
        raise ValueError("permission trial requires exact source-bound proposal")
    validate_permission(template, proposal, plan, assignment)


def trial(folder=ROOT):
    folder = Path(folder)
    assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    manifest = json.loads((folder / "execution-manifest.json").read_text())
    plan = json.loads((folder / "case-plan.json").read_text())
    proposal = json.loads((folder / "proposals/cases.json").read_text())
    template = json.loads((folder / "proposals/template.json").read_text())
    original = validation.coverage

    def permission_aware(cases, binding, templates, sweep_specs=()):
        with patch.object(validation, "coverage", original):
            return permission_aware_coverage(cases, binding, templates, sweep_specs,
                                             template=template, proposal=proposal,
                                             plan=plan, assignment=assignment)

    with patch.object(validation, "coverage", permission_aware):
        report = validate_delivery(folder, assignment, manifest)
    return {"format": "worker-permission-runtime-trial", "assignment_id": ROOT.name,
            "pinned_semantic_runtime_modified": False,
            "pinned_semantic_validator_passed": False,
            "permission_trial_passed": True,
            "pinned_stage_count": report["stage_count"],
            "selected_cases": report["selected_cases"],
            "scope": "Isolated replacement of the one plain-rule pair predicate; pinned stages and ordinary validation retained"}


def main():
    print(json.dumps(trial(), indent=2))


if __name__ == "__main__":
    main()
