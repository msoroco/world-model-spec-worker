"""Propose ordered local Native jobs and source-bound follow-on audits."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
PREFIX = 'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" '
BASE = '--repo "$PWD" --batch full-test-delivery --db "$DB" --assignment ' + AID


def main():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    rows = []
    for entry in manifest['cases']:
        case_id = entry['case_id']
        case = ' --case ' + case_id
        prepare = PREFIX + 'prepare-delivery ' + BASE + case
        execute = (PREFIX + 'execute-delivery ' + BASE + case +
                   ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON"' +
                   ' --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (PREFIX + 'accept-delivery ' + BASE + case +
                  ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT"' +
                  ' --audit "$AUDIT" --review-archive /external/archive')
        rows.append({
            'assignment_id': AID, 'case_id': case_id,
            'prepare_command': prepare, 'execute_command': execute,
            'accept_command': accept, 'capture_command': execute,
            'owner_release_command': 'CASE_ID=' + case_id +
                ' .venv-cpu/bin/python runtime.py owner-released --attempt "$ATTEMPT"' +
                ' --receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released',
            'postprocessing_command': entry['post_capture']['command'],
            'additional_source_audit_command':
                'PYTHONPATH="$PWD/runtime/scenario_pipeline" .venv-cpu/bin/python work/' +
                AID + '/queue_delivery.py --attempt "$ATTEMPT"' +
                ' --processed-root "$PROCESSED" --case ' + case_id +
                ' --output "$SOURCE_AUDIT_OUTPUT"',
            'candidate_commands': {candidate['id']: prepare + ' --candidate ' + candidate['id']
                                   for candidate in entry.get('candidates', [])}})
    comparisons = [{
        'assignment_id': AID, 'comparison_id': comparison['comparison_id'],
        'command': '.venv-cpu/bin/python work/' + AID +
            '/comparison_audit.py --comparison ' + comparison['comparison_id'] +
            ' --report-map "$REPORT_MAP" --output "$OUTPUT"'}
        for comparison in plan['comparisons']]
    proposal = {'format': 'worker-ordered-gpu-queue-proposal',
                'assignment_id': AID, 'cases': rows,
                'comparison_audit_commands': comparisons}
    (ROOT / 'gpu-queue-proposal.json').write_text(json.dumps(proposal, indent=2) + '\n')


if __name__ == '__main__':
    main()
