"""Build a provisional exact-case queue for the two sourced exterior cases.

The full attention sweep can add cases only after original interior sources are
reviewed. This proposal is not the shared dispatch queue.
"""
from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
BATCH = "full-test-delivery"
LOCAL = ('PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python '
         '-m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" ')


def build() -> dict:
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    cases = sorted(item["case_id"] for item in manifest["cases"])
    expected = [ASSIGNMENT + "__steady_travel", ASSIGNMENT + "__steering_variation"]
    if (manifest.get("assignment_id") != ASSIGNMENT or cases != expected or
            len(plan["comparisons"]) != 1 or
            plan["comparisons"][0]["case_ids"] != expected):
        raise ValueError("provisional queue no longer matches selected exact cases")
    rows = []
    for order, case_id in enumerate(cases, 1):
        common = (' --repo "$PWD" --batch ' + BATCH + ' --db "$DB"'
                  ' --assignment ' + ASSIGNMENT + ' --case ' + case_id)
        prepare = LOCAL + "prepare-delivery" + common
        execute = (LOCAL + "execute-delivery" + common +
                   ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON"'
                   ' --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (LOCAL + "accept-delivery" + common +
                  ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT"'
                  ' --audit "$AUDIT" --review-archive /external/archive')
        rows.append({
            "order": order, "assignment_id": ASSIGNMENT, "case_id": case_id,
            "prepare_command": prepare, "execute_command": execute,
            "accept_command": accept, "capture_command": execute,
            "postprocessing_command": (
                ".venv-cpu/bin/python runtime.py process-saved --manifest work/" +
                ASSIGNMENT + "/execution-manifest.json --case " + case_id +
                ' --attempt "$ATTEMPT" --output "$PROCESSED"'
                ' --library runtime/library --validator "$LEAN_VALIDATOR"'
                ' --owner-release-receipt "$OWNER_RELEASE_RECEIPT"'),
            "owner_release_command": (
                "CASE_ID=" + case_id +
                " .venv-cpu/bin/python runtime.py owner-released --attempt"
                ' "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT"'
                ' --acknowledge-owner-released'),
            "additional_source_audit_command": (
                ".venv-cpu/bin/python work/" + ASSIGNMENT +
                "/source_audit_cli.py --case " + case_id +
                ' --attempt "$ATTEMPT" --output "$SOURCE_AUDIT_RECEIPT"'),
            "candidate_commands": {},
        })
    comparison = plan["comparisons"][0]
    result = {
        "format": "worker-ordered-gpu-queue-proposal",
        "assignment_id": ASSIGNMENT,
        "status": "partial_attention_sweep_source_pending",
        "source": "execution-manifest.json",
        "cases": rows,
        "comparison_audit_commands": [{
            "assignment_id": ASSIGNMENT,
            "comparison_id": comparison["comparison_id"],
            "command": (
                ".venv-cpu/bin/python work/" + ASSIGNMENT +
                "/saved_delivery.py --steady \"$STEADY_ATTEMPT\""
                ' --variation "$VARIATION_ATTEMPT"'
                ' --output "$COMPARISON_AUDIT_RECEIPT"'),
        }],
    }
    (HERE / "gpu-queue-proposal.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    proposal = build()
    print(json.dumps({"cases": len(proposal["cases"]),
                      "comparisons": len(proposal["comparison_audit_commands"]),
                      "status": proposal["status"]}))
