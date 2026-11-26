"""Create exact-case queue rows for lead integration after scoped strict proof."""
import json
from pathlib import Path

from native_packet import AID

HERE = Path(__file__).resolve().parent


def build():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    prefix = ('PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m '
              'scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" ')
    common = ' --repo "$PWD" --batch full-test-delivery --db "$DB" --assignment ' + AID
    rows = []
    for order, entry in enumerate(manifest['cases'], 1):
        case_id = entry['case_id']
        selected = common + ' --case ' + case_id
        prepare = prefix + 'prepare-delivery' + selected
        execute = (prefix + 'execute-delivery' + selected
                   + ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON"'
                   + ' --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (prefix + 'accept-delivery' + selected
                  + ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT"'
                  + ' --audit "$AUDIT" --review-archive /external/archive')
        rows.append({'order': order, 'assignment_id': AID, 'case_id': case_id,
                     'prepare_command': prepare, 'execute_command': execute,
                     'accept_command': accept, 'capture_command': execute,
                     'postprocessing_command': entry['post_capture']['command'],
                     'owner_release_command': 'CASE_ID=' + case_id
                     + ' .venv-cpu/bin/python runtime.py owner-released --attempt'
                       ' "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT"'
                       ' --acknowledge-owner-released',
                     'additional_source_audit_command':
                     'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c149752-gpu-audit"'
                     ' TMPDIR="$PWD/.runtime-work/c149752-gpu-audit"'
                     ' PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' + AID
                     + '/delivery_audit.py --case ' + case_id
                     + ' --attempt "$ATTEMPT" --processed "$PROCESSED"'
                       ' --output "$AUDIT"',
                     'candidate_commands': {candidate['id']: prepare
                                            + ' --candidate ' + candidate['id']
                                            for candidate in entry.get('candidates', [])}})
    comparisons = [{'assignment_id': AID, 'comparison_id': item['comparison_id'],
                    'command': 'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c149752-gpu-audit"'
                    ' TMPDIR="$PWD/.runtime-work/c149752-gpu-audit"'
                    ' PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' + AID
                    + '/comparison_audit.py --comparison ' + item['comparison_id']
                    + ' --report "$REPORT_A" --report "$REPORT_B"'
                      ' --output "$COMPARISON_AUDIT"',
                    'record_requirement': 'Independent sealed original Native reports'}
                   for item in plan['comparisons']]
    proposal = {'format': 'worker-ordered-gpu-queue-proposal', 'assignment_id': AID,
                'source': 'execution-manifest.json', 'cases': rows,
                'comparison_audit_commands': comparisons}
    (HERE / 'gpu-queue-proposal.json').write_text(json.dumps(proposal, indent=2) + '\n')
    print(len(rows), 'cases and', len(comparisons), 'comparisons proposed')


if __name__ == '__main__':
    build()
