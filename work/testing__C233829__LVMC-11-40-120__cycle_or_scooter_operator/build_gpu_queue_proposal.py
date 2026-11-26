"""Emit assignment-local exact-case queue proposal after CPU readiness."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
BATCH = 'full-test-delivery'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    if len(manifest['cases']) != 7 or len(plan['comparisons']) != 4:
        raise ValueError('selected case or comparison count incomplete')
    prefix = ('PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m '
              'scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" ')
    cases = []
    for order, entry in enumerate(manifest['cases'], 1):
        case = entry['case_id']
        common = (f'--repo "$PWD" --batch {BATCH} --db "$DB" '
                  f'--assignment {AID} --case {case}')
        prepare = prefix + 'prepare-delivery ' + common
        execute = ('SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c233829-local-capture" '
                   + prefix + 'execute-delivery ' + common +
                   ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON"'
                   ' --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = prefix + 'accept-delivery ' + common + (
            ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT"'
            ' --audit "$AUDIT" --review-archive /external/archive')
        saved = (f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/execution-manifest.json'
                 f' --case {case} --attempt "$ATTEMPT" --output "$PROCESSED"'
                 ' --library runtime/library --validator "$LEAN_VALIDATOR"'
                 ' --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        source_audit = (f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{AID}/delivery_audit.py'
                        f' --attempt "$ATTEMPT" --processed "$PROCESSED_RESULT"'
                        f' --case {case} --output "$SOURCE_AUDIT"')
        cases.append({'order': order, 'assignment_id': AID, 'case_id': case,
                      'prepare_command': prepare, 'execute_command': execute,
                      'accept_command': accept, 'capture_command': execute,
                      'postprocessing_command': saved,
                      'owner_release_command': f'CASE_ID={case} .venv-cpu/bin/python runtime.py owner-released --attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released',
                      'additional_source_audit_command': source_audit,
                      'candidate_commands': {candidate['id']: prepare + ' --candidate ' + candidate['id']
                                             for candidate in entry.get('candidates', [])}})
    comparisons = [{'assignment_id': AID, 'comparison_id': row['comparison_id'],
                    'case_ids': row['case_ids'],
                    'command': (f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{AID}/compare_saved.py'
                                f' --left "$LEFT_AUDIT" --right "$RIGHT_AUDIT" --comparison {row["comparison_id"]}'
                                ' --output "$COMPARISON_AUDIT"')}
                   for row in plan['comparisons']]
    proposal = {'format': 'worker-gpu-queue-proposal', 'assignment_id': AID,
                'selected_manifest_sha256': sha(manifest_path),
                'cases': cases, 'comparison_audit_commands': comparisons,
                'source_prerequisites': ['reviewed original municipal path designation and adjacency',
                                         'source-sealed Native roadway and adjacent path geometry with distinct rider routes',
                                         'path condition and access review source and source-hashed Native adapter',
                                         'four synchronized original cameras and 900 joined actor frames'],
                'remaining_review': ['Native rider path/roadway physical completion and actual pixels',
                                     'path usability, access and legal compliance remain unresolved']}
    (HERE / 'gpu-queue-proposal.json').write_text(json.dumps(proposal, indent=2) + '\n')


if __name__ == '__main__':
    build()
