"""Prepare exact C147332 commands for later ordered local delivery dispatch."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
BATCH = "full-test-delivery"
LOCAL = 'python3.11 -m scenario_pipeline.worker_exchange --project "$PROJECT" --root "$LOCAL_ROOT"'
BASE = ' --repo "$WORKER_REPO" --batch ' + BATCH + ' --db "$DB" --assignment ' + ASSIGNMENT


def build() -> dict:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    expected = {item["case_id"] for item in plan["cases"]}
    entries = {item["case_id"]: item for item in manifest["cases"]}
    contracts = {item["case_id"] for item in manifest["cases"] if item.get("delivery_acceptance")}
    if len(expected) != 4 or set(entries) != expected or contracts != expected:
        raise ValueError("exact four-case queue coverage differs")
    expected_comparisons = {item["comparison_id"] for item in plan["comparisons"]}
    if len(expected_comparisons) != 2:
        raise ValueError("exact two-comparison queue coverage differs")
    rows = []
    for case in sorted(expected):
        entry = entries[case]
        execute = (LOCAL + " execute-delivery" + BASE + ' --run "$RUN" --case ' + case +
                   ' --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"')
        rows.append({
            "assignment_id": ASSIGNMENT, "case_id": case,
            "prepare_command": LOCAL + " prepare-delivery" + BASE + " --case " + case,
            "execute_command": execute, "capture_command": execute,
            "owner_release_command": ('CASE_ID=' + case +
                                      ' PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py owner-released'
                                      ' --attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT"'
                                      ' --acknowledge-owner-released'),
            "postprocessing_command": ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved'
                                       ' --manifest work/' + ASSIGNMENT + '/execution-manifest.json --case ' + case +
                                       ' --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" --library "$LIBRARY"'
                                       ' --validator "$VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"'),
            "additional_source_audit_command": ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' +
                                                ASSIGNMENT + '/independent/delivery_audit.py --case-id ' + case +
                                                ' --attempt "$ATTEMPT" --physical-receipt "$PHYSICAL_RECEIPT"'
                                                ' --pixel-review "$PIXEL_REVIEW" --decode-receipt "$DECODE_RECEIPT"'
                                                ' --media-auditor "$MEDIA_AUDITOR" --job-id "$JOB_ID"'
                                                ' --attempt-number "$ATTEMPT_NUMBER" --recording-id "$RECORDING_ID"'
                                                ' --output "$AUDIT"'),
            "accept_command": (LOCAL + " accept-delivery" + BASE + ' --run "$RUN" --case ' + case +
                               ' --job "$JOB_ID" --attempt "$ATTEMPT_NUMBER" --audit "$AUDIT"'
                               ' --review-archive /external/archive'),
            "candidate_commands": {candidate["id"]: LOCAL + " prepare-delivery" + BASE +
                                   " --case " + case + " --candidate " + candidate["id"]
                                   for candidate in entry.get("candidates", [])},
        })
    comparisons = [{
        "assignment_id": ASSIGNMENT, "comparison_id": item["comparison_id"],
        "command": ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' + ASSIGNMENT +
                    '/independent/comparison_audit.py --comparison-id ' + item["comparison_id"] +
                    ' --baseline-attempt "$BASELINE_ATTEMPT" --changed-attempt "$CHANGED_ATTEMPT"'
                    ' --output "$COMPARISON_AUDIT"'),
    } for item in plan["comparisons"]]
    return {"format": "worker-assignment-queue-entries-partial",
            "assignment_id": ASSIGNMENT, "cases": rows,
            "comparison_audit_commands": comparisons,
            "batch_queue_complete": False, "original_attempts_reviewed": False}


def main() -> None:
    packet = build()
    (ROOT / "queue-entries.partial.json").write_text(json.dumps(packet, indent=2) + "\n")
    print(f"{ASSIGNMENT}: {len(packet['cases'])} cases and "
          f"{len(packet['comparison_audit_commands'])} comparisons queued as partial")


if __name__ == "__main__":
    main()
