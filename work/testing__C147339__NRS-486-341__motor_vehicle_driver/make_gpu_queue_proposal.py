"""Render exact case and comparison commands for lead queue integration."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
aid = root.name
manifest_path = root / "execution-manifest.json"
manifest = json.loads(manifest_path.read_text())
plan = json.loads((root / "case-plan.json").read_text())
prefix = 'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" '
common = '--repo "$PWD" --batch full-test-delivery --db "$DB" --assignment ' + aid
rows = []
for index, entry in enumerate(manifest["cases"], 1):
    cid = entry["case_id"]
    select = common + ' --case ' + cid
    execute = ('SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c147339-local-capture" ' + prefix +
               'execute-delivery ' + select +
               ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"')
    accept = (prefix + 'accept-delivery ' + select +
              ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT" --audit "$AUDIT" --review-archive /external/archive')
    owner = ('CASE_ID=' + cid + ' .venv-cpu/bin/python runtime.py owner-released '
             '--attempt "$SAVED_ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released')
    post = ('.venv-cpu/bin/python runtime.py process-saved --manifest work/' + aid +
            '/execution-manifest.json --case ' + cid +
            ' --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_ROOT" --library runtime/library '
            '--validator "$LEAN_VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
    rows.append({"assignment_id": aid, "case_id": cid,
                 "prepare_command": prefix + 'prepare-delivery ' + select,
                 "execute_command": execute, "capture_command": execute,
                 "accept_command": accept,
                 "candidate_commands": {candidate["id"]: prefix + 'prepare-delivery ' + select +
                                        ' --candidate ' + candidate["id"]
                                        for candidate in entry["candidates"]},
                 "owner_release_command": owner, "postprocessing_command": post,
                 "additional_source_audit_command": '.venv-cpu/bin/python work/' + aid +
                    '/delivery_audit.py --case ' + cid + ' --attempt "$SAVED_ATTEMPT" --require-original',
                 "order": index})
comparisons = []
for item in plan["comparisons"]:
    left, right = item["case_ids"]
    comparisons.append({"assignment_id": aid, "comparison_id": item["comparison_id"],
                        "case_ids": item["case_ids"],
                        "command": 'CASE_LEFT=' + left + ' CASE_RIGHT=' + right +
                                   ' .venv-cpu/bin/python work/' + aid +
                                   '/comparison_audit.py --comparison ' + item["comparison_id"] +
                                   ' --left "$LEFT_SAVED_ATTEMPT" --right "$RIGHT_SAVED_ATTEMPT"'})
proposal = {"format": "worker-gpu-queue-proposal", "assignment_id": aid,
            "cases": rows, "comparison_audit_commands": comparisons,
            "selected_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "source_prerequisites": ["independently reviewed original one-way multilane public highway survey and OpenDRIVE hash",
                                     "chapter motorcycle or moped source classification, exclusion review and blueprint/body dimensions",
                                     "source-bound protected occupied lane and routes with exact case identity",
                                     "four reviewed camera poses and original Native two-actor readback"],
            "remaining_review": ["original Native two-actor motion and 900 synchronized frames per case",
                                 "four actual camera streams and independent pixel review",
                                 "source-bound full lane use and statutory chapter classification judgments"]}
(root / "gpu-queue-proposal.json").write_text(json.dumps(proposal, indent=2) + "\n")
