"""Draft exact local GPU and comparison commands for root queue integration."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
MANIFEST = HERE / 'execution-manifest.json'
OUTPUT = HERE / 'gpu-queue-proposal.json'
PREFIX = 'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" '
BASE = '--repo "$PWD" --batch full-test-delivery --db "$DB" '


def build() -> dict:
    manifest = json.loads(MANIFEST.read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    rows = []
    for order, entry in enumerate(manifest['cases'], 1):
        case_id = entry['case_id']
        identity = '--assignment ' + ASSIGNMENT + ' --case ' + case_id
        prepare = PREFIX + 'prepare-delivery ' + BASE + identity
        execute = (PREFIX + 'execute-delivery ' + BASE + '--run "$RUN" ' + identity +
                   ' --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"')
        source_env = ('C150153_REVIEWED_SITE_PACKET="$REVIEWED_SITE_PACKET" '
                      'C150153_ORIGINAL_SOURCE_ROOT="$REVIEWED_SOURCE_ROOT" '
                      'C150153_NATIVE_ADAPTER_MODULE="$NATIVE_ADAPTER_MODULE" ')
        capture = source_env + execute
        accept = (PREFIX + 'accept-delivery ' + BASE + '--run "$RUN" ' + identity +
                  ' --job "$JOB_ID" --attempt "$ATTEMPT" --audit "$AUDIT" '
                  '--review-archive /external/archive')
        candidates = {candidate['id']: prepare + ' --candidate ' + candidate['id']
                      for candidate in entry['candidates']}
        audit = ('.venv-cpu/bin/python work/' + ASSIGNMENT + '/delivery_audit.py'
                 ' --case ' + case_id + ' --attempt "$ATTEMPT"'
                 ' --packet "$REVIEWED_SITE_PACKET" --source-root "$REVIEWED_SOURCE_ROOT"'
                 ' --output "$AUDIT"')
        owner = ('CASE_ID=' + case_id + ' .venv-cpu/bin/python runtime.py owner-released'
                 ' --attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT"'
                 ' --acknowledge-owner-released')
        saved = ('.venv-cpu/bin/python runtime.py process-saved --manifest work/' + ASSIGNMENT +
                 '/execution-manifest.json --case ' + case_id +
                 ' --attempt "$ATTEMPT" --output "$PROCESSED" --library runtime/library'
                 ' --validator "$LEAN_VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        rows.append({'order': order, 'assignment_id': ASSIGNMENT, 'case_id': case_id,
                     'prepare_command': prepare, 'execute_command': execute,
                     'capture_command': capture, 'candidate_commands': candidates,
                     'owner_release_command': owner, 'postprocessing_command': saved,
                     'additional_source_audit_command': audit, 'accept_command': accept})
    comparisons = []
    for comparison in plan['comparisons']:
        comparison_id = comparison['comparison_id']
        command = ('.venv-cpu/bin/python work/' + ASSIGNMENT + '/comparison_audit.py'
                   ' --comparison-id ' + comparison_id +
                   ' --left "$LEFT_ATTEMPT" --right "$RIGHT_ATTEMPT"'
                   ' --site-packet "$REVIEWED_SITE_PACKET"'
                   ' --source-root "$REVIEWED_SOURCE_ROOT"'
                   ' --output "$COMPARISON_AUDIT"')
        comparisons.append({'assignment_id': ASSIGNMENT,
                            'comparison_id': comparison_id, 'command': command})
    proposal = {'format': 'c150153-exact-queue-proposal',
                'status': 'pending_root_queue_and_original_sources',
                'assignment_id': ASSIGNMENT,
                'source_inputs': ['REVIEWED_SITE_PACKET', 'REVIEWED_SOURCE_ROOT',
                                  'NATIVE_ADAPTER_MODULE'],
                'cases': rows, 'comparison_audit_commands': comparisons}
    OUTPUT.write_text(json.dumps(proposal, indent=2) + '\n')
    return proposal


if __name__ == '__main__':
    proposal = build()
    print(len(proposal['cases']), 'cases and',
          len(proposal['comparison_audit_commands']), 'comparison commands drafted')
