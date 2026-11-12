"""Reprove every selected candidate's pinned offline construction after case edits."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE/'execution-manifest.json'
PROPOSAL = HERE/'proposals/cases.json'
PYTHON = ROOT/'.venv-cpu/bin/python'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_sha, proposal_sha = sha(MANIFEST), sha(PROPOSAL)
    manifest = json.loads(MANIFEST.read_text())
    if manifest['selection_review']['proposal_sha256'] != proposal_sha:
        raise ValueError('Current semantic proposal not bound')
    rows = []
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        for candidate in CANDIDATES:
            selected = (entry if candidate == 'primary' else
                        next(item for item in entry['candidates'] if item['id'] == candidate))
            output = ROOT/'.runtime-work'/f'c104538-update023-offline-{suffix}-{candidate}'
            log = HERE/f'update023-{suffix}-{candidate}-offline.log'
            command = [str(PYTHON), str(ROOT/'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', case,
                       '--candidate', candidate, '--output', str(output),
                       '--python', str(PYTHON)]
            if not log.is_file():
                if output.exists():
                    raise ValueError(f'Partial offline output: {output}')
                with log.open('w') as stream:
                    result = subprocess.run(command, cwd=ROOT, stdout=stream,
                                            stderr=subprocess.STDOUT, timeout=300)
                if result.returncode:
                    raise RuntimeError(f'Offline failed: {case} {candidate}')
            receipt = json.loads(log.read_text())
            if (receipt.get('offline_passed') is not True or
                    receipt.get('simulation_started') is not False or
                    receipt.get('case_id') != case or
                    receipt.get('candidate_id') != candidate):
                raise ValueError(f'Offline receipt incomplete: {case} {candidate}')
            rows.append({'case_id': case, 'candidate_id': candidate,
                         'construction_sha256': selected['construction_sha256'],
                         'manifest_sha256': manifest_sha, 'proposal_sha256': proposal_sha,
                         'command': shlex.join(command), 'log': log.name,
                         'log_sha256': sha(log), 'offline_passed': True,
                         'simulation_started': False})
            print(suffix, candidate, 'offline passed', flush=True)
    if sha(MANIFEST) != manifest_sha or sha(PROPOSAL) != proposal_sha:
        raise ValueError('Manifest/proposal changed during offline run')
    summary = {'format': 'c104538-semantic-bound-offline-v1',
               'manifest_sha256': manifest_sha, 'proposal_sha256': proposal_sha,
               'results': rows, 'simulation_started': False}
    path = HERE/'update023-semantic-bound-offline.json'
    path.write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({'offline_proofs': len(rows), 'summary_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
