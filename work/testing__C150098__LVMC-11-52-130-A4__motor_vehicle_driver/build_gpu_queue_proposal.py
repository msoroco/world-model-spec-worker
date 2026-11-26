"""Emit assignment-local exact hydrant delivery queue intent."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    comparisons = json.loads((HERE / 'comparison-audit-plan.json').read_text())
    if len(manifest['cases']) != 11 or len(plan['comparisons']) != 4:
        raise ValueError('exact hydrant queue coverage incomplete')
    prefix = ('PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m '
              'scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" ')
    cases = []
    for order, entry in enumerate(manifest['cases'], 1):
        case = entry['case_id']
        common = ('--repo "$PWD" --batch full-test-delivery --db "$DB" '
                  f'--assignment {AID} --case {case}')
        prepare = prefix + 'prepare-delivery ' + common
        execute = ('SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c150098-local-capture" '
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
        audit = (f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{AID}/delivery_audit.py'
                 f' --attempt "$ATTEMPT" --processed "$PROCESSED_RESULT"'
                 f' --case {case} --output "$SOURCE_AUDIT"')
        cases.append({'order': order, 'assignment_id': AID, 'case_id': case,
            'prepare_command': prepare, 'execute_command': execute,
            'accept_command': accept, 'capture_command': execute,
            'postprocessing_command': saved,
            'owner_release_command': (f'CASE_ID={case} .venv-cpu/bin/python runtime.py owner-released'
                                      ' --attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT"'
                                      ' --acknowledge-owner-released'),
            'additional_source_audit_command': audit,
            'candidate_commands': {candidate['id']: prepare + ' --candidate ' + candidate['id']
                                   for candidate in entry.get('candidates', [])}})
    proposal = {'format': 'worker-gpu-queue-proposal', 'assignment_id': AID,
        'selected_manifest_sha256': sha(manifest_path), 'cases': cases,
        'comparison_audit_commands': [{'assignment_id': AID,
            'comparison_id': row['comparison_id'], 'case_ids': row['case_ids'],
            'command': row['command']} for row in comparisons['comparisons']],
        'source_prerequisites': ['reviewed original municipal parallel-parking authority',
            'physical hydrant identity, geometry, blueprint and curb source',
            'source-hashed Native map, four reviewed camera poses and adapter',
            'exception source for traffic conflict, police or device cases'],
        'remaining_review': ['Native physical placement, target activity and actual pixels',
            'legal distance convention and exception necessity remain unresolved']}
    (HERE / 'gpu-queue-proposal.json').write_text(json.dumps(proposal, indent=2) + '\n')


if __name__ == '__main__':
    main()
