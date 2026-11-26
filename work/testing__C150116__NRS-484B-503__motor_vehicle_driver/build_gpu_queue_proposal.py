"""Emit assignment-local exact-case queue proposal after strict CPU readiness."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
ROOT = HERE.parents[1]
BATCH = 'full-test-delivery'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    if len(manifest['cases']) != 16 or len(plan['comparisons']) != 7:
        raise ValueError('selected case or comparison count incomplete')
    cases = []
    prefix = ('PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m '
              'scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" ')
    for index, entry in enumerate(manifest['cases'], 1):
        case = entry['case_id']
        common = (f'--repo "$PWD" --batch {BATCH} --db "$DB" '
                  f'--assignment {AID} --case {case}')
        prepare = prefix + 'prepare-delivery ' + common
        execute = ('SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c150116-local-capture" '
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
        source_audit = ('PYTHONDONTWRITEBYTECODE=1 '
                        f'.venv-cpu/bin/python work/{AID}/finalize_original_delivery.py'
                        f' --attempt "$ATTEMPT" --case {case} && '
                        f'.venv-cpu/bin/python work/{AID}/delivery_audit.py case'
                        f' --attempt "$ATTEMPT" --case {case} --output "$SOURCE_AUDIT"')
        cases.append({'order': index, 'assignment_id': AID, 'case_id': case,
                      'prepare_command': prepare, 'execute_command': execute,
                      'accept_command': accept, 'capture_command': execute,
                      'postprocessing_command': saved,
                      'owner_release_command': f'CASE_ID={case} .venv-cpu/bin/python runtime.py owner-released --attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released',
                      'additional_source_audit_command': source_audit,
                      'candidate_commands': {candidate['id']: prepare +
                                             ' --candidate ' + candidate['id']
                                             for candidate in entry.get('candidates', [])}})
    comparisons = [{'assignment_id': AID, 'comparison_id': row['comparison_id'],
                    'case_ids': row['case_ids'],
                    'command': f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{AID}/delivery_audit.py comparisons --attempts "$ATTEMPT_INDEX" --comparison {row["comparison_id"]} --output "$COMPARISON_AUDIT"'}
                   for row in plan['comparisons']]
    proposal = {'format': 'worker-gpu-queue-proposal',
                'assignment_id': AID, 'selected_manifest_sha256': sha(manifest_path),
                'cases': cases, 'comparison_audit_commands': comparisons,
                'source_prerequisites': ['reviewed original marked passenger curb polygon/designation and one-way route',
                                         'applicable jurisdiction regulation/effective hours and civil clock',
                                         'source-hashed original Native adapter and passenger-event source',
                                         'four synchronized original camera streams and 900 frame history'],
                'remaining_review': ['CARLA physical completion and actual pixel decode',
                                     'legal expeditiousness and effective-zone judgment remain unresolved']}
    (HERE / 'gpu-queue-proposal.json').write_text(json.dumps(proposal, indent=2) + '\n')


if __name__ == '__main__':
    build()
