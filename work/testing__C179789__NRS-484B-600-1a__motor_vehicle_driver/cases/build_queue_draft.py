"""Prepare exact local dispatch commands without changing the shared ready queue."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name


def build():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    relative = ROOT.relative_to(REPO).as_posix()
    rows = []
    for entry in manifest['cases']:
        case = entry['case_id']
        canonical = ('PYTHONPATH=runtime/scenario_pipeline $CARLA_PYTHON -m worker_exchange '
                     '--repo . --batch batch.json --db $DB --assignment ' + ASSIGNMENT +
                     ' --case ' + case)
        rows.append({
            'assignment_id': ASSIGNMENT, 'case_id': case,
            'prepare_command': canonical.replace('-m worker_exchange ', '-m worker_exchange prepare-delivery '),
            'execute_command': canonical.replace('-m worker_exchange ', '-m worker_exchange execute-delivery ') +
                               ' --run $RUN --job $JOB_ID --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT',
            'accept_command': canonical.replace('-m worker_exchange ', '-m worker_exchange accept-delivery ') +
                              ' --run $RUN --job $JOB_ID --attempt $ATTEMPT --audit $AUDIT --review-archive /external/archive',
            'capture_command': '$CARLA_PYTHON runtime.py capture --manifest ' + relative +
                               '/execution-manifest.json --case ' + case +
                               ' --output $ATTEMPT --host $CARLA_HOST --port $CARLA_PORT --python $CARLA_PYTHON',
            'postprocessing_command': '.venv-cpu/bin/python runtime.py process-saved --manifest ' +
                                      relative + '/execution-manifest.json --case ' + case +
                                      ' --attempt $ATTEMPT --output $OUTPUT --library runtime/library '
                                      '--validator $VALIDATOR --owner-release-receipt $ATTEMPT/owner-release.json',
            'owner_release_command': 'SCENARIO_CASE_ID=' + case +
                                     ' .venv-cpu/bin/python runtime.py owner-released --attempt $ATTEMPT '
                                     '--receipt $ATTEMPT/owner-release.json --acknowledge-owner-released',
            'additional_source_audit_command': 'SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c179789-native-audit '
                                               '.venv-cpu/bin/python ' + relative +
                                               '/delivery_acceptance.py --case ' + case +
                                               ' --attempt $ATTEMPT --pixel-review $PIXEL_REVIEW --output $AUDIT',
            'candidate_commands': {candidate['id']: canonical.replace('-m worker_exchange ',
                                '-m worker_exchange prepare-delivery ') + ' --candidate ' + candidate['id']
                                   for candidate in entry.get('candidates', [])}})
    comparisons = [{'assignment_id': ASSIGNMENT, 'comparison_id': item['comparison_id'],
                    'command': '.venv-cpu/bin/python ' + relative + '/delivery_audit.py '
                               '--dry $DRY --wet $WET --dense $DENSE --narrow $NARROW '
                               '--low $LOW --ice $ICE --dry4 $DRY4 --dry6 $DRY6'}
                   for item in plan['comparisons']]
    output = {'format': 'worker-c179789-queue-draft', 'cases': rows,
              'comparison_audit_commands': comparisons,
              'integrate_only_after_strict_assignment_gate': True}
    path = ROOT / 'cases/queue-draft.json'
    path.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'cases': len(rows), 'comparisons': len(comparisons)}))


if __name__ == '__main__':
    build()
