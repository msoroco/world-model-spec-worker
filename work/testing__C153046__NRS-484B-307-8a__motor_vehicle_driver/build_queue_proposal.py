"""Prepare assignment-local local-delivery commands for the exact selected grid."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
PREFIX = ('python3.11 -m scenario_pipeline.worker_exchange --project "$PROJECT" '
          '--root "$LOCAL_ROOT" ')
BASE = (' --repo "$WORKER_REPO" --batch full-test-delivery --db "$DB" '
        '--assignment ' + AID)


def main() -> None:
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    ids = [row['case_id'] for row in manifest['cases']]
    if ids != [row['case_id'] for row in plan['cases']]:
        raise ValueError('selected manifest and plan case order differ')
    rows = []
    for order, entry in enumerate(manifest['cases'], 1):
        case = entry['case_id']
        prepare = PREFIX + 'prepare-delivery' + BASE + ' --case ' + case
        execute = (PREFIX + 'execute-delivery' + BASE + ' --run "$RUN" --case ' + case +
                   ' --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" '
                   '--port "$CARLA_PORT"')
        rows.append({
            'order': order, 'assignment_id': AID, 'case_id': case,
            'prepare_command': prepare,
            'candidate_commands': {candidate['id']: prepare + ' --candidate ' + candidate['id']
                                   for candidate in entry['candidates']},
            'execute_command': execute, 'capture_command': execute,
            'owner_release_command': ('CASE_ID=' + case + ' PYTHONDONTWRITEBYTECODE=1 '
                '.venv-cpu/bin/python runtime.py owner-released --attempt "$ATTEMPT" '
                '--receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released'),
            'postprocessing_command': ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python '
                'runtime.py process-saved --manifest work/' + AID + '/execution-manifest.json '
                '--case ' + case + ' --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" '
                '--library "$LIBRARY" --validator "$VALIDATOR" '
                '--owner-release-receipt "$OWNER_RELEASE_RECEIPT"'),
            'additional_source_audit_command': ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python '
                'work/' + AID + '/selected_delivery.py --attempt "$SAVED_OUTPUT/v0001/analysis" --case ' +
                case + ' > "$AUDIT"'),
            'accept_command': (PREFIX + 'accept-delivery' + BASE + ' --run "$RUN" --case ' +
                case + ' --job "$JOB_ID" --attempt "$ATTEMPT_NUMBER" --audit "$AUDIT" '
                '--review-archive /external/archive')})
    comparisons = [{
        'assignment_id': AID, 'comparison_id': pair['comparison_id'],
        'case_ids': pair['case_ids'],
        'command': ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' + AID +
                    '/selected_comparison.py --comparison ' + pair['comparison_id'] +
                    ' --left "$BASELINE_ATTEMPT" --right "$CHANGED_ATTEMPT" '
                    '> "$COMPARISON_AUDIT"')}
        for pair in plan['comparisons']]
    proposal = {'format': 'worker-assignment-queue-proposal', 'assignment_id': AID,
                'cases': rows, 'comparison_audit_commands': comparisons}
    (ROOT / 'queue-proposal.json').write_text(json.dumps(proposal, indent=2) + '\n')
    print('queue proposal:', len(rows), 'cases,', len(comparisons), 'comparisons')


if __name__ == '__main__':
    main()
