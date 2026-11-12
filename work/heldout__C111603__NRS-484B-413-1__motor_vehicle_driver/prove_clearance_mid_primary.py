"""Prove the exact intermediate clearance primary on the CPU path."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PY = str(REPO / '.venv-cpu/bin/python')
MANIFEST = ROOT / 'clearance-mid-manifest.json'
manifest = json.loads(MANIFEST.read_text())
entry = manifest['cases'][0]
CASE = entry['case_id']

def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()

def run(command, log):
    with log.open('w') as stream:
        subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, check=True)

command = [PY, 'runtime.py', 'offline', '--manifest', str(MANIFEST.relative_to(REPO)),
           '--case', CASE, '--output', '.runtime-work/c111603-clearance-mid-primary-offline-f', '--python', PY]
log = ROOT / 'clearance-mid-offline.log'
run(command, log)
entry['offline'] = {'command': ' '.join(command), 'exit_code': 0, 'log': log.name,
                    'log_sha256': sha(log), 'construction_sha256': entry['construction_sha256']}
command = [PY, 'runtime.py', 'compatibility', '--manifest', str(MANIFEST.relative_to(REPO)),
           '--case', CASE, '--output', '.runtime-work/c111603-clearance-mid-primary-compat-f',
           '--library', 'runtime/library', '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
log = ROOT / 'clearance-mid-compatibility.log'
run(command, log)
attempt = REPO / '.runtime-work/c111603-clearance-mid-primary-compat-f'
for source, destination in (('compatibility.json', 'clearance-mid-compatibility-receipt.json'),
                            ('compatibility-analysis.log', 'clearance-mid-analysis.log'),
                            ('negative-analysis.log', 'clearance-mid-negative.log')):
    shutil.copy2(attempt / source, ROOT / destination)
receipt = ROOT / 'clearance-mid-compatibility-receipt.json'
entry['compatibility'] = {'receipt': receipt.name, 'sha256': sha(receipt),
                          'log': 'clearance-mid-analysis.log'}
entry['negative'] = {'log': 'clearance-mid-negative.log'}
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
print('Intermediate clearance primary offline and compatibility proofs passed')
