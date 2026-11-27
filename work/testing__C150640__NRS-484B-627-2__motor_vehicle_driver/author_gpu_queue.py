"""Propose canonical local jobs for six exact stop cases and five comparisons."""
from __future__ import annotations

import json
from pathlib import Path

from stop_model import ASSIGNMENT


ROOT = Path(__file__).resolve().parent
PREFIX = 'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT"'
COMMON = f'--repo "$PWD" --batch full-test-delivery --db "$DB" --assignment {ASSIGNMENT}'
SOURCE = 'C150640_STOP_REVIEWED_SCENE="$C150640_STOP_REVIEWED_SCENE" '


def main():
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    rows = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        selected = f"{COMMON} --case {case}"
        prepare = f"{PREFIX} prepare-delivery {selected}"
        execute = (f"{SOURCE}{PREFIX} execute-delivery {selected} --run \"$RUN\" "
                   "--job \"$JOB_ID\" --python \"$CARLA_PYTHON\" "
                   "--host \"$CARLA_HOST\" --port \"$CARLA_PORT\"")
        accept = (f"{PREFIX} accept-delivery {selected} --run \"$RUN\" "
                  "--job \"$JOB_ID\" --attempt \"$ATTEMPT\" --audit \"$AUDIT\" "
                  "--review-archive /external/archive")
        release = (f"CASE_ID={case} .venv-cpu/bin/python runtime.py owner-released "
                   "--attempt \"$ATTEMPT\" --receipt \"$OWNER_RELEASE_RECEIPT\" "
                   "--acknowledge-owner-released")
        saved = (f".venv-cpu/bin/python runtime.py process-saved --manifest "
                 f"work/{ASSIGNMENT}/execution-manifest.json --case {case} "
                 "--attempt \"$ATTEMPT\" --output \"$PROCESSED\" "
                 "--library runtime/library --validator \"$LEAN_VALIDATOR\" "
                 "--owner-release-receipt \"$OWNER_RELEASE_RECEIPT\"")
        source_audit = (f".venv-cpu/bin/python work/{ASSIGNMENT}/delivery_audit.py "
                        f"--case {case} --attempt \"$ATTEMPT\" "
                        "--processing \"$PROCESSING_RECEIPT\" "
                        "--decode-receipt \"$DECODE_RECEIPT\" > \"$AUDIT\"")
        rows.append({"assignment_id": ASSIGNMENT, "case_id": case,
                     "prepare_command": prepare, "execute_command": execute,
                     "capture_command": execute, "accept_command": accept,
                     "owner_release_command": release,
                     "postprocessing_command": saved,
                     "additional_source_audit_command": source_audit,
                     "candidate_commands": {candidate["id"]: f"{prepare} --candidate {candidate['id']}"
                                            for candidate in entry.get("candidates", [])}})
    comparisons = []
    for item in plan["comparisons"]:
        comparison = item["comparison_id"]
        command = (f".venv-cpu/bin/python work/{ASSIGNMENT}/comparison_audit.py "
                   f"--comparison {comparison} --report-map \"$REPORT_MAP\" "
                   "--output \"$COMPARISON_AUDIT\"")
        comparisons.append({"assignment_id": ASSIGNMENT,
                            "comparison_id": comparison,
                            "case_ids": item["case_ids"], "command": command})
    output = {"format": "worker-assignment-gpu-queue-proposal",
              "assignment_id": ASSIGNMENT,
              "cases": rows, "comparison_audit_commands": comparisons}
    (ROOT / "gpu-queue-proposal.json").write_text(json.dumps(output, indent=2) + "\n",
                                                     encoding="utf-8")
    print(len(rows), len(comparisons))


if __name__ == "__main__":
    main()
