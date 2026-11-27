"""Return direct exact-case local commands without executing any GPU job."""
from __future__ import annotations

import json
from pathlib import Path

from fire_station_scene import ASSIGNMENT


ROOT = Path(__file__).resolve().parent


def main():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text(encoding='utf-8'))
    plan = json.loads((ROOT / 'case-plan.json').read_text(encoding='utf-8'))
    base = ('PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python '
            '-m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT"')
    package = 'work/' + ASSIGNMENT
    rows = []
    for entry in manifest['cases']:
        cid = entry['case_id']
        identity = (' --repo "$PWD" --batch full-test-delivery --db "$DB"' +
                    ' --assignment ' + ASSIGNMENT + ' --case ' + cid)
        prepare = base + ' prepare-delivery' + identity
        execute = (base + ' execute-delivery' + identity +
                   ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON"' +
                   ' --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (base + ' accept-delivery' + identity +
                  ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT"' +
                  ' --audit "$AUDIT" --review-archive /external/archive')
        owner_release = ('CASE_ID=' + cid +
                         ' .venv-cpu/bin/python runtime.py owner-released' +
                         ' --attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT"' +
                         ' --acknowledge-owner-released')
        process = ('.venv-cpu/bin/python runtime.py process-saved' +
                   ' --manifest ' + package + '/execution-manifest.json' +
                   ' --case ' + cid + ' --attempt "$ATTEMPT"' +
                   ' --output "$PROCESSED" --library runtime/library' +
                   ' --validator "$LEAN_VALIDATOR"' +
                   ' --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        audit = ('PYTHONPATH="$PWD/runtime/scenario_pipeline"' +
                 ' .venv-cpu/bin/python ' + package + '/queue_delivery.py' +
                 ' --attempt "$ATTEMPT" --processed-root "$PROCESSED"' +
                 ' --case ' + cid + ' --output "$SOURCE_AUDIT_OUTPUT"')
        rows.append({
            'assignment_id': ASSIGNMENT, 'case_id': cid,
            'prepare_command': prepare,
            'execute_command': execute,
            'accept_command': accept,
            'capture_command': execute,
            'owner_release_command': owner_release,
            'postprocessing_command': process,
            'additional_source_audit_command': audit,
            'candidate_commands': {
                candidate['id']: prepare + ' --candidate ' + candidate['id']
                for candidate in entry.get('candidates', [])}})
    comparisons = [{
        'assignment_id': ASSIGNMENT,
        'comparison_id': pair['comparison_id'],
        'command': ('.venv-cpu/bin/python ' + package + '/comparison_audit.py' +
                    ' --comparison ' + pair['comparison_id'] +
                    ' --left-report "$LEFT_REPORT"' +
                    ' --right-report "$RIGHT_REPORT"' +
                    ' --output "$OUTPUT"')}
        for pair in plan['comparisons']]
    (ROOT / 'gpu-queue-proposal.json').write_text(json.dumps({
        'format': 'worker-ordered-gpu-queue-proposal',
        'assignment_id': ASSIGNMENT,
        'cases': rows,
        'comparison_audit_commands': comparisons}, indent=2) + '\n',
        encoding='utf-8')


if __name__ == '__main__':
    main()
