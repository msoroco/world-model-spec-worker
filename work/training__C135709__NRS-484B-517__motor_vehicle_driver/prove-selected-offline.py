"""Run the pinned exact offline command for each selected stand candidate."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT/'selected-all/draft-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    env = dict(os.environ, MPLCONFIGDIR='/tmp/c135709-mpl')
    for entry in manifest['cases']:
        witness = entry['case_id'].split('__')[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            output = REPO/'.runtime-work/update051-c135709-selected-all-v5'/witness/candidate
            log = ROOT/'update050-offline'/witness/(candidate+'.log')
            log.parent.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, str(REPO/'runtime.py'), 'offline',
                '--manifest', str(MANIFEST), '--case', entry['case_id'],
                '--candidate', candidate, '--output', str(output),
                '--python', sys.executable]
            with log.open('w') as stream:
                result = subprocess.run(command, cwd=REPO, env=env,
                    stdout=stream, stderr=subprocess.STDOUT, timeout=300)
            construction = entry if candidate == 'primary' else next(
                item for item in entry['candidates'] if item['id'] == candidate)
            rows.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                'construction_sha256': construction['construction_sha256'],
                'command': ' '.join(command), 'exit_code': result.returncode,
                'log': log.relative_to(ROOT).as_posix(), 'log_sha256': sha(log),
                'runtime_output': output.relative_to(REPO).as_posix()})
            print(json.dumps({'case': witness, 'candidate': candidate,
                              'exit_code': result.returncode}), flush=True)
    proof = {'format': 'c135709-selected-offline-proof-v1',
        'manifest_sha256': sha(MANIFEST), 'results': rows,
        'all_passed': all(row['exit_code'] == 0 for row in rows),
        'original_native_observed': False}
    path = ROOT/'selected-all/draft-proof.json'
    path.write_text(json.dumps(proof, indent=2)+'\n')
    if not proof['all_passed']:
        raise ValueError('One or more selected offline checks failed; inspect hashed logs')
    return proof


if __name__ == '__main__':
    print(json.dumps({'passed': len(prove()['results'])}))
