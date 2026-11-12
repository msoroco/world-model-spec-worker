"""Run source-bound CPU classifier and lifecycle checks for the staged policy."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parents[1]
REPO = ASSIGNMENT.parent.parent
STAGE = HERE / 'clearance_guard'
MANIFEST = ASSIGNMENT / 'clearance-guard-draft-manifest.json'
PROOF = REPO / '.runtime-work/c109749-clearance-guard-primary-saved/v0001/processing.json'
SCRIPT = ASSIGNMENT / 'inside_physical_fixture_proof.py'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove():
    entry = json.loads(MANIFEST.read_text())['cases'][0]
    if not entry['case_id'].endswith('__approaching_far'):
        raise ValueError('Wrong staged case')
    results = []
    for kind in KINDS:
        output = STAGE / ('physical-' + kind + '.json')
        log = STAGE / ('physical-' + kind + '.log')
        args = ['.venv-cpu/bin/python', str(SCRIPT), '--manifest', str(MANIFEST),
                '--case', entry['case_id'], '--kind', kind, '--output', str(output)]
        if kind == 'lifecycle':
            args += ['--saved-receipt', str(PROOF)]
        with log.open('w') as stream:
            subprocess.run(args, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, check=True)
        result = json.loads(output.read_text())
        if result.get('diagnostic_fixture') is not True:
            raise ValueError('Physical fixture provenance missing')
        if kind != 'lifecycle' and result.get('physical_acceptance_claimed') is not False:
            raise ValueError('Physical acceptance incorrectly asserted')
        results.append({'kind': kind, 'command': ' '.join(args),
                        'log': str(log.relative_to(ASSIGNMENT)), 'log_sha256': sha(log),
                        'result': str(output.relative_to(ASSIGNMENT)),
                        'result_sha256': sha(output), 'exit_code': 0})
    receipt = {'format': 'worker-staged-physical-proof', 'case_id': entry['case_id'],
               'construction_sha256': entry['construction_sha256'],
               'manifest_sha256': sha(MANIFEST), 'saved_receipt_sha256': sha(PROOF),
               'fixtures': results, 'physical_acceptance_claimed': False}
    path = STAGE / 'physical-proof-receipt.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    return {'fixture_count': len(results), 'receipt': str(path.relative_to(ASSIGNMENT)),
            'sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
