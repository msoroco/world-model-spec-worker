"""Run public exact-case offline checks and bind their source-hashed logs."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
PROBES = ('distance_below_500ft', 'distance_at_500ft', 'distance_above_500ft')
MANIFEST = ROOT/'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
for probe in PROBES:
    entry = next(e for e in manifest['cases'] if e['case_id'] == AID+'__'+probe)
    for candidate in ('primary', 'fallback1'):
        output = REPO/'.runtime-work'/'c183394'/('offline-'+probe+'-'+candidate)
        command = [str(REPO/'.venv-cpu/bin/python'), str(REPO/'runtime.py'), 'offline',
                   '--manifest', str(MANIFEST), '--case', entry['case_id'],
                   '--candidate', candidate, '--output', str(output),
                   '--python', str(REPO/'.venv-cpu/bin/python')]
        if output.exists():
            shutil.rmtree(output)
        result = subprocess.run(command, cwd=REPO, env=os.environ, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f'{probe} {candidate}: {result.stderr[-1000:]}')
        proof_log = ROOT/'offline'/f'{probe}-{candidate}.log'
        shutil.copyfile(output/'offline.log', proof_log)
        construction = entry if candidate == 'primary' else entry['candidates'][0]
        construction['offline'] = {'case_id': entry['case_id'], 'candidate_id': candidate,
            'construction_sha256': construction['construction_sha256'],
            'command': ' '.join(command), 'exit_code': 0,
            'log': str(proof_log.relative_to(ROOT)), 'log_sha256': sha(proof_log)}
        print('PASS', probe, candidate)
MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
