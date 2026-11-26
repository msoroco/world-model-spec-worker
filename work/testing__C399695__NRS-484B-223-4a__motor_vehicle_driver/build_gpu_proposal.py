"""Produce assignment-local exact GPU queue proposal for lead integration."""

import json
from pathlib import Path

from package_spec import AID

HERE = Path(__file__).resolve().parent
BASE = ('PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m '
        'scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" ')


def run():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    if manifest["assignment_id"] != AID or len(manifest["cases"]) != 4:
        raise ValueError("exact four-case manifest required")
    rows = []
    for index, entry in enumerate(manifest["cases"], start=1):
        case = entry["case_id"]
        select = (' --repo "$PWD" --batch full-test-delivery --db "$DB" '
                  '--assignment ' + AID + ' --case ' + case)
        prepare = BASE + 'prepare-delivery' + select
        execute = (BASE + 'execute-delivery' + select +
                   ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON"'
                   ' --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (BASE + 'accept-delivery' + select +
                  ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT"'
                  ' --audit "$AUDIT" --review-archive /external/archive')
        source = ('SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c399695-owner-nov26/gpu-audit" '
                  'TMPDIR="$PWD/.runtime-work/c399695-owner-nov26/gpu-audit" '
                  'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' + AID +
                  '/delivery_audit.py --case ' + case +
                  ' --attempt "$ATTEMPT" --review "$PIXEL_REVIEW"'
                  ' --physical "$PHYSICAL_RESULT"')
        rows.append({"order": index, "assignment_id": AID, "case_id": case,
                     "prepare_command": prepare, "execute_command": execute,
                     "accept_command": accept, "capture_command": execute,
                     "postprocessing_command": entry["post_capture"]["command"],
                     "owner_release_command": 'CASE_ID=' + case +
                     ' .venv-cpu/bin/python runtime.py owner-released --attempt "$ATTEMPT"'
                     ' --receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released',
                     "additional_source_audit_command": source,
                     "candidate_commands": {candidate["id"]: prepare +
                                            ' --candidate ' + candidate["id"]
                                            for candidate in entry["candidates"]}})
    comparisons = [{"assignment_id": AID,
                    "comparison_id": comparison["comparison_id"],
                    "command": ('SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c399695-owner-nov26/gpu-audit" '
                                'TMPDIR="$PWD/.runtime-work/c399695-owner-nov26/gpu-audit" '
                                'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' +
                                AID + '/comparison_audit.py --comparison ' +
                                comparison["comparison_id"] +
                                ' --records "$COMPARISON_RECORDS"'),
                    "record_requirement": "JSON mapping each comparison case ID to separately reviewed original delivery measurement"}
                   for comparison in plan["comparisons"]]
    output = {"format": "worker-ordered-gpu-queue-proposal",
              "assignment_id": AID, "source": "execution-manifest.json",
              "cases": rows, "comparison_audit_commands": comparisons}
    (HERE / "gpu-queue-proposal.json").write_text(json.dumps(output, indent=2) + "\n")
    return len(rows), len(comparisons)


if __name__ == "__main__":
    print("right-turn-lane queue proposal:", run())
