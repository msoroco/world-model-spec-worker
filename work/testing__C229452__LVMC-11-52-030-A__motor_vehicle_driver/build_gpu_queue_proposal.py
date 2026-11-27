"""Propose every exact red-curb delivery and comparison command for lead integration."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
BASE = 'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT"'
ORIGINAL = f'.venv-cpu/bin/python work/{ASSIGNMENT}/queue_original.py'


def main():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    cases = []
    for entry in manifest['cases']:
        case = entry['case_id']
        identity = (f'--repo "$PWD" --batch full-test-delivery --db "$DB" '
                    f'--assignment {ASSIGNMENT} --case {case} --run "$RUN" --job "$JOB_ID"')
        prepare = f'{BASE} prepare-delivery {identity}'
        execute = (f'{BASE} execute-delivery {identity} --python "$CARLA_PYTHON" '
                   '--host "$CARLA_HOST" --port "$CARLA_PORT"')
        cases.append({
            'assignment_id': ASSIGNMENT, 'case_id': case,
            'prepare_command': prepare,
            'execute_command': execute,
            'accept_command': (f'{BASE} accept-delivery {identity} --attempt "$ATTEMPT" '
                               '--audit "$AUDIT" --review-archive /external/archive'),
            'capture_command': execute,
            'postprocessing_command': (f'.venv-cpu/bin/python runtime.py process-saved '
                                       f'--manifest work/{ASSIGNMENT}/execution-manifest.json '
                                       f'--case {case} --attempt "$ATTEMPT" --output "$PROCESSED" '
                                       '--library runtime/library --validator "$LEAN_VALIDATOR" '
                                       '--owner-release-receipt "$OWNER_RELEASE_RECEIPT"'),
            'owner_release_command': (f'CASE_ID={case} .venv-cpu/bin/python runtime.py owner-released '
                                      '--attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT" '
                                      '--acknowledge-owner-released'),
            'additional_source_audit_command': (f'{ORIGINAL} source --attempt "$ATTEMPT" '
                                                f'--case {case} --output "$SOURCE_AUDIT_OUTPUT"'),
            'candidate_commands': {candidate['id']: prepare + ' --candidate ' + candidate['id']
                                   for candidate in entry['candidates']}})
    comparisons = [{
        'assignment_id': ASSIGNMENT, 'comparison_id': item['comparison_id'],
        'case_ids': item['case_ids'],
        'command': (f'{ORIGINAL} comparison --comparison {item["comparison_id"]} '
                    '--left "$LEFT_ATTEMPT" --right "$RIGHT_ATTEMPT" --output "$OUTPUT"')}
        for item in plan['comparisons']]
    proposal = {'format': 'worker-gpu-queue-proposal', 'assignment_id': ASSIGNMENT,
                'cases': cases, 'comparison_audit_commands': comparisons,
                'scope': 'exact-case commands for lead integration; no Native/GPU result claimed'}
    (ROOT / 'gpu-queue-proposal.json').write_text(json.dumps(proposal, indent=2) + '\n')


if __name__ == '__main__':
    main()
