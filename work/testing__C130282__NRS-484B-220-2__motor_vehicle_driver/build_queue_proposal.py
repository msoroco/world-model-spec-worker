"""Produce four exact source-gated island jobs and three comparison queue rows."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
PREFIX = 'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" '
BASE = '--repo "$PWD" --batch full-test-delivery --db "$DB" --assignment ' + AID
SOURCE = 'C130282_ISLAND_REVIEW="$ISLAND_REVIEW_PACKET" '
SCRATCH = ('mkdir -p "$PWD/.runtime-work/local-c130282-audit" && '
           'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/local-c130282-audit" '
           'TMPDIR="$PWD/.runtime-work/local-c130282-audit" PYTHONDONTWRITEBYTECODE=1 ')


def main():
    manifest = json.loads((ROOT / "execution-manifest.json").read_text(encoding="utf-8"))
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    cases = []
    for entry in manifest["cases"]:
        cid = entry["case_id"]
        job = BASE + ' --case ' + cid
        prepare = PREFIX + 'prepare-delivery ' + job
        execute = (SOURCE + PREFIX + 'execute-delivery ' + job +
            ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON"'
            ' --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (PREFIX + 'accept-delivery ' + job +
            ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT"'
            ' --audit "$AUDIT" --review-archive /external/archive')
        cases.append({"assignment_id": AID, "case_id": cid,
            "prepare_command": prepare, "execute_command": execute,
            "capture_command": execute, "accept_command": accept,
            "candidate_commands": {candidate["id"]: prepare + ' --candidate ' + candidate["id"]
                                   for candidate in entry["candidates"]},
            "owner_release_command": ('CASE_ID=' + cid +
                ' .venv-cpu/bin/python runtime.py owner-released --attempt "$ATTEMPT"'
                ' --receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released'),
            "postprocessing_command": (
                '.venv-cpu/bin/python runtime.py process-saved --manifest work/' + AID +
                '/execution-manifest.json --case ' + cid +
                ' --attempt "$ATTEMPT" --output "$PROCESSED" --library runtime/library'
                ' --validator "$LEAN_VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"'),
            "additional_source_audit_command": (
                SCRATCH + '.venv-cpu/bin/python work/' + AID + '/delivery_audit.py'
                ' --case-id ' + cid + ' --attempt "$ATTEMPT" --output "$AUDIT"')})
    comparisons = []
    for row in plan["comparisons"]:
        command = SCRATCH + '.venv-cpu/bin/python work/' + AID + '/comparison_audit.py'
        for cid in row["case_ids"]:
            tag = cid.rsplit('__', 1)[-1].upper()
            command += ' --attempt "$' + tag + '_ATTEMPT"'
        command += (' --comparison-id ' + row["comparison_id"] +
                    ' --plan work/' + AID + '/case-plan.json'
                    ' --output "$PWD/.runtime-work/local-c130282-audit/' +
                    AID + '__' + row["comparison_id"] + '.json"')
        comparisons.append({"assignment_id": AID, "comparison_id": row["comparison_id"],
                            "case_ids": row["case_ids"], "command": command})
    proposal = {"format": "worker-assignment-gpu-queue-proposal", "assignment_id": AID,
                "cases": cases, "comparison_audit_commands": comparisons}
    (ROOT / "gpu-queue-proposal.json").write_text(json.dumps(proposal, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(len(cases), len(comparisons))


if __name__ == "__main__":
    main()
