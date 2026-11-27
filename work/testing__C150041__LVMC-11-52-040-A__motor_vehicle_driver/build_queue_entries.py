"""Author exact C150041 local dispatch commands as a partial queue packet."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
LOCAL = 'python3.11 -m scenario_pipeline.worker_exchange --project "$PROJECT" --root "$LOCAL_ROOT"'
BASE = ' --repo "$WORKER_REPO" --batch full-test-delivery --db "$DB" --assignment ' + AID


def build() -> dict:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    draft = json.loads((ROOT / "execution-manifest.json").read_text())
    acceptance = json.loads((ROOT / "execution-manifest.json").read_text())
    expected = {entry["case_id"] for entry in plan["cases"]}
    entries = {entry["case_id"]: entry for entry in draft["cases"]}
    contracts = {entry["case_id"] for entry in acceptance["cases"] if entry.get("delivery_acceptance")}
    pairs = {entry["comparison_id"] for entry in plan["comparisons"]}
    if (len(expected) != 16 or expected != set(entries) or expected != contracts or
            len(pairs) != 13 or pairs != {entry["comparison_id"] for entry in plan["comparisons"]}):
        raise ValueError("exact C150041 queue coverage differs")
    cases = []
    for order, case in enumerate(sorted(expected), 1):
        execute = (LOCAL + " execute-delivery" + BASE + ' --run "$RUN" --case ' + case +
                   ' --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"')
        candidates = [entry["id"] for entry in entries[case].get("candidates", [])]
        cases.append({
            "order": order, "assignment_id": AID, "case_id": case,
            "prepare_command": LOCAL + " prepare-delivery" + BASE + " --case " + case,
            "candidate_commands": {candidate: LOCAL + " prepare-delivery" + BASE +
                                   " --case " + case + " --candidate " + candidate
                                   for candidate in candidates},
            "execute_command": execute, "capture_command": execute,
            "owner_release_command": ('CASE_ID=' + case +
                                      ' PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py owner-released'
                                      ' --attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT"'
                                      ' --acknowledge-owner-released'),
            "postprocessing_command": ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved'
                                       ' --manifest work/' + AID + '/execution-manifest.json --case ' + case +
                                       ' --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" --library "$LIBRARY"'
                                       ' --validator "$VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"'),
            "additional_source_audit_command": ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' +
                                                AID + '/independent/delivery_audit.py --case-id ' + case +
                                                ' --attempt "$ATTEMPT" --physical-receipt "$PHYSICAL_RECEIPT"'
                                                ' --pixel-review "$PIXEL_REVIEW" --decode-receipt "$DECODE_RECEIPT"'
                                                ' --media-auditor "$MEDIA_AUDITOR" --job-id "$JOB_ID"'
                                                ' --attempt-number "$ATTEMPT_NUMBER" --recording-id "$RECORDING_ID"'
                                                ' --output "$AUDIT"'),
            "accept_command": (LOCAL + " accept-delivery" + BASE + ' --run "$RUN" --case ' + case +
                               ' --job "$JOB_ID" --attempt "$ATTEMPT_NUMBER" --audit "$AUDIT"'
                               ' --review-archive /external/archive')})
    comparisons = []
    for entry in plan["comparisons"]:
        pair = entry["comparison_id"]
        auditor = ('sweep_comparison_audit.py' if pair in {
            'sweep_0_vs_20', 'sweep_10_vs_30', 'sweep_40_vs_60',
            'sweep_30_vs_50', 'sweep_70_vs_90', 'sweep_60_vs_80'}
                   else 'comparison_audit.py')
        comparisons.append({
            "assignment_id": AID, "comparison_id": pair, "case_ids": entry["case_ids"],
            "command": ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' + AID +
                        '/independent/' + auditor + ' --comparison-id ' + pair +
                        ' --baseline-attempt "$BASELINE_ATTEMPT" --changed-attempt "$CHANGED_ATTEMPT"'
                        ' --baseline-delivery "$BASELINE_DELIVERY" --changed-delivery "$CHANGED_DELIVERY"'
                        ' --output "$COMPARISON_AUDIT"')})
    return {"format": "worker-assignment-queue-proposal", "assignment_id": AID,
            "cases": cases, "comparison_audit_commands": comparisons}


if __name__ == "__main__":
    packet = build()
    (ROOT / "queue-proposal.json").write_text(json.dumps(packet, indent=2) + "\n")
    print("sixteen exact cases and thirteen comparison commands proposed")
