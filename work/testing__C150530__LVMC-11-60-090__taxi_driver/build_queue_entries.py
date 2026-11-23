"""Prepare exact C150530 rows for the batch's ordered local GPU queue.

These commands are declarative. This script never executes a GPU job or edits
the shared queue while other assignments remain incomplete.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
BATCH = "full-test-delivery"
LOCAL = 'python3.11 -m scenario_pipeline.worker_exchange --project "$PROJECT" --root "$LOCAL_ROOT"'
BASE = ' --repo "$WORKER_REPO" --batch ' + BATCH + ' --db "$DB" --assignment ' + ASSIGNMENT


def build() -> dict:
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    expected = {item["case_id"] for item in plan["cases"]}
    actual = [item["case_id"] for item in manifest["cases"]]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("exact taxi queue case coverage differs")
    rows = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(ASSIGNMENT + "__")
        if suffix == case or not entry.get("delivery_acceptance"):
            raise ValueError("missing exact delivery contract: " + case)
        execute = (LOCAL + " execute-delivery" + BASE + ' --run "$RUN" --case ' + case +
                   ' --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"')
        row = {
            "assignment_id": ASSIGNMENT, "case_id": case,
            "prepare_command": LOCAL + " prepare-delivery" + BASE + " --case " + case,
            "execute_command": execute,
            "capture_command": execute,
            "owner_release_command": ('CASE_ID=' + case +
                                      ' PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py owner-released'
                                      ' --attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT"'
                                      ' --acknowledge-owner-released'),
            "postprocessing_command": ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved'
                                       ' --manifest work/' + ASSIGNMENT + '/execution-manifest.json --case ' + case +
                                       ' --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" --library "$LIBRARY"'
                                       ' --validator "$VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"'),
            "additional_source_audit_command": ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' +
                                                ASSIGNMENT + '/independent/delivery_audit.py --case ' + suffix +
                                                ' --case-id ' + case +
                                                ' --attempt "$ATTEMPT" --map "$MAP" --layout "$LAYOUT"'
                                                ' --composition-receipt "$COMPOSITION_RECEIPT"'
                                                ' --decode-receipt "$DECODE_RECEIPT" --media-auditor "$MEDIA_AUDITOR"'
                                                ' --physical-receipt "$PHYSICAL_RECEIPT" --pixel-review "$PIXEL_REVIEW"'
                                                ' --job-id "$JOB_ID" --attempt-number "$ATTEMPT_NUMBER"'
                                                ' --recording-id "$RECORDING_ID" --output "$AUDIT"'),
            "accept_command": (LOCAL + " accept-delivery" + BASE + ' --run "$RUN" --case ' + case +
                               ' --job "$JOB_ID" --attempt "$ATTEMPT_NUMBER" --audit "$AUDIT"'
                               ' --review-archive /external/archive'),
            "candidate_commands": {candidate["id"]: LOCAL + " prepare-delivery" + BASE +
                                   " --case " + case + " --candidate " + candidate["id"]
                                   for candidate in entry.get("candidates", [])},
        }
        rows.append(row)
    comparisons = []
    for item in plan["comparisons"]:
        cid = item["comparison_id"]
        if cid == "stand_to_first_intersection_distance":
            command = ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' + ASSIGNMENT +
                       '/measured_comparison_audit.py --near-attempt "$NEAR_ATTEMPT"'
                       ' --far-attempt "$FAR_ATTEMPT" --output "$COMPARISON_AUDIT"')
        elif cid == "posted_right_turn_vs_straight_attempt":
            command = ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' + ASSIGNMENT +
                       '/turn_pair_audit.py --right-attempt "$RIGHT_ATTEMPT"'
                       ' --straight-attempt "$STRAIGHT_ATTEMPT" --output "$COMPARISON_AUDIT"')
        else:
            raise ValueError("unknown exact comparison: " + cid)
        comparisons.append({"assignment_id": ASSIGNMENT, "comparison_id": cid,
                            "command": command})
    return {"format": "worker-assignment-queue-entries-partial",
            "assignment_id": ASSIGNMENT, "cases": rows,
            "comparison_audit_commands": comparisons,
            "batch_queue_complete": False}


def main() -> None:
    result = build()
    (ROOT / "queue-entries.partial.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"{ASSIGNMENT}: {len(result['cases'])} exact dispatch rows, "
          f"{len(result['comparison_audit_commands'])} comparison audits prepared; "
          "batch queue remains partial")


if __name__ == "__main__":
    main()
