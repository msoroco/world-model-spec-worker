"""Draft exact-case and comparison commands for local delivery integration."""
from __future__ import annotations

import json
from pathlib import Path

from delivery_audit import ASSIGNMENT

ROOT = Path(__file__).resolve().parent


def main() -> None:
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    rows = []
    for i, entry in enumerate(manifest["cases"], 1):
        case = entry["case_id"]
        base = (f'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange '
                f'--root "$LOCAL_ROOT"')
        prepare = (f'{base} prepare-delivery --repo "$PWD" --batch full-test-delivery '
                   f'--db "$DB" --assignment {ASSIGNMENT} --case {case}')
        execute = (f'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c227824-local-capture" '
                   f'{base} execute-delivery --repo "$PWD" --batch full-test-delivery '
                   f'--db "$DB" --assignment {ASSIGNMENT} --case {case} --run "$RUN" '
                   f'--job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (f'{base} accept-delivery --repo "$PWD" --batch full-test-delivery '
                  f'--db "$DB" --assignment {ASSIGNMENT} --case {case} --run "$RUN" '
                  f'--job "$JOB_ID" --attempt "$ATTEMPT" --audit "$AUDIT" --review-archive "$REVIEW_ARCHIVE"')
        rows.append({"order": i, "assignment_id": ASSIGNMENT, "case_id": case,
                     "prepare_command": prepare, "execute_command": execute,
                     "capture_command": execute, "accept_command": accept,
                     "owner_release_command": f'CASE_ID={case} .venv-cpu/bin/python runtime.py owner-released --attempt "$SAVED_ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released',
                     "postprocessing_command": f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{ASSIGNMENT}/execution-manifest.json --case {case} --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_ROOT" --library runtime/library --validator "$LEAN_VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"',
                     "additional_source_audit_command": f'.venv-cpu/bin/python work/{ASSIGNMENT}/audit_cli.py --authority-root "$SOURCE_ROOT" --receipt "$RECEIPT" --output "$AUDIT" --case {case}',
                     "candidate_commands": {}})
    comparisons = [{"assignment_id": ASSIGNMENT, "comparison_id": item["comparison_id"],
                    "command": f'.venv-cpu/bin/python work/{ASSIGNMENT}/audit_cli.py --comparison {item["comparison_id"]} --authority-root "$SOURCE_ROOT" --receipts "$RECEIPTS" --output "$COMPARISON_AUDIT"'}
                   for item in plan["comparisons"]]
    value = {"format": "worker-assignment-gpu-queue-proposal", "assignment_id": ASSIGNMENT,
             "status": "source_gated_not_dispatchable", "cases": rows,
             "comparison_audit_commands": comparisons,
             "preconditions": ["complete two source-supported judgment sweep plans",
                               "obtain reviewed original curb/path site and source packet",
                               "pass exact strict worker gate before local queue adoption"]}
    (ROOT / "gpu-queue-proposal.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Drafted five exact case rows and four comparison audit commands")


if __name__ == "__main__":
    main()
