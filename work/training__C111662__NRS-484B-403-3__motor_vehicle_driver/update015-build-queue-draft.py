"""Draft exact C111662 delivery commands for the eventual batch-wide queue.

This is a worker-owned command inventory, not a local integration proof or GPU job.
The batch-wide queue must assign global order after the other 252 packages settle.
"""
import hashlib
import json
from pathlib import Path
import shlex

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
manifest = json.loads((ROOT / "execution-manifest.json").read_text())
plan = json.loads((ROOT / "case-plan.json").read_text())
module = 'python3.11 -m scenario_pipeline.worker_exchange --root "$PROJECT_ROOT"'
common = f'--repo "$WORKER_RETURN" --batch full-train-delivery --db "$DB" --assignment {AID}'


def call(action, case, rest=""):
    return f'{module} {action} {common} --case {case}' + (" " + rest if rest else "")


rows = []
for order, entry in enumerate(manifest["cases"], 1):
    case = entry["case_id"]
    prepare = call("prepare-delivery", case, "--candidate primary")
    execute = call("execute-delivery", case,
                   '--run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" '
                   '--host "$CARLA_HOST" --port "$CARLA_PORT"')
    accept = call("accept-delivery", case,
                  '--run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT_NUMBER" '
                  '--audit "$AUDIT_FILE"')
    audit = (f'python3.11 "$OPERATIONS/delivery_audit.py" --case {case} '
             '--job-id "$JOB_ID" --attempt-number "$ATTEMPT_NUMBER" '
             '--recording-id "$RECORDING_ID" --bundle "$BUNDLE" '
             '--attempt-dir "$ATTEMPT_DIR" --review "$REVIEW_FILE" '
             '--video "$VIDEO_REL" --trace "$TRACE_REL" '
             '--decode-receipt "$OPERATIONS/decode-$RECORDING_ID.json" '
             '--output "$AUDIT_FILE"')
    saved = (f'"$WORKER_RETURN/.venv-cpu/bin/python" "$WORKER_RETURN/runtime.py" '
             f'process-saved --manifest "$WORKER_RETURN/work/{AID}/execution-manifest.json" '
             f'--case {case} --attempt "$ATTEMPT_DIR" --output "$SAVED_DIR" '
             '--library "$LIBRARY" --validator "$VALIDATOR"')
    rows.append({"order": order, "assignment_id": AID, "case_id": case,
                 "prepare_command": prepare, "execute_command": execute,
                 "accept_command": accept, "capture_command": execute,
                 "postprocessing_command": saved,
                 "owner_release_command": accept,
                 "additional_source_audit_command": audit,
                 "candidate_commands": {candidate["id"]: call(
                     "prepare-delivery", case,
                     "--candidate " + candidate["id"])
                     for candidate in entry["candidates"]},
                 "original_attempt_required": True,
                 "execution_status": "unrun"})

comparisons = []
for item in plan["comparisons"]:
    case_a, case_b = item["case_ids"]
    branch = "divided_opening" if "divided" in item["comparison_id"] else "intersection"
    command = (f'python3.11 "$WORKER_RETURN/work/{AID}/native/audit_original_pair.py" '
               f'--branch {branch} --reference-bundle "$BUNDLE_{branch.upper()}_REFERENCE" '
               f'--reference-attempt "$ATTEMPT_{branch.upper()}_REFERENCE" '
               f'--reference-review "$REVIEW_{branch.upper()}_REFERENCE" '
               f'--contrast-bundle "$BUNDLE_{branch.upper()}_CONTRAST" '
               f'--contrast-attempt "$ATTEMPT_{branch.upper()}_CONTRAST" '
               f'--contrast-review "$REVIEW_{branch.upper()}_CONTRAST" '
               '--output "$COMPARISON_AUDIT"')
    comparisons.append({"assignment_id": AID, "comparison_id": item["comparison_id"],
                        "case_ids": [case_a, case_b], "command": command,
                        "original_pair_audited": False})

expected = {row["case_id"] for row in manifest["cases"]}
if (len(rows) != 4 or {row["case_id"] for row in rows} != expected or
        len(comparisons) != 2 or
        any({"fallback1", "fallback2", "fallback3"} != set(row["candidate_commands"])
            for row in rows)):
    raise ValueError("Draft queue does not cover exact selected C111662 work")
for row in rows:
    for key in ("prepare_command", "execute_command", "accept_command",
                "capture_command", "postprocessing_command",
                "owner_release_command", "additional_source_audit_command"):
        if row["case_id"] not in shlex.split(row[key]):
            raise ValueError("Draft queue command lost exact case: " + key)
result = {"format": "worker-assignment-queue-draft", "assignment_id": AID,
          "cases": rows, "comparison_audit_commands": comparisons,
          "canonical_batch_queue_complete": False,
          "local_integration_proved": False,
          "gpu_jobs_executed": 0, "recordings_accepted": 0}
output = ROOT / "update015-delivery-queue-draft.json"
output.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"cases": len(rows), "comparisons": len(comparisons),
                  "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}))
