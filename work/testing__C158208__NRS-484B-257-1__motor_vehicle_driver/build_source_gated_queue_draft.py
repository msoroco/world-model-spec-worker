"""Prepare exact current-CLI commands without publishing a partial package."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
MANIFEST = HERE / "execution-manifest.source-gated-draft.json"
BASE = ('SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c158208-local-queue" '
        'PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/runtime" '
        '.venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT"')
SCRIPT_BASE = (f'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c158208-local-audit" '
               f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{ASSIGNMENT}/')


def build() -> dict:
    manifest = json.loads(MANIFEST.read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    if manifest.get("assignment_id") != ASSIGNMENT:
        raise ValueError("source-gated draft identity differs")
    planned = [entry["case_id"] for entry in manifest["cases"]]
    if set(planned) != {entry["case_id"] for entry in plan["cases"]} or len(planned) != 11:
        raise ValueError("exact source-gated case inventory differs")
    rows = []
    for order, entry in enumerate(manifest["cases"], 1):
        case = entry["case_id"]
        identity = (f'--repo "$PWD" --batch full-test-delivery --db "$DB" '
                    f'--assignment {ASSIGNMENT} --case {case}')
        prepared = f'{BASE} prepare-delivery {identity}'
        run = f'{identity} --run "$RUN" --job "$JOB_ID"'
        execution = (f'{BASE} execute-delivery {run} --python "$CARLA_PYTHON" '
                     '--host "$CARLA_HOST" --port "$CARLA_PORT"')
        rows.append({
            "assignment_id": ASSIGNMENT, "case_id": case, "order": order,
            "prepare_command": prepared, "execute_command": execution,
            "capture_command": execution,
            "accept_command": (f'{BASE} accept-delivery {run} --attempt "$ATTEMPT" '
                               '--audit "$AUDIT" --review-archive /external/archive'),
            "candidate_commands": {candidate["id"]: prepared + " --candidate " + candidate["id"]
                                   for candidate in entry.get("candidates", [])},
            "owner_release_command": (f'CASE_ID={case} .venv-cpu/bin/python runtime.py '
                                      'owner-released --attempt "$ATTEMPT" '
                                      '--receipt "$OWNER_RELEASE_RECEIPT" '
                                      '--acknowledge-owner-released'),
            "postprocessing_command": (f'.venv-cpu/bin/python runtime.py process-saved '
                                       f'--manifest work/{ASSIGNMENT}/execution-manifest.json '
                                       f'--case {case} --attempt "$ATTEMPT" '
                                       '--output "$PROCESSED" --library runtime/library '
                                       '--validator "$LEAN_VALIDATOR" '
                                       '--owner-release-receipt "$OWNER_RELEASE_RECEIPT"'),
            "additional_source_audit_command": (
                f'{SCRIPT_BASE}selected_delivery_audit.py --stage "$ATTEMPT" '
                f'--case {case} --output "$SOURCE_AUDIT"')})
    comparisons = []
    for comparison in plan["comparisons"]:
        comp = comparison["comparison_id"]
        comparisons.append({
            "assignment_id": ASSIGNMENT, "comparison_id": comp,
            "case_ids": comparison["case_ids"],
            "command": (f'{SCRIPT_BASE}statutory_comparison_audit.py '
                        '--stages "$ALL_CASE_STAGES_JSON" '
                        '--reviewed-expectations "$REVIEWED_EXPECTATIONS_JSON" '
                        f'--output "$COMPARISON_OUTPUT_ROOT/{comp}.json"')})
    if len(comparisons) != 8:
        raise ValueError("exact comparison inventory differs")
    proposal = {
        "format": "worker-gpu-queue-proposal-draft",
        "assignment_id": ASSIGNMENT, "publishable": False,
        "selection_status": "awaits_original_site_surveys_and_source_grounded_sweeps",
        "required_env": ["C158208_REVIEWED_SITE", "C158208_REVIEWED_SITE_SHA256",
                         "CARLA_PYTHON", "CARLA_HOST", "CARLA_PORT"],
        "cases": rows, "comparison_audit_commands": comparisons,
        "scope": "current-CLI command rehearsal only; not a selected delivery queue"}
    target = HERE / "gpu-queue-source-gated-draft.json"
    target.write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n")
    return {"cases": len(rows), "comparisons": len(comparisons),
            "publishable": False}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
