"""Build the exact local-operator command fragment for C158208-2."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
MANIFEST = "work/" + ASSIGNMENT + "/execution-manifest.json"
LIBRARY = "runtime/library"
VALIDATOR = "$VALIDATOR"
CANONICAL = "PYTHONPATH=runtime/scenario_pipeline $CARLA_PYTHON -m worker_exchange"


def run():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    cases = []
    for order, entry in enumerate(manifest["cases"], 1):
        case = entry["case_id"]
        common = " --repo . --batch batch.json --db $DB --assignment " + ASSIGNMENT + " --case " + case
        cases.append({
            "order": order,
            "assignment_id": ASSIGNMENT,
            "case_id": case,
            "prepare_command": CANONICAL + " prepare-delivery" + common,
            "execute_command": CANONICAL + " execute-delivery" + common
                               + " --run $RUN --job $JOB_ID --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT",
            "accept_command": CANONICAL + " accept-delivery" + common
                              + " --run $RUN --job $JOB_ID --attempt $ATTEMPT --audit $AUDIT"
                              + " --review-archive /external/archive",
            "capture_command": "$CARLA_PYTHON runtime.py capture --manifest " + MANIFEST
                               + " --case " + case + " --output $ATTEMPT --host $CARLA_HOST"
                               + " --port $CARLA_PORT --python $CARLA_PYTHON",
            "postprocessing_command": ".venv-cpu/bin/python runtime.py process-saved --manifest "
                                      + MANIFEST + " --case " + case + " --attempt $ATTEMPT"
                                      + " --output $OUTPUT --library " + LIBRARY + " --validator "
                                      + VALIDATOR + " --owner-release-receipt $ATTEMPT/owner-release.json",
            "owner_release_command": "SCENARIO_CASE_ID=" + case
                                     + " .venv-cpu/bin/python runtime.py owner-released --attempt $ATTEMPT"
                                     + " --receipt $ATTEMPT/owner-release.json --acknowledge-owner-released",
            "additional_source_audit_command": ".venv-cpu/bin/python work/" + ASSIGNMENT
                                               + "/delivery_audit.py --attempt $ATTEMPT --case " + case,
            "candidate_commands": {candidate["id"]: CANONICAL + " prepare-delivery" + common
                                   + " --candidate " + candidate["id"]
                                   for candidate in entry.get("candidates", [])},
        })
    comparisons = [
        {"assignment_id": ASSIGNMENT, "comparison_id": item["comparison_id"],
         "command": ".venv-cpu/bin/python work/" + ASSIGNMENT
                    + "/comparison_audit.py --comparison " + item["comparison_id"]
                    + " --attempt $LEFT_ATTEMPT --attempt $RIGHT_ATTEMPT"}
        for item in plan["comparisons"]
    ]
    result = {"format": "worker-assignment-dispatch-plan", "assignment_id": ASSIGNMENT,
              "status": "cpu_prepared_partial", "cases": cases,
              "comparison_audit_commands": comparisons,
              "scope": "Exact local-operator commands; no Native execution or acceptance occurred here"}
    (HERE / "dispatch-plan.json").write_text(json.dumps(result, indent=2) + "\n")
    print("planned", len(cases), "exact cases,", len(comparisons), "comparison audits")


if __name__ == "__main__":
    run()
