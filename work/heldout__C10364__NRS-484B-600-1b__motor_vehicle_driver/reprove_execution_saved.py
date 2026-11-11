"""Reprocess all exact alley primary diagnostic attempts under execution manifest."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
VALIDATOR = REPO / '.runtime-work/c125714-validator/.lake/build/bin/adapterCheck'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    entries = []
    for case in manifest['cases']:
        suffix = case['case_id'].split('__')[-1]
        source_attempt = REPO / '.runtime-work' / f'c10364-{suffix}-attempt-sourcepoint'
        attempt = REPO / '.runtime-work' / f'c10364-{suffix}-execution-attempt-proof-v3'
        if json.loads((source_attempt / 'fixture-provenance.json').read_text()).get(
                'provenance_kind') != 'synthetic_fixture':
            raise ValueError('Execution saved reproof requires marked synthetic original')
        if attempt.exists():
            raise ValueError('Retain prior diagnostic execution attempt: ' + suffix)
        shutil.copytree(source_attempt, attempt)
        selected = {'format': 'worker-candidate-selection', 'case_id': case['case_id'],
                    'candidate_id': 'primary',
                    'construction_sha256': case['construction_sha256'],
                    'manifest_sha256': digest(MANIFEST)}
        (attempt / 'candidate-selection.json').write_text(json.dumps(selected, indent=2) + '\n')
        output = REPO / '.runtime-work' / f'c10364-{suffix}-execution-saved-proof-v3'
        log = ROOT / 'cases' / f'execution-saved-{suffix}.log'
        command = [sys.executable, str(REPO / 'runtime.py'), 'process-saved',
                   '--manifest', str(MANIFEST), '--case', case['case_id'],
                   '--attempt', str(attempt), '--output', str(output),
                   '--library', str(REPO / 'runtime/library'),
                   '--validator', str(VALIDATOR)]
        process = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
        log.write_text(process.stdout + process.stderr)
        if process.returncode:
            raise ValueError('Exact saved execution failed: ' + suffix)
        receipt = json.loads(process.stdout)
        if (receipt.get('case_id') != case['case_id'] or not receipt.get('passed')
                or receipt.get('candidate_id') != 'primary'
                or receipt.get('native_revision', {}).get('construction_sha256') !=
                case['construction_sha256']
                or not receipt.get('originals_preserved')
                or receipt.get('missing_evidence')
                or receipt.get('physical_acceptance_claimed')
                or receipt.get('legal_acceptance_claimed')):
            raise ValueError('Exact saved execution receipt differs: ' + suffix)
        copy = ROOT / 'cases' / f'execution-saved-{suffix}.json'
        copy.write_text(json.dumps(receipt, indent=2) + '\n')
        entries.append({'case_id': case['case_id'], 'command': ' '.join(command),
                        'log': str(log.relative_to(ROOT)), 'log_sha256': digest(log),
                        'receipt': str(copy.relative_to(ROOT)),
                        'receipt_sha256': digest(copy), 'originals_preserved': True,
                        'physical_acceptance_claimed': False})
        print('saved ' + suffix, flush=True)
    (ROOT / 'execution-saved-proofs.json').write_text(json.dumps({
        'format': 'worker-alley-execution-saved-proofs',
        'assignment_id': manifest['assignment_id'],
        'execution_manifest_sha256': digest(MANIFEST), 'cases': entries}, indent=2) + '\n')
    print('Nine exact execution-manifest saved processing paths pass', flush=True)


if __name__ == '__main__':
    main()
