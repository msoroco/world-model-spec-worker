"""Rebuild recorded-only processing from each exact draft compatibility attempt."""
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'body-geometry-all-draft-manifest.json'
VALIDATOR = REPO / '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'
COMPAT_ROOT = REPO / '.runtime-work/c101303-body-geometry-all-compat-v1'
SAVED_ROOT = REPO / '.runtime-work/c101303-body-geometry-all-saved-v1'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    for case in manifest['cases']:
        rows.append((case['case_id'], 'primary', case))
        rows.extend((case['case_id'], candidate['id'], candidate)
                    for candidate in case['candidates'])
    if len(rows) != 32:
        raise ValueError('Expected 32 exact constructions')
    log_dir = ROOT / 'body-geometry-draft' / 'saved'
    log_dir.mkdir(exist_ok=True)
    evidence = []
    for case_id, candidate_id, row in rows:
        label = case_id.rsplit('__', 1)[-1] + '-' + candidate_id
        attempt = COMPAT_ROOT / label
        receipt = json.loads((attempt / 'compatibility.json').read_text())
        if (receipt.get('passed') is not True or receipt['case_id'] != case_id
                or receipt['candidate_id'] != candidate_id
                or receipt['construction_sha256'] != row['construction_sha256']):
            raise ValueError('Compatibility attempt is not exact: ' + label)
        output = SAVED_ROOT / label
        command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                   'process-saved', '--manifest', str(MANIFEST), '--case', case_id,
                   '--attempt', str(attempt), '--output', str(output),
                   '--library', str(REPO / 'runtime/library'),
                   '--validator', str(VALIDATOR)]
        completed = subprocess.run(command, cwd=REPO, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = log_dir / (label + '.log')
        log.write_text(completed.stdout)
        proof_path = output / 'v0001/processing.json'
        if completed.returncode == 0:
            proof = json.loads(proof_path.read_text())
            if (proof.get('passed') is not True or proof.get('recorded_only') is not True
                    or proof.get('originals_preserved') is not True
                    or proof.get('candidate_id') != candidate_id
                    or proof.get('physical_acceptance_claimed') is not False):
                raise ValueError('Recorded-only saved proof failed: ' + label)
        evidence.append({'case_id': case_id, 'candidate_id': candidate_id,
                         'construction_sha256': row['construction_sha256'],
                         'exit_code': completed.returncode,
                         'log': str(log.relative_to(ROOT)), 'log_sha256': digest(log),
                         'processing_sha256': digest(proof_path) if proof_path.exists() else None})
        print(label, completed.returncode, flush=True)
        if completed.returncode:
            break
    summary = ROOT / 'body-geometry-draft' / 'all-saved-proof.json'
    summary.write_text(json.dumps({'manifest_sha256': digest(MANIFEST),
                                   'attempted_count': len(evidence),
                                   'passed_count': sum(r['exit_code'] == 0 for r in evidence),
                                   'proofs': evidence}, indent=2) + '\n')
    if len(evidence) != 32 or any(r['exit_code'] for r in evidence):
        raise ValueError('At least one geometry draft saved-processing check failed')


if __name__ == '__main__':
    main()
