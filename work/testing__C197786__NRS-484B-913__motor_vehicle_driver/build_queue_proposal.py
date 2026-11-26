"""Write exact assignment queue rows for lead integration into the shared queue."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
PREFIX = 'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" '
COMMON = '--repo "$PWD" --batch full-test-delivery --db "$DB" '


def main():
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    rows = []
    for order, entry in enumerate(manifest["cases"], 1):
        case = entry["case_id"]
        short = case.removeprefix(ASSIGNMENT + "__")
        exact = f"--assignment {ASSIGNMENT} --case {case}"
        prepare = PREFIX + "prepare-delivery " + COMMON + exact
        execute = (PREFIX + "execute-delivery " + COMMON + '--run "$RUN" ' + exact +
                   ' --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (PREFIX + "accept-delivery " + COMMON + '--run "$RUN" ' + exact +
                  ' --job "$JOB_ID" --attempt "$ATTEMPT" --audit "$AUDIT" --review-archive /external/archive')
        post = (f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{ASSIGNMENT}/execution-manifest.json '
                f'--case {case} --attempt "$ATTEMPT" --output "$PROCESSED" --library runtime/library '
                '--validator "$LEAN_VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        release = (f'CASE_ID={case} .venv-cpu/bin/python runtime.py owner-released '
                   '--attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released')
        passage = "avoid" if short.endswith("_avoid") else "cross"
        audit = (f'.venv-cpu/bin/python work/{ASSIGNMENT}/delivery_audit.py '
                 '--packet "$ATTEMPT/saved-packet.json" --source-root "$ATTEMPT" '
                 f'--case-id {case} --require-complete-body --require-camera-sources '
                 f'--expected-passage {passage} --output "$AUDIT_OUTPUT"')
        rows.append({"order": order, "assignment_id": ASSIGNMENT, "case_id": case,
                     "prepare_command": prepare, "execute_command": execute,
                     "accept_command": accept, "capture_command": execute,
                     "postprocessing_command": post, "owner_release_command": release,
                     "additional_source_audit_command": audit,
                     "candidate_commands": {candidate["id"]: prepare + " --candidate " + candidate["id"]
                                            for candidate in entry.get("candidates", [])}})
    variables = {"command_consent": "consent", "command_refusal": "consent",
                 "hose_protection": "protection", "physical_passage": "passage",
                 "fire_vs_alarm": "incident_purpose", "fire_vs_practice": "incident_purpose"}
    comparisons = []
    for item in plan["comparisons"]:
        ident = item["comparison_id"]
        left, right = item["case_ids"]
        other_passage = "avoid" if right.endswith("_avoid") else "cross"
        command = (f'.venv-cpu/bin/python work/{ASSIGNMENT}/delivery_audit.py '
                   '--packet "$LEFT_ATTEMPT/saved-packet.json" --source-root "$LEFT_ATTEMPT" '
                   f'--case-id {left} --compare "$RIGHT_ATTEMPT/saved-packet.json" '
                   '--compare-source-root "$RIGHT_ATTEMPT" '
                   f'--variable {variables[ident]} --require-complete-body --require-camera-sources '
                   f'--expected-passage cross --compare-expected-passage {other_passage} '
                   '--output "$COMPARISON_AUDIT_OUTPUT"')
        comparisons.append({"assignment_id": ASSIGNMENT, "comparison_id": ident,
                            "case_ids": [left, right], "command": command})
    proposal = {"format": "worker-assignment-queue-proposal", "assignment_id": ASSIGNMENT,
                "cases": rows, "comparison_audit_commands": comparisons,
                "note": "Relative order 1..7; lead assigns final shared queue order. GPU commands are unexecuted."}
    (ROOT / "queue-proposal.json").write_text(json.dumps(proposal, indent=2) + "\n")
    print(len(rows), "cases", len(comparisons), "comparisons")


if __name__ == "__main__":
    main()
