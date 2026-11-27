"""Prepare concrete exact-case local GPU commands for lead integration."""

from __future__ import annotations

import json
from pathlib import Path

from signed_road import AID

HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE / "case-plan.json").read_text())
MANIFEST = json.loads((HERE / "execution-manifest.json").read_text())


def command(stage, case_id):
    base = ('PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m '
            'scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" ' + stage +
            ' --repo "$PWD" --batch full-test-delivery --db "$DB"'
            ' --assignment ' + AID + ' --case ' + case_id)
    if stage == "execute-delivery":
        base += (' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON"'
                 ' --host "$CARLA_HOST" --port "$CARLA_PORT"')
    if stage == "accept-delivery":
        base += (' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT"'
                 ' --audit "$AUDIT" --review-archive /external/archive')
    return base


def main():
    rows = []
    for order, entry in enumerate(MANIFEST["cases"], 1):
        case_id = entry["case_id"]
        rows.append({
            "order": order, "assignment_id": AID, "case_id": case_id,
            "prepare_command": command("prepare-delivery", case_id),
            "execute_command": command("execute-delivery", case_id),
            "accept_command": command("accept-delivery", case_id),
            "capture_command": command("execute-delivery", case_id),
            "postprocessing_command": '.venv-cpu/bin/python runtime.py process-saved'
                ' --manifest work/' + AID + '/execution-manifest.json --case ' + case_id +
                ' --attempt "$ATTEMPT" --output "$PROCESSED" --library runtime/library'
                ' --validator "$LEAN_VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"',
            "owner_release_command": 'CASE_ID=' + case_id +
                ' .venv-cpu/bin/python runtime.py owner-released --attempt "$ATTEMPT"'
                ' --receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released',
            "additional_source_audit_command":
                'PYTHONPATH="$PWD/runtime/scenario_pipeline" .venv-cpu/bin/python work/' +
                AID + '/queue_delivery.py --attempt "$ATTEMPT" --processed-root "$PROCESSED"'
                ' --case ' + case_id + ' --output "$SOURCE_AUDIT_OUTPUT"',
            "candidate_commands": {},
        })
    comparisons = [{"assignment_id": AID, "comparison_id": item["comparison_id"],
                    "case_ids": item["case_ids"],
                    "command": '.venv-cpu/bin/python work/' + AID +
                               '/comparison_audit.py --report-map "$REPORT_MAP"'
                               ' --comparison ' + item["comparison_id"] +
                               ' --output "$COMPARISON_AUDIT_OUTPUT"'}
                   for item in PLAN["comparisons"]]
    proposal = {"format": "worker-ordered-gpu-queue-proposal",
                "assignment_id": AID, "cases": rows,
                "comparison_audit_commands": comparisons}
    (HERE / "queue-proposal.json").write_text(json.dumps(proposal, indent=2) + "\n")
    print("prepared concrete queue proposal", len(rows), len(comparisons))


if __name__ == "__main__":
    main()
