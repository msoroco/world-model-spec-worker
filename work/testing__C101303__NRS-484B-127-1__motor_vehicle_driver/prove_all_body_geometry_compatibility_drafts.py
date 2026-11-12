"""Run exact software compatibility on every geometry-aware draft bundle."""
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'body-geometry-all-draft-manifest.json'
VALIDATOR = REPO / '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if not VALIDATOR.is_file():
        raise ValueError('Pinned Lean decoder is absent')
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    for case in manifest['cases']:
        rows.append((case['case_id'], 'primary', case))
        rows.extend((case['case_id'], candidate['id'], candidate)
                    for candidate in case['candidates'])
    if len(rows) != 32:
        raise ValueError('Expected 32 exact constructions')
    log_dir = ROOT / 'body-geometry-draft' / 'compatibility'
    log_dir.mkdir(exist_ok=True)
    evidence = []
    for case_id, candidate_id, row in rows:
        source = ROOT / row['construction']
        if digest(source) != row['construction_sha256']:
            raise ValueError('Draft construction hash changed: ' + str(source))
        label = case_id.rsplit('__', 1)[-1] + '-' + candidate_id
        output = REPO / '.runtime-work/c101303-body-geometry-all-compat-v1' / label
        command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                   'compatibility', '--manifest', str(MANIFEST), '--case', case_id,
                   '--candidate', candidate_id, '--output', str(output),
                   '--library', str(REPO / 'runtime/library'),
                   '--validator', str(VALIDATOR)]
        completed = subprocess.run(command, cwd=REPO, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = log_dir / (label + '.log')
        log.write_text(completed.stdout)
        evidence.append({'case_id': case_id, 'candidate_id': candidate_id,
                         'construction_sha256': row['construction_sha256'],
                         'exit_code': completed.returncode,
                         'log': str(log.relative_to(ROOT)), 'log_sha256': digest(log)})
        print(label, completed.returncode, flush=True)
        if completed.returncode:
            break
    summary = ROOT / 'body-geometry-draft' / 'all-compatibility-proof.json'
    summary.write_text(json.dumps({'manifest_sha256': digest(MANIFEST),
                                   'attempted_count': len(evidence),
                                   'passed_count': sum(r['exit_code'] == 0 for r in evidence),
                                   'proofs': evidence}, indent=2) + '\n')
    if len(evidence) != 32 or any(r['exit_code'] for r in evidence):
        raise ValueError('At least one geometry draft compatibility check failed')


if __name__ == '__main__':
    main()
