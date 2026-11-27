"""Propose exact canonical dispatch rows for lead integration only."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name


def main():
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    env = 'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c233871-local" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/runtime" '
    canonical = env + '.venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" '
    common = f'--repo "$PWD" --batch full-test-delivery --db "$DB" --assignment {ASSIGNMENT}'
    rows = []
    for entry in manifest["cases"]:
        cid = entry["case_id"]
        prepare = canonical + f'prepare-delivery {common} --case {cid}'
        execute = (canonical + f'execute-delivery {common} --case {cid} --run "$RUN" --job "$JOB_ID" '
                   '--python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (canonical + f'accept-delivery {common} --case {cid} --run "$RUN" --job "$JOB_ID" '
                  '--attempt "$ATTEMPT" --audit "$AUDIT" --review-archive /external/archive')
        post = (f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{ASSIGNMENT}/execution-manifest.json '
                f'--case {cid} --attempt "$ATTEMPT" --output "$PROCESSED" --library runtime/library '
                '--validator "$LEAN_VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        audit = (f'PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/work/{ASSIGNMENT}:$PWD/runtime/scenario_pipeline" '
                 f'.venv-cpu/bin/python work/{ASSIGNMENT}/delivery_audit.py --attempt "$ATTEMPT" '
                 f'--processing "$PROCESSED/v0001/processing.json" --decode-receipt "$SOURCE_DECODE_RECEIPT" --case {cid}')
        rows.append({"assignment_id": ASSIGNMENT, "case_id": cid,
                     "prepare_command": prepare, "execute_command": execute,
                     "accept_command": accept, "capture_command": execute,
                     "postprocessing_command": post,
                     "owner_release_command": f'CASE_ID={cid} .venv-cpu/bin/python runtime.py owner-released --attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released',
                     "additional_source_audit_command": audit,
                     "candidate_commands": {candidate["id"]: prepare + f' --candidate {candidate["id"]}'
                                            for candidate in entry["candidates"]}})
    comparisons = [{"assignment_id": ASSIGNMENT,
                    "comparison_id": item["comparison_id"],
                    "case_ids": item["case_ids"],
                    "command": f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{ASSIGNMENT}/comparison_audit.py "$PROMPT_AUDIT" "$DEFERRED_AUDIT"'}
                   for item in plan["comparisons"]]
    proposal = {"assignment_id": ASSIGNMENT, "cases": rows,
                "comparison_audit_commands": comparisons}
    (ROOT / "queue-proposal.json").write_text(json.dumps(proposal, indent=2) + "\n")


if __name__ == "__main__":
    main()
