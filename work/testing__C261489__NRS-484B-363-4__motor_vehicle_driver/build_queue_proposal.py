"""Propose exact GPU dispatch rows for lead integration; never launch them here."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
ASSIGNMENT = HERE.name


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    operator = "work/" + ASSIGNMENT + "/native_operator.py"
    operator_sha = sha(HERE / "native_operator.py")
    module = 'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT"'
    rows = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        prepare = (module + ' prepare-delivery --repo "$PWD" --batch full-test-delivery --db "$DB"'
                   + ' --assignment ' + ASSIGNMENT + ' --case ' + case)
        execute = (module + ' execute-delivery --repo "$PWD" --batch full-test-delivery --db "$DB"'
                   + ' --run "$RUN" --assignment ' + ASSIGNMENT + ' --case ' + case
                   + ' --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (module + ' accept-delivery --repo "$PWD" --batch full-test-delivery --db "$DB"'
                  + ' --run "$RUN" --assignment ' + ASSIGNMENT + ' --case ' + case
                  + ' --job "$JOB_ID" --attempt "$ATTEMPT_ID" --audit "$AUDIT"'
                  + ' --review-archive /external/archive')
        rows.append({
            "assignment_id": ASSIGNMENT, "case_id": case,
            "prepare_command": prepare, "execute_command": execute, "accept_command": accept,
            "capture_command": ('SCENARIO_SCHOOL_PASS_SITE_PACKET="$SCHOOL_SITE_PACKET" '
                                'SCENARIO_SCHOOL_PASS_SITE_SHA256="$SCHOOL_SITE_SHA256" '
                                'SCENARIO_SCHOOL_PASS_OPERATOR_MODULE="$PWD/' + operator + '" '
                                'SCENARIO_SCHOOL_PASS_OPERATOR_SHA256=' + operator_sha
                                + ' "$CARLA_PYTHON" runtime.py capture --manifest work/'
                                + ASSIGNMENT + '/execution-manifest.json --case ' + case
                                + ' --output "$ATTEMPT" --host "$CARLA_HOST" --port "$CARLA_PORT"'
                                + ' --python "$CARLA_PYTHON"'),
            "owner_release_command": ('CASE_ID=' + case + ' .venv-cpu/bin/python runtime.py owner-released'
                                      + ' --attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT"'
                                      + ' --acknowledge-owner-released'),
            "postprocessing_command": entry["post_capture"]["command"],
            "additional_source_audit_command": ('.venv-cpu/bin/python work/' + ASSIGNMENT
                                                + '/delivery_audit.py --case ' + case
                                                + ' --attempt "$ATTEMPT" --output "$AUDIT_OUTPUT"'),
            "candidate_commands": {"fallback1": prepare + ' --candidate fallback1'},
        })
    comparisons = []
    for row in plan["comparisons"]:
        left, right = row["case_ids"]
        cid = row["comparison_id"]
        comparisons.append({"assignment_id": ASSIGNMENT, "comparison_id": cid,
                            "command": ('.venv-cpu/bin/python work/' + ASSIGNMENT
                                        + '/comparison_audit.py --comparison ' + cid
                                        + ' --left-case ' + left + ' --left-attempt "$LEFT_ATTEMPT"'
                                        + ' --right-case ' + right + ' --right-attempt "$RIGHT_ATTEMPT"'
                                        + ' --output "$COMPARISON_AUDIT_OUTPUT"')})
    (HERE / "queue-proposal.json").write_text(json.dumps({
        "format": "worker-exact-queue-proposal", "assignment_id": ASSIGNMENT,
        "cases": rows, "comparison_audit_commands": comparisons,
        "diagnostic_only": False, "not_dispatched": True,
    }, indent=2, sort_keys=True) + "\n")
    print(len(rows), "case queue rows and", len(comparisons), "comparisons proposed")


if __name__ == "__main__":
    main()
