"""Run exact CPU offline, positive and missing-original proofs for three fallbacks."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PY = str(REPO / '.venv-cpu/bin/python')
CASE = ROOT.name + '__vehicle_left_indicator'
MANIFEST = ROOT / 'vehicle-indicator-manifest.json'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def run(command, log):
    with log.open('w') as stream:
        result = subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(log.name + ': ' + log.read_text()[-1800:])


manifest = json.loads(MANIFEST.read_text())
entry = manifest['cases'][0]
for candidate in entry['candidates']:
    name = candidate['id']
    offline = f'.runtime-work/c111603-vehicle-indicator-{name}-offline-b'
    command = [PY, 'runtime.py', 'offline', '--manifest', str(MANIFEST.relative_to(REPO)),
               '--case', CASE, '--candidate', name, '--output', offline, '--python', PY]
    offline_log = ROOT / ('vehicle-indicator-' + name + '-offline.log')
    run(command, offline_log)
    candidate['offline'] = {'command': ' '.join(command), 'exit_code': 0,
                            'log': offline_log.name, 'log_sha256': sha(offline_log),
                            'construction_sha256': candidate['construction_sha256']}
    output = f'.runtime-work/c111603-vehicle-indicator-{name}-compat-b'
    command = [PY, 'runtime.py', 'compatibility', '--manifest', str(MANIFEST.relative_to(REPO)),
               '--case', CASE, '--candidate', name, '--output', output,
               '--library', 'runtime/library',
               '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    stdout = ROOT / ('vehicle-indicator-' + name + '-compatibility.log')
    run(command, stdout)
    receipt = ROOT / ('vehicle-indicator-' + name + '-receipt.json')
    analysis = ROOT / ('vehicle-indicator-' + name + '-analysis.log')
    negative = ROOT / ('vehicle-indicator-' + name + '-negative.log')
    shutil.copy2(REPO / output / 'compatibility.json', receipt)
    shutil.copy2(REPO / output / 'compatibility-analysis.log', analysis)
    shutil.copy2(REPO / output / 'negative-analysis.log', negative)
    candidate['compatibility'] = {'receipt': receipt.name, 'sha256': sha(receipt),
                                  'log': analysis.name, 'negative_log': negative.name}
    print(name, 'offline and compatibility passed', flush=True)
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
