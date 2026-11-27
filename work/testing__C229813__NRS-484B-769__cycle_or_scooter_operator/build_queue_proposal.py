"""Write the exact original-acquisition queue proposal for this assignment."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
PACKAGE = f"work/{ASSIGNMENT}"
PREFIX = 'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT"'
AUDIT_ENV = ('SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c229813-owner/gpu-audit" '
             'TMPDIR="$PWD/.runtime-work/c229813-owner/gpu-audit" PYTHONDONTWRITEBYTECODE=1 ')


def main():
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    rows = []
    for order, case in enumerate(manifest["cases"], 1):
        case_id = case["case_id"]
        common = (f'--repo "$PWD" --batch full-test-delivery --db "$DB" '
                  f'--assignment {ASSIGNMENT} --case {case_id}')
        prepare = f"{PREFIX} prepare-delivery {common}"
        execute = (f'{PREFIX} execute-delivery {common} --run "$RUN" --job "$JOB_ID" '
                   '--python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (f'{PREFIX} accept-delivery {common} --run "$RUN" --job "$JOB_ID" '
                  '--attempt "$ATTEMPT" --audit "$AUDIT" --review-archive /external/archive')
        rows.append({
            "order": order, "assignment_id": ASSIGNMENT, "case_id": case_id,
            "prepare_command": prepare, "execute_command": execute,
            "accept_command": accept, "capture_command": execute,
            "postprocessing_command": (
                f'.venv-cpu/bin/python runtime.py process-saved --manifest {PACKAGE}/execution-manifest.json '
                f'--case {case_id} --attempt "$ATTEMPT" --output "$PROCESSED" '
                '--library runtime/library --validator "$LEAN_VALIDATOR" '
                '--owner-release-receipt "$OWNER_RELEASE_RECEIPT"'),
            "owner_release_command": (
                f'CASE_ID={case_id} .venv-cpu/bin/python runtime.py owner-released '
                '--attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT" '
                '--acknowledge-owner-released'),
            "additional_source_audit_command": (
                f'{AUDIT_ENV}.venv-cpu/bin/python {PACKAGE}/delivery_audit.py '
                f'--case {case_id} --attempt "$ATTEMPT" --review "$PIXEL_REVIEW"'),
            "candidate_commands": {
                candidate["id"]: prepare + f' --candidate {candidate["id"]}'
                for candidate in case["candidates"]},
        })
    comparisons = []
    for comparison in plan["comparisons"]:
        comparison_id = comparison["comparison_id"]
        comparisons.append({
            "assignment_id": ASSIGNMENT, "comparison_id": comparison_id,
            "case_ids": comparison["case_ids"],
            "command": (f'{AUDIT_ENV}.venv-cpu/bin/python {PACKAGE}/compare_saved.py '
                        f'--comparison {comparison_id} '
                        '--attempt "$ATTEMPT_A" --attempt "$ATTEMPT_B" --attempt "$ATTEMPT_C"'),
            "record_requirement": "Three separately reviewed original saved acquisitions in listed case order",
        })
    proposal = {"format": "worker-ordered-gpu-queue-proposal",
                "assignment_id": ASSIGNMENT, "source": "execution-manifest.json",
                "cases": rows, "comparison_audit_commands": comparisons}
    (ROOT / "gpu-queue-proposal.json").write_text(json.dumps(proposal, indent=2) + "\n")
    print(f"proposed {len(rows)} cases and {len(comparisons)} comparisons")


if __name__ == "__main__":
    main()
