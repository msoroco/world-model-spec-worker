"""Read selected manifest and propose exact local GPU handoff commands."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
PREFIX = ('PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m '
          'scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" ')
COMMON = (' --repo "$PWD" --batch full-test-delivery --db "$DB" '
          '--assignment ' + AID + ' --case ')


def main():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    rows = []
    for entry in manifest['cases']:
        case = entry['case_id']
        prepare = PREFIX + 'prepare-delivery' + COMMON + case
        execute = (PREFIX + 'execute-delivery' + COMMON + case +
                   ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON"'
                   ' --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (PREFIX + 'accept-delivery' + COMMON + case +
                  ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT_NUMBER"'
                  ' --audit "$AUDIT" --review-archive "$REVIEW_ARCHIVE"')
        process = ('.venv-cpu/bin/python runtime.py process-saved --manifest work/' +
                   AID + '/execution-manifest.json --case ' + case +
                   ' --attempt "$SAVED_ATTEMPT" --output "$PROCESSED"'
                   ' --library runtime/library --validator "$LEAN_VALIDATOR"'
                   ' --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        release = ('CASE_ID=' + case + ' .venv-cpu/bin/python runtime.py owner-released --attempt '
                   '"$SAVED_ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT"'
                   ' --acknowledge-owner-released')
        audit = ('PYTHONPATH="$PWD/runtime/scenario_pipeline" .venv-cpu/bin/python '
                 'work/' + AID + '/delivery_audit.py --case ' + case +
                 ' --attempt "$SAVED_ATTEMPT" --processing "$SAVED_PROCESSING_RECEIPT"'
                 ' --review "$SOURCE_REVIEW" --pixel-review "$PIXEL_REVIEW"'
                 ' --video "$FINAL_VIDEO_RELATIVE" --trace "$CORE_TRACE_RELATIVE"'
                 ' --decode-receipt "$DECODE_RECEIPT" --auditor work/' + AID +
                 '/delivery_audit.py --job "$JOB_ID" --attempt-number '
                 '"$ATTEMPT_NUMBER" --recording-id "$RECORDING_ID"'
                 ' --output "$SOURCE_AUDIT_OUTPUT"')
        rows.append({'assignment_id': AID, 'case_id': case,
                     'prepare_command': prepare, 'execute_command': execute,
                     'accept_command': accept, 'capture_command': execute,
                     'owner_release_command': release,
                     'postprocessing_command': process,
                     'additional_source_audit_command': audit,
                     'candidate_commands': {c['id']: prepare + ' --candidate ' + c['id']
                                            for c in entry['candidates']}})
    comparisons = []
    for item in plan['comparisons']:
        comparisons.append({'assignment_id': AID,
                            'comparison_id': item['comparison_id'],
                            'case_ids': item['case_ids'],
                            'command': ('.venv-cpu/bin/python work/' + AID +
                                        '/comparison_audit.py --comparison ' +
                                        item['comparison_id'] + ' --left "$LEFT_REPORT"'
                                        ' --right "$RIGHT_REPORT" --output "$OUTPUT"')})
    value = {'format': 'worker-gpu-queue-proposal', 'assignment_id': AID,
             'status': 'ready_for_local_original_checks', 'cases': rows,
             'comparison_audit_commands': comparisons}
    (ROOT / 'gpu-queue-proposal.json').write_text(json.dumps(value, indent=2) + '\n')


if __name__ == '__main__':
    main()
