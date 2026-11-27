"""Emit assignment-local twelve-case and ten-comparison queue intent."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    plan = json.loads((HERE / 'case-plan.json').read_text(encoding='utf-8'))
    if len(manifest['cases']) != 12 or len(plan['comparisons']) != 10:
        raise ValueError('exact emergency-unit queue coverage incomplete')
    comparison_script = HERE / 'comparison_audit.py'
    comparisons = []
    for row in plan['comparisons']:
        command = (f'.venv-cpu/bin/python work/{AID}/comparison_audit.py'
                   f' --comparison {row["comparison_id"]}')
        for index, case_id in enumerate(row['case_ids'], 1):
            command += f' --audit {case_id} "$AUDIT_{index}"'
        command += ' --output "$COMPARISON_AUDIT"'
        comparisons.append({'comparison_id': row['comparison_id'],
            'case_ids': row['case_ids'], 'script': comparison_script.name,
            'script_sha256': sha(comparison_script), 'command': command,
            'source_gate': 'Closed original Native attempts and independent source-hashed case audits required.'})
    (HERE / 'comparison-audit-plan.json').write_text(json.dumps({
        'format': 'c405341-original-comparison-audit-plan-v1',
        'assignment_id': AID, 'comparisons': comparisons,
        'original_source_verified': False}, indent=2) + '\n', encoding='utf-8')
    prefix = ('PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m '
              'scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" ')
    cases = []
    for order, entry in enumerate(manifest['cases'], 1):
        case = entry['case_id']
        common = ('--repo "$PWD" --batch full-test-delivery --db "$DB" '
                  f'--assignment {AID} --case {case}')
        prepare = prefix + 'prepare-delivery ' + common
        execute = ('SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c405341-2e-local-capture" '
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
            'command': row['command']} for row in comparisons],
        'source_prerequisites': ['reviewed paved-road ego and unit routes',
            'authorized emergency or regulatory official class and qualifying flashing equipment',
            'source-bound traffic, weather, roadway, other hazard condition, officer direction and visible preparation cues where selected',
            'four reviewed camera poses and source-hashed Native adapter'],
        'remaining_review': ['Native unit movement, ego lane footprint, traffic/weather context and driver-view pixels',
            'statutory possibility and safety judgments remain unresolved']}
    (HERE / 'gpu-queue-proposal.json').write_text(json.dumps(proposal, indent=2) + '\n',
                                                  encoding='utf-8')


if __name__ == '__main__':
    main()
