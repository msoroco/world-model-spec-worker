"""Build exact-case portable GPU queue intent for lead integration."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
REL = "work/" + AID


def build():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    rows = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        common = ("PYTHONPATH=\"$PWD/runtime\" .venv-cpu/bin/python "
                  "-m scenario_pipeline.worker_exchange --root \"$LOCAL_ROOT\" ")
        base = (f" --repo \"$PWD\" --batch full-test-delivery --db \"$DB\" "
                f"--assignment {AID} --case {case}")
        prepare = common + "prepare-delivery" + base
        sourced = ("SCENARIO_CENTER_LANE_SITE_PACKET=\"$CENTER_LANE_SITE_PACKET\" "
                   "SCENARIO_CENTER_LANE_SITE_SHA256=\"$CENTER_LANE_SITE_SHA256\" "
                   "SCENARIO_CENTER_LANE_OPERATOR_MODULE=\"$CENTER_LANE_OPERATOR_MODULE\" "
                   "SCENARIO_CENTER_LANE_OPERATOR_SHA256=\"$CENTER_LANE_OPERATOR_SHA256\" ")
        execute = (sourced + common + "execute-delivery" + base +
                   " --run \"$RUN\" --job \"$JOB_ID\" --python \"$CARLA_PYTHON\" "
                   "--host \"$CARLA_HOST\" --port \"$CARLA_PORT\"")
        accept = (common + "accept-delivery" + base +
                  " --run \"$RUN\" --job \"$JOB_ID\" --attempt \"$ATTEMPT\" "
                  "--audit \"$AUDIT\" --review-archive \"$REVIEW_ARCHIVE\"")
        rows.append({"assignment_id": AID, "case_id": case,
                     "prepare_command": prepare, "execute_command": execute,
                     "capture_command": execute, "accept_command": accept,
                     "owner_release_command": (f"CASE_ID={case} .venv-cpu/bin/python runtime.py "
                         "owner-released --attempt \"$ATTEMPT\" --receipt \"$OWNER_RELEASE_RECEIPT\" "
                         "--acknowledge-owner-released"),
                     "postprocessing_command": (f".venv-cpu/bin/python runtime.py process-saved "
                         f"--manifest {REL}/execution-manifest.json --case {case} "
                         "--attempt \"$ATTEMPT\" --output \"$PROCESSED\" "
                         "--library runtime/library --validator \"$LEAN_VALIDATOR\" "
                         "--owner-release-receipt \"$OWNER_RELEASE_RECEIPT\""),
                     "additional_source_audit_command": (
                         "mkdir -p \"$PWD/.runtime-work/local-center-lane-audit\" && "
                         "SCENARIO_PIPELINE_OUTPUT_ROOT=\"$PWD/.runtime-work/local-center-lane-audit\" "
                         "TMPDIR=\"$PWD/.runtime-work/local-center-lane-audit\" "
                         f"PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python {REL}/delivery_audit.py "
                         f"--case-id {case} --attempt \"$ATTEMPT\" --plan {REL}/case-plan.json "
                         "--output \"$AUDIT\""),
                     "candidate_commands": {candidate["id"]: prepare +
                         " --candidate " + candidate["id"]
                         for candidate in entry.get("candidates", [])}})
    comparisons = []
    for row in plan["comparisons"]:
        ident = AID + "__" + row["comparison_id"]
        member_args = " ".join(f'--attempt "${{ATTEMPT_{i}}}"'
                               for i in range(len(row["case_ids"])))
        comparisons.append({"assignment_id": AID, "comparison_id": row["comparison_id"],
                            "case_ids": row["case_ids"], "command": (
                                f"PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python {REL}/comparison_audit.py "
                                f"{member_args} --comparison {row['comparison_id']} "
                                f"--comparison-id {ident} --plan {REL}/case-plan.json "
                                ' --output "$COMPARISON_AUDIT"')})
    output = {"format": "worker-assignment-gpu-queue-proposal",
              "assignment_id": AID, "cases": rows,
              "comparison_audit_commands": comparisons}
    path = HERE / "gpu-queue-proposal.json"
    path.write_text(json.dumps(output, sort_keys=True, indent=2) + "\n")
    return len(rows)


if __name__ == "__main__":
    print(build())
