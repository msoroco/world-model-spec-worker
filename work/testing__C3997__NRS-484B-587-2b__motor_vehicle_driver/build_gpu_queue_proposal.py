"""Emit the exact assignment-local local-delivery queue intent."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shlex
import subprocess


HERE = Path(__file__).resolve().parent
AID = HERE.name
PREFIX = ('PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m '
          'scenario_pipeline.worker_exchange --root "$LOCAL_ROOT"')


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    comparison_proposal = json.loads((HERE / 'comparison-proposal.json').read_text())
    expected_cases = {row['case_id'] for row in plan['cases']}
    if len(manifest['cases']) != 10 or {row['case_id'] for row in manifest['cases']} != expected_cases:
        raise ValueError('Exact C3997 case coverage changed')
    if len(plan['comparisons']) != 9 or {row['comparison_id'] for row in plan['comparisons']} != {
            row['comparison_id'] for row in comparison_proposal['comparisons']}:
        raise ValueError('Exact C3997 comparison coverage changed')
    cases = []
    for order, entry in enumerate(manifest['cases'], 1):
        case = entry['case_id']
        common = (f'--repo "$PWD" --batch full-test-delivery --db "$DB" '
                  f'--assignment {AID} --case {case}')
        prepare = PREFIX + ' prepare-delivery ' + common
        execute = ('C3997_REVIEWED_SITE="$C3997_REVIEWED_SITE" ' + PREFIX +
                   ' execute-delivery ' + common + ' --run "$RUN" --job "$JOB_ID"' +
                   ' --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (PREFIX + ' accept-delivery ' + common +
                  ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT"' +
                  ' --audit "$AUDIT" --review-archive /external/archive')
        owner = (f'CASE_ID={case} .venv-cpu/bin/python runtime.py owner-released' +
                 ' --attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT"' +
                 ' --acknowledge-owner-released')
        saved = (f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/execution-manifest.json' +
                 f' --case {case} --attempt "$ATTEMPT" --output "$PROCESSED"' +
                 ' --library runtime/library --validator "$LEAN_VALIDATOR"' +
                 ' --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        audit = (f'mkdir -p "$PWD/.runtime-work/c3997-local-audit" && ' +
                 'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c3997-local-audit" ' +
                 'TMPDIR="$PWD/.runtime-work/c3997-local-audit" ' +
                 f'.venv-cpu/bin/python work/{AID}/delivery_audit.py --case {case}' +
                 ' --attempt "$ATTEMPT" --review "$PIXEL_REVIEW"' +
                 ' --physical "$PHYSICAL_RESULT" > "$AUDIT"')
        cases.append({'order': order, 'assignment_id': AID, 'case_id': case,
                      'prepare_command': prepare, 'execute_command': execute,
                      'capture_command': execute, 'accept_command': accept,
                      'owner_release_command': owner, 'postprocessing_command': saved,
                      'additional_source_audit_command': audit,
                      'candidate_commands': {candidate['id']: prepare + ' --candidate ' + candidate['id']
                                             for candidate in entry['candidates']}})
    comparisons = []
    for row in plan['comparisons']:
        cid = row['comparison_id']
        command = (f'.venv-cpu/bin/python work/{AID}/comparison_audit.py' +
                   f' --plan work/{AID}/case-plan.json --comparison {cid}' +
                   ' --left-history "$LEFT_ATTEMPT/original-history.jsonl"' +
                   ' --right-history "$RIGHT_ATTEMPT/original-history.jsonl"' +
                   ' --left-sha256 "$LEFT_HISTORY_SHA256"' +
                   ' --right-sha256 "$RIGHT_HISTORY_SHA256"' +
                   ' --map-sha256 "$MAP_SHA256" > "$COMPARISON_AUDIT"')
        comparisons.append({'assignment_id': AID, 'comparison_id': cid,
                            'case_ids': row['case_ids'], 'command': command})
    proposal = {'format': 'worker-assignment-gpu-queue-proposal',
                'assignment_id': AID, 'selected_manifest_sha256': digest(manifest_path),
                'cases': cases, 'comparison_audit_commands': comparisons,
                'comparison_source_prerequisites': [
                    'Use the two exact source-sealed original Native attempts named by each comparison.',
                    'Bind each history SHA from its original capture-seal receipt and the common reviewed map SHA.'
                ]}
    for command in [value for row in cases for key, value in row.items()
                    if key.endswith('_command') and isinstance(value, str)] + [
                    value for row in cases for value in row['candidate_commands'].values()] + [
                    row['command'] for row in comparisons]:
        if not shlex.split(command) or subprocess.run(['bash', '-n', '-c', command],
                                                       capture_output=True).returncode:
            raise ValueError('Malformed queue command: ' + command)
    (HERE / 'gpu-queue-proposal.json').write_text(json.dumps(proposal, indent=2) + '\n')
    return {'cases': len(cases), 'comparisons': len(comparisons),
            'commands': 7 * len(cases) + sum(len(row['candidate_commands']) for row in cases)
                        + len(comparisons)}


if __name__ == '__main__':
    print(json.dumps(build()))
