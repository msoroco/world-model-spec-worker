"""Build exact local handoff commands for all curb/shoulder cases and comparisons."""
from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
AID = HERE.name
PREFIX = 'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT"'
SOURCE = ('C183357_1B_REVIEWED_PACKET="$C183357_1B_REVIEWED_PACKET" '
          'C183357_1B_NATIVE_ADAPTER_MODULE="$C183357_1B_NATIVE_ADAPTER_MODULE" ')


def build():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    cases = []
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        fixed = f'--repo "$PWD" --batch full-test-delivery --db "$DB" --assignment {AID} --case {case_id}'
        prepare = PREFIX + " prepare-delivery " + fixed
        execute = (SOURCE + PREFIX + " execute-delivery " + fixed +
                   ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON"' +
                   ' --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (PREFIX + " accept-delivery " + fixed +
                  ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT"' +
                  ' --audit "$AUDIT" --review-archive /external/archive')
        owner = (f'CASE_ID={case_id} .venv-cpu/bin/python runtime.py owner-released '
                 '--attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT" '
                 '--acknowledge-owner-released')
        saved = (f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/execution-manifest.json '
                 f'--case {case_id} --attempt "$ATTEMPT" --output "$PROCESSED" '
                 '--library runtime/library --validator "$LEAN_VALIDATOR" '
                 '--owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        audit = (f'mkdir -p "$PWD/.runtime-work/local-curb-audit" && '
                 'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/local-curb-audit" '
                 'TMPDIR="$PWD/.runtime-work/local-curb-audit" PYTHONDONTWRITEBYTECODE=1 '
                 f'.venv-cpu/bin/python work/{AID}/delivery_audit.py --case-id {case_id} '
                 f'--attempt "$ATTEMPT" --plan work/{AID}/case-plan.json --output "$AUDIT"')
        cases.append({"assignment_id": AID, "case_id": case_id,
                      "prepare_command": prepare, "execute_command": execute,
                      "capture_command": execute, "accept_command": accept,
                      "owner_release_command": owner,
                      "postprocessing_command": saved,
                      "additional_source_audit_command": audit,
                      "candidate_commands": {candidate["id"]:
                          prepare + " --candidate " + candidate["id"]
                          for candidate in entry["candidates"]}})
    comparisons = []
    for row in plan["comparisons"]:
        cid = AID + "__" + row["comparison_id"]
        command = (f'mkdir -p "$PWD/.runtime-work/local-curb-audit" && '
                   'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/local-curb-audit" '
                   'TMPDIR="$PWD/.runtime-work/local-curb-audit" PYTHONDONTWRITEBYTECODE=1 '
                   f'.venv-cpu/bin/python work/{AID}/comparison_audit.py '
                   f'--comparison-id {cid} '
                   f'--plan work/{AID}/case-plan.json')
        for index, _ in enumerate(row["case_ids"], 1):
            command += f' --attempt "$ATTEMPT_{index}"'
        command += ' --output "$COMPARISON_AUDIT"'
        comparisons.append({"assignment_id": AID,
                            "comparison_id": row["comparison_id"],
                            "command": command})
    value = {"format": "worker-assignment-gpu-queue-proposal",
             "assignment_id": AID, "cases": cases,
             "comparison_audit_commands": comparisons}
    path = HERE / "gpu-queue-proposal.json"
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    return len(cases), len(comparisons)


if __name__ == "__main__":
    print(build())
