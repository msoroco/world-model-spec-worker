"""Draft assignment-scoped canonical local commands for lead integration."""

import json
from pathlib import Path

from school_lane_controls import ASSIGNMENT


HERE = Path(__file__).resolve().parent


def main():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    rows = []
    for index, entry in enumerate(manifest["cases"], 1):
        case = entry["case_id"]
        base = ('PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m '
                'scenario_pipeline.worker_exchange --root "$LOCAL_ROOT"')
        prepare = (base + ' prepare-delivery --repo "$PWD" --batch full-test-delivery'
                   ' --db "$DB" --assignment ' + ASSIGNMENT + ' --case ' + case)
        execute = ('SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c422976-local-capture" ' +
                   base + ' execute-delivery --repo "$PWD" --batch full-test-delivery'
                   ' --db "$DB" --assignment ' + ASSIGNMENT + ' --case ' + case +
                   ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON"'
                   ' --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (base + ' accept-delivery --repo "$PWD" --batch full-test-delivery'
                  ' --db "$DB" --assignment ' + ASSIGNMENT + ' --case ' + case +
                  ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT"'
                  ' --audit "$AUDIT" --review-archive /external/archive')
        rows.append({"order": index, "assignment_id": ASSIGNMENT, "case_id": case,
                     "prepare_command": prepare, "execute_command": execute,
                     "capture_command": execute, "accept_command": accept,
                     "owner_release_command": 'CASE_ID=' + case +
                     ' .venv-cpu/bin/python runtime.py owner-released --attempt "$SAVED_ATTEMPT"'
                     ' --receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released',
                     "postprocessing_command": '.venv-cpu/bin/python runtime.py process-saved'
                     ' --manifest work/' + ASSIGNMENT + '/execution-manifest.json --case ' + case +
                     ' --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_ROOT"'
                     ' --library runtime/library --validator "$LEAN_VALIDATOR"'
                     ' --owner-release-receipt "$OWNER_RELEASE_RECEIPT"',
                     "additional_source_audit_command": '.venv-cpu/bin/python work/' +
                     ASSIGNMENT + '/delivery_audit.py --authority-root "$SOURCE_ROOT"'
                     ' --receipt "$RECEIPT" --output "$AUDIT" --case ' + case,
                     "candidate_commands": {}})
    comparisons = [{"assignment_id": ASSIGNMENT,
                    "comparison_id": pair["comparison_id"],
                    "command": '.venv-cpu/bin/python work/' + ASSIGNMENT +
                               '/run_comparison_audit.py --comparison ' + pair["comparison_id"] +
                               ' --left "$LEFT_AUDIT" --right "$RIGHT_AUDIT"'
                               ' --output "$COMPARISON_AUDIT"'}
                   for pair in plan["comparisons"]]
    value = {"format": "worker-assignment-gpu-queue-proposal",
             "assignment_id": ASSIGNMENT,
             "status": "cpu_prepared_pending_local_original_review",
             "cases": rows, "comparison_audit_commands": comparisons,
             "preconditions": ["obtain reviewed original school lane and source packet",
                               "pass exact scoped strict gate before local queue adoption"]}
    (HERE / "gpu-queue-proposal.json").write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Drafted", len(rows), "exact rows and", len(comparisons), "comparison audits")


if __name__ == "__main__":
    main()
