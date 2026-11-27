"""Build exact local dispatch commands; lead integrates the shared queue."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
BATCH = 'full-test-delivery'
PREFIX = 'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" '
CAPTURE_ENV = 'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c143766-1d3-local-capture" '


def command(kind: str, cid: str, suffix: str = '') -> str:
    return (PREFIX + kind + ' --repo "$PWD" --batch ' + BATCH + ' --db "$DB" --assignment ' +
            ASSIGNMENT + ' --case ' + cid + suffix)


def build() -> None:
    plan = json.loads((HERE / 'case-plan.json').read_text())
    rows = []
    for order, case in enumerate(plan['cases'], 1):
        cid = case['case_id']
        prepare = command('prepare-delivery', cid)
        execute = CAPTURE_ENV + command('execute-delivery', cid,
            ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = command('accept-delivery', cid,
            ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT" --audit "$AUDIT" --review-archive /external/archive')
        rows.append({'order': order, 'assignment_id': ASSIGNMENT, 'case_id': cid,
            'prepare_command': prepare, 'execute_command': execute,
            'capture_command': execute, 'accept_command': accept,
            'candidate_commands': {'fallback1': command('prepare-delivery', cid, ' --candidate fallback1')},
            'owner_release_command': 'CASE_ID=' + cid +
                ' .venv-cpu/bin/python runtime.py owner-released --attempt "$SAVED_ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released',
            'postprocessing_command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' +
                ASSIGNMENT + '/execution-manifest.json --case ' + cid +
                ' --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_ROOT" --library runtime/library --validator "$LEAN_VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"',
            'additional_source_audit_command':
                'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c143766-1d3-local-audit" PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py work/' +
                ASSIGNMENT + '/delivery_audit.py --attempt "$SAVED_ATTEMPT" --case-id ' + cid + ' --output "$SOURCE_AUDIT"'})
    comparisons = [{'assignment_id': ASSIGNMENT, 'comparison_id': row['comparison_id'],
        'case_ids': row['case_ids'],
        'command': 'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c143766-1d3-local-comparison" PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py work/' +
            ASSIGNMENT + '/comparison_audit.py --comparison ' + row['comparison_id'] +
            ' --first-attempt "$FIRST_ATTEMPT" --second-attempt "$SECOND_ATTEMPT" --output "$COMPARISON_AUDIT"'}
        for row in plan['comparisons']]
    proposal = {'format': 'worker-gpu-queue-proposal', 'assignment_id': ASSIGNMENT,
        'cases': rows, 'comparison_audit_commands': comparisons,
        'source_prerequisites': [
            'Set C143766_CROSSING_REVIEW_PACKET, C143766_CROSSING_SOURCE_ROOT and C143766_CROSSING_ADAPTER_MODULE to separately reviewed original sources before execute-delivery.',
            'Original CARLA route, four-view pixels, prior lawful entry and cited exceptions remain unverified.']}
    (HERE / 'gpu-queue-proposal.json').write_text(json.dumps(proposal, indent=2, sort_keys=True) + '\n')
    print(len(rows), 'cases', len(comparisons), 'comparisons')


if __name__ == '__main__':
    build()
