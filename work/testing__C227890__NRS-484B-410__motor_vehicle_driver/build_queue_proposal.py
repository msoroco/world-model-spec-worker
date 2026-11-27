"""Build exact canonical GPU handoff commands after scoped CPU readiness."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
ROOT = "work/" + AID
BASE = 'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" '
ENV = ('SCENARIO_PARKED_SITE_PACKET="$PARKED_SITE_PACKET" '
       'SCENARIO_PARKED_SITE_SHA256="$PARKED_SITE_SHA256" '
       'SCENARIO_PARKED_OPERATOR_MODULE="$PARKED_OPERATOR_MODULE" '
       'SCENARIO_PARKED_OPERATOR_SHA256="$PARKED_OPERATOR_SHA256" '
       'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/local-delivery" ')
AUDIT_ENV = ('mkdir -p "$PWD/.runtime-work/local-parked-audit" && '
             'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/local-parked-audit" '
             'TMPDIR="$PWD/.runtime-work/local-parked-audit" PYTHONDONTWRITEBYTECODE=1 ')


def main():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    cases = []
    for entry in manifest["cases"]:
        cid = entry["case_id"]
        common = '--repo "$PWD" --batch full-test-delivery --db "$DB" --assignment ' + AID + ' --case ' + cid
        prepare = BASE + "prepare-delivery " + common
        execute = ENV + BASE + "execute-delivery " + common + ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"'
        accept = BASE + "accept-delivery " + common + ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT" --audit "$AUDIT" --review-archive /external/archive'
        audit = (AUDIT_ENV + ".venv-cpu/bin/python " + ROOT + "/delivery_audit.py --case-id " + cid +
                 ' --attempt "$ATTEMPT" --plan ' + ROOT + '/case-plan.json --output "$AUDIT"')
        post = (".venv-cpu/bin/python runtime.py process-saved --manifest " + ROOT +
                "/execution-manifest.json --case " + cid + ' --attempt "$ATTEMPT" --output "$PROCESSED"'
                ' --library runtime/library --validator "$LEAN_VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        cases.append({"assignment_id": AID, "case_id": cid,
                      "prepare_command": prepare, "execute_command": execute,
                      "capture_command": execute, "accept_command": accept,
                      "additional_source_audit_command": audit,
                      "postprocessing_command": post,
                      "owner_release_command": "CASE_ID=" + cid + ' .venv-cpu/bin/python runtime.py owner-released --attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released',
                      "candidate_commands": {candidate["id"]: prepare + " --candidate " + candidate["id"]
                                             for candidate in entry["candidates"]}})
    comparisons = []
    for row in plan["comparisons"]:
        comparison = row["comparison_id"]
        command = (AUDIT_ENV + ".venv-cpu/bin/python " + ROOT + "/comparison_audit.py --comparison " +
                   comparison + " --comparison-id " + AID + "__" + comparison + " --plan " + ROOT +
                   '/case-plan.json --attempt "$ATTEMPT_1" --attempt "$ATTEMPT_2" --output "$COMPARISON_AUDIT"')
        comparisons.append({"assignment_id": AID, "comparison_id": comparison, "command": command})
    (HERE / "queue-proposal.json").write_text(json.dumps({"format": "worker-ordered-gpu-queue",
                                                           "assignment_id": AID, "cases": cases,
                                                           "comparison_audit_commands": comparisons},
                                                          indent=2, sort_keys=True) + "\n")
    print("proposal", len(cases), len(comparisons))


if __name__ == "__main__":
    main()
