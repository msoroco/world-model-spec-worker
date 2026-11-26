"""Prepare canonical local delivery commands for selected bus/device cases."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
PREFIX = ('python3.11 -m scenario_pipeline.worker_exchange --project "$PROJECT" '
          '--root "$LOCAL_ROOT" ')
BASE = (' --repo "$WORKER_REPO" --batch full-test-delivery --db "$DB" '
        '--assignment ' + AID)


def main():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    if [row['case_id'] for row in manifest['cases']] != [row['case_id'] for row in plan['cases']]:
        raise ValueError('selected case order differs from exact plan')
    rows = []
    for order, entry in enumerate(manifest['cases'], 1):
        cid = entry['case_id']
        prepare = PREFIX + 'prepare-delivery' + BASE + ' --case ' + cid
        execute = (PREFIX + 'execute-delivery' + BASE + ' --run "$RUN" --case ' + cid +
                   ' --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" '
                   '--port "$CARLA_PORT"')
        rows.append({'order': order, 'assignment_id': AID, 'case_id': cid,
            'prepare_command': prepare,
            'candidate_commands': {item['id']: prepare + ' --candidate ' + item['id']
                                   for item in entry.get('candidates', [])},
            'execute_command': execute, 'capture_command': execute,
            'owner_release_command': ('CASE_ID=' + cid + ' PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python '
                'runtime.py owner-released --attempt "$ATTEMPT" '
                '--receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released'),
            'postprocessing_command': ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python '
                'runtime.py process-saved --manifest work/' + AID + '/execution-manifest.json '
                '--case ' + cid + ' --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" '
                '--library "$LIBRARY" --validator "$VALIDATOR" '
                '--owner-release-receipt "$OWNER_RELEASE_RECEIPT"'),
            'additional_source_audit_command': ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python '
                'work/' + AID + '/selected_delivery.py --attempt "$ATTEMPT" --case ' +
                cid + ' > "$AUDIT"'),
            'accept_command': (PREFIX + 'accept-delivery' + BASE + ' --run "$RUN" --case ' +
                cid + ' --job "$JOB_ID" --attempt "$ATTEMPT_NUMBER" --audit "$AUDIT" '
                '--review-archive /external/archive')})
    comparisons = [{'assignment_id': AID, 'comparison_id': pair['comparison_id'],
                    'case_ids': pair['case_ids'],
                    'command': ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' +
                        AID + '/selected_comparison.py --comparison ' + pair['comparison_id'] +
                        ' --left "$BASELINE_ATTEMPT" --right "$CHANGED_ATTEMPT" '
                        '> "$COMPARISON_AUDIT"')}
                   for pair in plan['comparisons']]
    proposal = {'format': 'worker-assignment-queue-proposal', 'assignment_id': AID,
                'cases': rows, 'comparison_audit_commands': comparisons}
    (HERE / 'queue-proposal.json').write_text(json.dumps(proposal, indent=2) + '\n')
    print('queue proposal:', len(rows), 'cases,', len(comparisons), 'comparisons')


if __name__ == '__main__':
    main()
