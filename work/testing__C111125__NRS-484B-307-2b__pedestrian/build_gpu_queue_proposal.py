"""Build exact local dispatch rows for lead integration into the shared queue."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
PREFIX = 'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" '
COMMON = '--repo "$PWD" --batch full-test-delivery --db "$DB" --assignment ' + ASSIGNMENT
SITE = ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python '
        f'work/{ASSIGNMENT}/reviewed_site_preflight.py '
        '--site "$SCENARIO_REVIEWED_SITE_PACKET" --case {case_id} && ')


def build() -> dict:
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    entries = {item['case_id']: item for item in manifest['cases']}
    rows = []
    for order, item in enumerate(plan['cases'], start=1):
        case_id = item['case_id']
        suffix = case_id.removeprefix(ASSIGNMENT + '__')
        identity = COMMON + ' --case ' + case_id
        prepare = PREFIX + 'prepare-delivery ' + identity
        execute = (SITE.format(case_id=case_id) + 'SCENARIO_REVIEWED_SITE_PACKET="$SCENARIO_REVIEWED_SITE_PACKET" '
                   'SCENARIO_PEDESTRIAN_OPERATOR_ADAPTER="$SCENARIO_PEDESTRIAN_OPERATOR_ADAPTER" '
                   + PREFIX + 'execute-delivery ' + identity
                   + ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON"'
                   + ' --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (PREFIX + 'accept-delivery ' + identity
                  + ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT"'
                  + ' --audit "$AUDIT" --review-archive /external/archive')
        row = {
            'order': order, 'assignment_id': ASSIGNMENT, 'case_id': case_id,
            'prepare_command': prepare, 'execute_command': execute,
            'capture_command': execute, 'accept_command': accept,
            'postprocessing_command': (
                '.venv-cpu/bin/python runtime.py process-saved --manifest '
                f'work/{ASSIGNMENT}/execution-manifest.json --case {case_id}'
                ' --attempt "$ATTEMPT" --output "$PROCESSED" --library runtime/library'
                ' --validator "$LEAN_VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"'),
            'owner_release_command': (
                f'CASE_ID={case_id} .venv-cpu/bin/python runtime.py owner-released'
                ' --attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT"'
                ' --acknowledge-owner-released'),
            'additional_source_audit_command': (
                'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python '
                f'work/{ASSIGNMENT}/production_delivery_audit.py'
                f' --case {case_id} --attempt "$ATTEMPT"'),
            'candidate_commands': {
                candidate['id']: prepare + ' --candidate ' + candidate['id']
                for candidate in entries[case_id].get('candidates', [])
            },
        }
        rows.append(row)
    pairs = [{
        'assignment_id': ASSIGNMENT,
        'comparison_id': comparison['comparison_id'],
        'case_ids': comparison['case_ids'],
        'command': ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python '
                    f'work/{ASSIGNMENT}/production_comparison_audit.py'
                    ' --comparison ' + comparison['comparison_id']
                    + ' --left "$LEFT_ATTEMPT" --right "$RIGHT_ATTEMPT"'),
    } for comparison in plan['comparisons']]
    return {'format': 'worker-gpu-queue-proposal', 'assignment_id': ASSIGNMENT,
            'cases': rows, 'comparison_audit_commands': pairs}


def main() -> None:
    value = build()
    (ROOT / 'gpu-queue-proposal.json').write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    print(len(value['cases']), len(value['comparison_audit_commands']))


if __name__ == '__main__':
    main()
