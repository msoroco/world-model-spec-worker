"""Prepare ten exact case rows and five source-bound comparison commands."""
from __future__ import annotations

import json
from pathlib import Path

from engineering_sweep_station import engineering_station
from reviewed_scene import ASSIGNMENT

HERE = Path(__file__).resolve().parent
PREFIX = 'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT"'
COMMON = f'--repo "$PWD" --batch full-test-delivery --db "$DB" --assignment {ASSIGNMENT}'
SOURCE = 'C147344_AUTHORITY_ROOT="$C147344_AUTHORITY_ROOT" C147344_SITE_REF="$C147344_SITE_REF" '


def main() -> None:
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    rows = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        selected = f"{COMMON} --case {case}"
        prepare = f"{PREFIX} prepare-delivery {selected}"
        execute = f"{SOURCE}{PREFIX} execute-delivery {selected} --run \"$RUN\" --job \"$JOB_ID\" --python \"$CARLA_PYTHON\" --host \"$CARLA_HOST\" --port \"$CARLA_PORT\""
        accept = f"{PREFIX} accept-delivery {selected} --run \"$RUN\" --job \"$JOB_ID\" --attempt \"$ATTEMPT\" --audit \"$AUDIT\" --review-archive /external/archive"
        release = f"CASE_ID={case} .venv-cpu/bin/python runtime.py owner-released --attempt \"$ATTEMPT\" --receipt \"$OWNER_RELEASE_RECEIPT\" --acknowledge-owner-released"
        saved = f".venv-cpu/bin/python runtime.py process-saved --manifest work/{ASSIGNMENT}/execution-manifest.json --case {case} --attempt \"$ATTEMPT\" --output \"$PROCESSED\" --library runtime/library --validator \"$LEAN_VALIDATOR\" --owner-release-receipt \"$OWNER_RELEASE_RECEIPT\""
        source_audit = f".venv-cpu/bin/python work/{ASSIGNMENT}/audit_exact_case.py --case {case} --authority-root \"$C147344_AUTHORITY_ROOT\" --receipt \"$RECEIPT\" --output \"$AUDIT\""
        rows.append({"assignment_id": ASSIGNMENT, "case_id": case,
                     "prepare_command": prepare, "execute_command": execute,
                     "capture_command": execute, "accept_command": accept,
                     "owner_release_command": release, "postprocessing_command": saved,
                     "additional_source_audit_command": source_audit,
                     "candidate_commands": {candidate["id"]: f"{prepare} --candidate {candidate['id']}"
                                            for candidate in entry.get("candidates", [])}})
    comparisons = []
    sweep_receipts = " ".join(f'--receipt \"$SWEEP_RECEIPT_{rank}\"' for rank in range(6))
    for comparison in plan["comparisons"]:
        cid = comparison["comparison_id"]
        ids = comparison["case_ids"]
        if cid.endswith("_engineering_speed_sweep"):
            command = f".venv-cpu/bin/python work/{ASSIGNMENT}/engineering_sweep_audit.py --authority-root \"$C147344_AUTHORITY_ROOT\" --site-ref \"$C147344_SITE_REF\" {sweep_receipts} --output \"$SWEEP_AUDIT\""
        else:
            command = f".venv-cpu/bin/python work/{ASSIGNMENT}/comparison_audit.py --comparison {cid} --left-plan \"$LEFT_PLAN\" --right-plan \"$RIGHT_PLAN\" --left-result \"$LEFT_RESULT\" --right-result \"$RIGHT_RESULT\" --output \"$COMPARISON_AUDIT\""
        comparisons.append({"assignment_id": ASSIGNMENT, "comparison_id": cid,
                            "case_ids": ids, "command": command})
    output = {"format": "worker-assignment-gpu-queue-proposal", "assignment_id": ASSIGNMENT,
              "cases": rows, "comparison_audit_commands": comparisons}
    (HERE / "gpu-queue-proposal.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(len(rows), len(comparisons))


if __name__ == "__main__":
    main()
