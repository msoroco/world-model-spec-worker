"""Run pinned offline construction checks for all unselected spacing drafts."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'body-geometry-all-draft-manifest.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    for case in manifest['cases']:
        rows.append((case['case_id'], None, case))
        rows.extend((case['case_id'], candidate['id'], candidate)
                    for candidate in case['candidates'])
    if len(rows) != 32:
        raise ValueError('Expected 32 exact draft constructions')
    log_dir = ROOT / 'body-geometry-draft' / 'offline'
    log_dir.mkdir(exist_ok=True)
    evidence = []
    for case_id, candidate_id, row in rows:
        source = MANIFEST.parent / row['construction']
        if digest(source) != row['construction_sha256']:
            raise ValueError('Draft construction hash changed: ' + str(source))
        label = case_id.rsplit('__', 1)[-1] + '-' + (candidate_id or 'primary')
        command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                   'offline', '--manifest', str(MANIFEST), '--case', case_id,
                   '--output', str(REPO / '.runtime-work/c101303-body-geometry-all-draft-v2' / label)]
        if candidate_id:
            command.extend(['--candidate', candidate_id])
        completed = subprocess.run(command, cwd=REPO, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = log_dir / (label + '.log')
        log.write_text(completed.stdout)
        evidence.append({'case_id': case_id, 'candidate_id': candidate_id or 'primary',
                         'construction_sha256': row['construction_sha256'],
                         'exit_code': completed.returncode,
                         'log': str(log.relative_to(ROOT)), 'log_sha256': digest(log)})
        print(label, completed.returncode, flush=True)
        if completed.returncode:
            break
    summary = ROOT / 'body-geometry-draft' / 'all-offline-proof.json'
    summary.write_text(json.dumps({'manifest_sha256': digest(MANIFEST),
                                   'attempted_count': len(evidence),
                                   'passed_count': sum(r['exit_code'] == 0 for r in evidence),
                                   'proofs': evidence}, indent=2) + '\n')
    if len(evidence) != 32 or any(r['exit_code'] for r in evidence):
        raise ValueError('At least one geometry draft offline check failed')


if __name__ == '__main__':
    main()
