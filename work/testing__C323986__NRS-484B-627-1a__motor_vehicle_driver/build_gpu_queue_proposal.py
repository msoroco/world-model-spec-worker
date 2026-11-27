"""Propose exact delivery and saved comparison commands for this assignment."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
AID = "testing__C323986__NRS-484B-627-1a__motor_vehicle_driver"
PREFIX = 'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT"'
COMMON = f'--repo "$PWD" --batch full-test-delivery --db "$DB" --assignment {AID}'
SITE = 'C323986_AUTHORITY_ROOT="$C323986_AUTHORITY_ROOT" C323986_SITE_REF="$C323986_SITE_REF" '


def main() -> None:
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    rows = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        selected = f"{COMMON} --case {case}"
        prepare = f"{PREFIX} prepare-delivery {selected}"
        execute = (f"{SITE}{PREFIX} execute-delivery {selected} --run \"$RUN\" "
                   '--job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (f"{PREFIX} accept-delivery {selected} --run \"$RUN\" --job \"$JOB_ID\" "
                  '--attempt "$ATTEMPT" --audit "$AUDIT" --review-archive /external/archive')
        release = (f"CASE_ID='{case}' .venv-cpu/bin/python runtime.py owner-released "
                   '--attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT" '
                   '--acknowledge-owner-released')
        saved = (f".venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/execution-manifest.json "
                 f"--case {case} --attempt \"$ATTEMPT\" --output \"$PROCESSED\" "
                 '--library runtime/library --validator "$LEAN_VALIDATOR" '
                 '--owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        audit = (f".venv-cpu/bin/python work/{AID}/delivery_audit.py --case {case} "
                 '--attempt "$ATTEMPT" > "$AUDIT"')
        rows.append({"assignment_id": AID, "case_id": case,
                     "prepare_command": prepare, "execute_command": execute,
                     "capture_command": execute, "accept_command": accept,
                     "owner_release_command": release,
                     "postprocessing_command": saved,
                     "additional_source_audit_command": audit,
                     "candidate_commands": {candidate["id"]:
                         f"{prepare} --candidate {candidate['id']}"
                         for candidate in entry.get("candidates", [])}})
    comparisons = []
    for comparison in plan["comparisons"]:
        ident = comparison["comparison_id"]
        attempts = " ".join(f'--attempt "$ATTEMPT_{index}"'
                            for index in range(len(comparison["case_ids"])))
        command = (f".venv-cpu/bin/python work/{AID}/comparison_audit.py "
                   f"--comparison {ident} {attempts} > \"$COMPARISON_AUDIT\"")
        comparisons.append({"assignment_id": AID, "comparison_id": ident,
                            "case_ids": comparison["case_ids"], "command": command})
    (ROOT / "gpu-queue-proposal.json").write_text(json.dumps({
        "format": "worker-assignment-gpu-queue-proposal", "assignment_id": AID,
        "cases": rows, "comparison_audit_commands": comparisons}, indent=2) + "\n")
    print(len(rows), len(comparisons))


if __name__ == "__main__":
    main()
