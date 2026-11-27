"""Draft six exact local GPU jobs for lead integration after strict readiness."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
BATCH = "full-test-delivery"
PREFIX = ('PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python '
    '-m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" ')
CAPTURE_ENV = ('SCENARIO_PIPELINE_OUTPUT_ROOT='
    '"$PWD/.runtime-work/c150911-1d2-local-capture" ')


def local(kind: str, case_id: str, suffix: str = "") -> str:
    return (PREFIX + kind + ' --repo "$PWD" --batch ' + BATCH +
        ' --db "$DB" --assignment ' + ASSIGNMENT + ' --case ' + case_id + suffix)


def build() -> dict:
    plan = json.loads((HERE / "case-plan.json").read_text())
    cases = []
    for order, case in enumerate(plan["cases"], 1):
        cid = case["case_id"]
        prepare = local("prepare-delivery", cid)
        execute = CAPTURE_ENV + local("execute-delivery", cid,
            ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON"'
            ' --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = local("accept-delivery", cid,
            ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT"'
            ' --audit "$AUDIT" --review-archive /external/archive')
        cases.append({"order": order, "assignment_id": ASSIGNMENT,
            "case_id": cid, "prepare_command": prepare,
            "execute_command": execute, "capture_command": execute,
            "accept_command": accept, "candidate_commands": {},
            "owner_release_command": 'CASE_ID=' + cid +
                ' .venv-cpu/bin/python runtime.py owner-released'
                ' --attempt "$SAVED_ATTEMPT" --receipt "$OWNER_RELEASE_DIR/' + cid + '.json"'
                ' --acknowledge-owner-released',
            "postprocessing_command": '.venv-cpu/bin/python runtime.py process-saved'
                ' --manifest work/' + ASSIGNMENT + '/execution-manifest.json'
                ' --case ' + cid + ' --attempt "$SAVED_ATTEMPT"'
                ' --output "$PROCESSED_ROOT" --library runtime/library'
                ' --validator "$LEAN_VALIDATOR"'
                ' --owner-release-receipt "$OWNER_RELEASE_DIR/' + cid + '.json"',
            "additional_source_audit_command": 'PYTHONDONTWRITEBYTECODE=1 '
                'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c150911-1d2-local-audit"'
                ' .venv-cpu/bin/python runtime.py work/' + ASSIGNMENT +
                '/delivery_audit.py --attempt "$SAVED_ATTEMPT" --case-id '
                + cid + ' --output "$SOURCE_AUDIT"'})
    comparisons = [{"assignment_id": ASSIGNMENT,
        "comparison_id": comparison["comparison_id"],
        "case_ids": comparison["case_ids"],
        "command": 'PYTHONDONTWRITEBYTECODE=1 '
            'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c150911-1d2-local-comparison"'
            ' .venv-cpu/bin/python runtime.py work/' + ASSIGNMENT +
            '/comparison_audit.py --comparison ' + comparison["comparison_id"] +
            ' --first-attempt "$FIRST_ATTEMPT"'
            ' --second-attempt "$SECOND_ATTEMPT" --output "$COMPARISON_AUDIT"'}
        for comparison in plan["comparisons"]]
    proposal = {"format": "worker-gpu-queue-proposal", "assignment_id": ASSIGNMENT,
        "status": "draft_pending_strict_gate", "cases": cases,
        "comparison_audit_commands": comparisons,
        "source_prerequisites": [
            "Review and source-hash original one-way public highway, both crossing routes, official facing pedestrian signal and legible countdown readback before Native.",
            "Actual CARLA motion and pixels, signal legibility and statutory exceptions remain unverified."]}
    (HERE / "gpu-queue-proposal.json").write_text(
        json.dumps(proposal, indent=2, sort_keys=True) + "\n")
    return proposal


if __name__ == "__main__":
    print(len(build()["cases"]))
