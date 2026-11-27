"""Emit exact canonical job commands for the C178244 delivery package."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
WORK = "work/" + AID
FRONT = 'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT"'
COMMON = f'--repo "$PWD" --batch full-test-delivery --db "$DB" --assignment {AID}'


def main() -> None:
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    rows = []
    for index, entry in enumerate(manifest["cases"], 1):
        case = entry["case_id"]
        tag = case.rsplit("__", 1)[-1]
        prepare = f'{FRONT} prepare-delivery {COMMON} --case {case}'
        execute = (f'{FRONT} execute-delivery --repo "$PWD" --batch full-test-delivery '
                   f'--db "$DB" --run "$RUN" --assignment {AID} --case {case} '
                   '--job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" '
                   '--port "$CARLA_PORT"')
        accept = (f'{FRONT} accept-delivery --repo "$PWD" --batch full-test-delivery '
                  f'--db "$DB" --run "$RUN" --assignment {AID} --case {case} '
                  '--job "$JOB_ID" --attempt "$ATTEMPT" --audit "$AUDIT" '
                  '--review-archive /external/archive')
        rows.append({
            "order": index, "assignment_id": AID, "case_id": case,
            "prepare_command": prepare, "execute_command": execute,
            "capture_command": execute, "accept_command": accept,
            "candidate_commands": {candidate["id"]: prepare + " --candidate " + candidate["id"]
                                   for candidate in entry["candidates"]},
            "owner_release_command": (f'CASE_ID={case} .venv-cpu/bin/python runtime.py '
                                      'owner-released --attempt "$ATTEMPT" '
                                      '--receipt "$OWNER_RELEASE_RECEIPT" '
                                      '--acknowledge-owner-released'),
            "postprocessing_command": (f'.venv-cpu/bin/python runtime.py process-saved '
                                       f'--manifest {WORK}/execution-manifest.json --case {case} '
                                       '--attempt "$ATTEMPT" --output "$PROCESSED" '
                                       '--library runtime/library --validator "$LEAN_VALIDATOR" '
                                       '--owner-release-receipt "$OWNER_RELEASE_RECEIPT"'),
            "additional_source_audit_command": (
                'mkdir -p "$PWD/.runtime-work/local-delivery-audit" && '
                'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/local-delivery-audit" '
                'TMPDIR="$PWD/.runtime-work/local-delivery-audit" '
                f'.venv-cpu/bin/python {WORK}/delivery_audit.py --case {case} '
                '--attempt "$ATTEMPT" > "$SOURCE_AUDIT"'),
            "physical_review_note": (f'{tag}: independently review original site, '
                                     'signal path, left turn, four camera views and legal source.'),
        })
    comparisons = []
    for item in plan["comparisons"]:
        command = (f'.venv-cpu/bin/python {WORK}/comparison_audit.py '
                   f'--comparison {item["comparison_id"]} ' +
                   " ".join(f'--attempt "$ATTEMPT_{case.rsplit("__", 1)[-1]}"'
                            for case in item["case_ids"]) +
                   ' > "$COMPARISON_AUDIT"')
        comparisons.append({"assignment_id": AID,
                            "comparison_id": item["comparison_id"],
                            "case_ids": item["case_ids"], "command": command})
    proposal = {"format": "worker-assignment-gpu-queue-proposal",
                "assignment_id": AID, "cases": rows,
                "comparison_audit_commands": comparisons}
    (ROOT / "gpu-queue-proposal.json").write_text(
        json.dumps(proposal, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
