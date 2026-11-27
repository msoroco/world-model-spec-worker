"""Bind seven original-only delivery commands and four comparison audits."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
MANIFEST_PATH = f"work/{ASSIGNMENT}/execution-manifest.json"
CLI = ('PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m '
       'scenario_pipeline.worker_exchange --root "$LOCAL_ROOT"')
BATCH = ' --repo "$PWD" --batch full-test-delivery --db "$DB"'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    rows = []
    for number, entry in enumerate(manifest["cases"], 1):
        case = entry["case_id"]
        suffix = case.removeprefix(ASSIGNMENT + "__")
        selection = f" --assignment {ASSIGNMENT} --case {case}"
        prepare = CLI + BATCH + " prepare-delivery" + selection
        execute = (CLI + BATCH + " execute-delivery" + selection +
                   ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON"'
                   ' --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (CLI + BATCH + " accept-delivery" + selection +
                  ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT"'
                  ' --audit "$AUDIT" --review-archive /external/archive')
        post = (f'.venv-cpu/bin/python runtime.py process-saved --manifest {MANIFEST_PATH}'
                f' --case {case} --attempt "$ATTEMPT" --output "$PROCESSED"'
                ' --library runtime/library --validator "$LEAN_VALIDATOR"'
                ' --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        audit = (f'.venv-cpu/bin/python work/{ASSIGNMENT}/selected_delivery.py'
                 f' --case {case} --attempt "$PROCESSED/v0001/analysis"')
        source_log = HERE / f"cpu-saved-{suffix}.json"
        proof = json.loads(source_log.read_text())
        if proof["case_id"] != case or proof["passed"] is not True or proof["recorded_only"] is not True:
            raise ValueError("Saved-only positive proof missing: " + case)
        entry["post_capture"] = {
            "recorded_only": True, "command": post, "feedback_command": audit,
            "test_exit_code": 0, "test_log": source_log.name,
            "test_log_sha256": sha(source_log),
        }
        rows.append({
            "order": number, "assignment_id": ASSIGNMENT, "case_id": case,
            "prepare_command": prepare, "execute_command": execute,
            "accept_command": accept, "capture_command": execute,
            "postprocessing_command": post,
            "owner_release_command": (f'CASE_ID={case} .venv-cpu/bin/python runtime.py'
                                      ' owner-released --attempt "$ATTEMPT"'
                                      ' --receipt "$OWNER_RELEASE_RECEIPT"'
                                      ' --acknowledge-owner-released'),
            "additional_source_audit_command": audit,
            "candidate_commands": {candidate["id"]: prepare +
                                   f' --candidate {candidate["id"]}'
                                   for candidate in entry["candidates"]},
        })
    write(manifest_path, manifest)
    comparisons = []
    for row in plan["comparisons"]:
        comp = row["comparison_id"]
        cases = row["case_ids"]
        paths = [f'"$PROCESSED_ROOT/{case}/v0001/analysis"' for case in cases]
        if comp == "approaching_near_crossing_speed_sweep":
            if len(paths) != 3:
                raise ValueError("Speed comparison requires exact three cases")
            command = (f'.venv-cpu/bin/python work/{ASSIGNMENT}/speed_sweep_comparison.py '
                       + ' '.join(paths) + ' --output "$AUDIT"')
        else:
            if len(paths) != 2:
                raise ValueError("Selected comparison requires exact pair")
            command = (f'.venv-cpu/bin/python work/{ASSIGNMENT}/selected_comparison.py'
                       f' --comparison {comp} --left {paths[0]} --right {paths[1]}')
        comparisons.append({"assignment_id": ASSIGNMENT,
                            "comparison_id": comp, "command": command})
    proposal = {"format": "worker-ordered-gpu-queue-proposal",
                "assignment_id": ASSIGNMENT, "source": "execution-manifest.json",
                "cases": rows, "comparison_audit_commands": comparisons}
    write(HERE / "gpu-queue-proposal.json", proposal)
    print(f"Bound {len(rows)} exact delivery cases and {len(comparisons)} comparisons")


if __name__ == "__main__":
    main()
