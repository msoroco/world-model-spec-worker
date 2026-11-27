"""Build exact heavy-vehicle job and comparison commands without claiming readiness."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    common = ('PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python '
              '-m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" ')
    rows = []
    for order, case in enumerate(plan["cases"], 1):
        case_id = case["case_id"]
        dispatch = (f'--repo "$PWD" --batch full-test-delivery --db "$DB" '
                    f'--assignment {ASSIGNMENT} --case {case_id}')
        execute = (common + "execute-delivery " + dispatch +
                   ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" '
                   '--host "$CARLA_HOST" --port "$CARLA_PORT"')
        rows.append({
            "order": order, "assignment_id": ASSIGNMENT, "case_id": case_id,
            "prepare_command": common + "prepare-delivery " + dispatch,
            "execute_command": execute, "capture_command": execute,
            "owner_release_command": (f'CASE_ID={case_id} .venv-cpu/bin/python runtime.py '
                                      'owner-released --attempt "$ATTEMPT" --receipt '
                                      '"$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released'),
            "postprocessing_command": ('.venv-cpu/bin/python runtime.py process-saved '
                                       f'--manifest work/{ASSIGNMENT}/execution-manifest.json '
                                       f'--case {case_id} --attempt "$ATTEMPT" '
                                       '--output "$PROCESSED" --library runtime/library '
                                       '--validator "$LEAN_VALIDATOR" '
                                       '--owner-release-receipt "$OWNER_RELEASE_RECEIPT"'),
            "additional_source_audit_command": (
                f'.venv-cpu/bin/python work/{ASSIGNMENT}/diagnostic_delivery_audit.py '
                f'--index "$DELIVERY_INDEX" --case {case_id} '
                '--output "$SOURCE_AUDIT_RECEIPT"'),
            "accept_command": (common + "accept-delivery " + dispatch +
                               ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT" '
                               '--audit "$AUDIT" --review-archive /external/archive'),
            "candidate_commands": {}
        })
    comparisons = [{"assignment_id": ASSIGNMENT,
                    "comparison_id": item["comparison_id"],
                    "case_ids": item["case_ids"],
                    "command": (f'.venv-cpu/bin/python work/{ASSIGNMENT}/comparison_audit.py '
                                f'--comparison {item["comparison_id"]} '
                                '--left "$LEFT_ORIGINAL_PACKET" '
                                '--right "$RIGHT_ORIGINAL_PACKET" '
                                '--output "$COMPARISON_AUDIT_RECEIPT"')}
                   for item in plan["comparisons"]]
    return {"format": "worker-ordered-gpu-queue-proposal",
            "assignment_id": ASSIGNMENT, "status": "partial_source_gated",
            "source": "case-plan.json", "cases": rows,
            "comparison_audit_commands": comparisons,
            "dispatch_limit": "Reviewed original site/operator and Native capture sources are required before physical acceptance."}


if __name__ == "__main__":
    (ROOT / "gpu-queue-proposal.json").write_text(
        json.dumps(build(), indent=2, sort_keys=True) + "\n")
