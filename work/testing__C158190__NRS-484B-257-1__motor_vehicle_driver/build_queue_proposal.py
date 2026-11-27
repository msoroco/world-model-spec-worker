"""Render the exact selected-case order; proposal stays partial until proofs exist."""

from __future__ import annotations

import json
from pathlib import Path

from stop_sign_branch import ASSIGNMENT


def build() -> dict:
    root = Path(__file__).resolve().parent
    plan = json.loads((root / "case-plan.json").read_text())
    cases = [case["case_id"] for case in plan["cases"]
             if case.get("kind") == "planned_controlled_construction"]
    rows = []
    for order, case_id in enumerate(cases, 1):
        common = ("PYTHONPATH=\"$PWD/runtime\" .venv-cpu/bin/python "
                  "-m scenario_pipeline.worker_exchange --root \"$LOCAL_ROOT\" ")
        dispatch = (f"--repo \"$PWD\" --batch full-test-delivery --db \"$DB\" "
                    f"--assignment {ASSIGNMENT} --case {case_id}")
        execute = common + "execute-delivery " + dispatch + (
            " --run \"$RUN\" --job \"$JOB_ID\" --python \"$CARLA_PYTHON\" "
            "--host \"$CARLA_HOST\" --port \"$CARLA_PORT\"")
        rows.append({
            "order": order, "assignment_id": ASSIGNMENT, "case_id": case_id,
            "prepare_command": common + "prepare-delivery " + dispatch,
            "execute_command": execute,
            "capture_command": execute,
            "owner_release_command": (f"CASE_ID={case_id} .venv-cpu/bin/python runtime.py "
                                      "owner-released --attempt \"$ATTEMPT\" --receipt "
                                      "\"$OWNER_RELEASE_RECEIPT\" --acknowledge-owner-released"),
            "postprocessing_command": (".venv-cpu/bin/python runtime.py process-saved "
                                       f"--manifest work/{ASSIGNMENT}/execution-manifest.json "
                                       f"--case {case_id} --attempt \"$ATTEMPT\" "
                                       "--output \"$PROCESSED\" --library runtime/library "
                                       "--validator \"$LEAN_VALIDATOR\" "
                                       "--owner-release-receipt \"$OWNER_RELEASE_RECEIPT\""),
            "additional_source_audit_command": (f"CASE_ID='{case_id}' .venv-cpu/bin/python work/{ASSIGNMENT}/"
                                                f"stop_source_audit.py --case {case_id} --original "
                                                "\"$ORIGINAL_PACKET\" --output \"$SOURCE_AUDIT_RECEIPT\""),
            "accept_command": (common + "accept-delivery " + dispatch +
                               " --run \"$RUN\" --job \"$JOB_ID\" --attempt \"$ATTEMPT\" "
                               "--audit \"$AUDIT\" --review-archive /external/archive"),
            "candidate_commands": {
                "fallback1": common + "prepare-delivery " + dispatch + " --candidate fallback1"}
        })
    comparison_rows = []
    for comparison in plan["comparisons"]:
        name = comparison["comparison_id"]
        comparison_rows.append({
            "assignment_id": ASSIGNMENT, "comparison_id": name,
            "case_ids": comparison["case_ids"],
            "command": (f"COMPARISON_ID='{name}' .venv-cpu/bin/python work/{ASSIGNMENT}/"
                        "stop_source_audit.py --left \"$LEFT_ORIGINAL_PACKET\" "
                        "--right \"$RIGHT_ORIGINAL_PACKET\" "
                        "--output \"$COMPARISON_AUDIT_RECEIPT\"")})
    return {"format": "worker-ordered-gpu-queue-proposal", "assignment_id": ASSIGNMENT,
            "status": "source_pending_cpu_bound", "source": "case-plan.json",
            "cases": rows, "comparison_audit_commands": comparison_rows,
            "dispatch_limit": "Do not run until selected manifest and source-bound CPU proofs pass."}


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    (root / "gpu-queue-proposal.json").write_text(
        json.dumps(build(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
