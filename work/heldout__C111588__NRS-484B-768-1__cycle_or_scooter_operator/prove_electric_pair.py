"""Run exact CPU offline, compatibility and negative-source proofs."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PY = str(REPO / '.venv-cpu/bin/python')
VALIDATOR = '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def run(cmd, log):
    with log.open('w') as out:
        result = subprocess.run(cmd, cwd=REPO, stdout=out, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(str(cmd) + '\n' + log.read_text()[-1200:])


for device in ('electric_bicycle', 'electric_scooter'):
    case = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__' + device + '_signal_once'
    manifest = ROOT / (device.replace('_', '-') + '-manifest.json')
    folder = ROOT / 'cases' / (device + '_signal_once')
    obj = json.loads(manifest.read_text())
    entry = obj['cases'][0]
    for number in range(4):
        name = 'primary' if number == 0 else 'fallback' + str(number)
        candidate = [] if number == 0 else ['--candidate', name]
        offline_output = '.runtime-work/c111588-' + device + '-' + name + '-offline-final-b'
        offline = [PY, 'runtime.py', 'offline', '--manifest', str(manifest.relative_to(REPO)),
                   '--case', case, '--output', offline_output, '--python', PY] + candidate
        test_log = folder / (name + '-tests.log')
        run(offline, test_log)
        if number:
            item = entry['candidates'][number-1]
            item['offline'] = {'command': ' '.join(offline), 'exit_code': 0,
                               'log': str(test_log.relative_to(ROOT)),
                               'log_sha256': sha(test_log), 'construction_sha256': item['construction_sha256']}
        output = '.runtime-work/c111588-' + device + '-' + name + '-compat-final-b'
        compat = [PY, 'runtime.py', 'compatibility', '--manifest', str(manifest.relative_to(REPO)),
                  '--case', case, '--output', output, '--library', 'runtime/library',
                  '--validator', VALIDATOR] + candidate
        compat_log = folder / (name + '-analysis.log')
        run(compat, compat_log)
        receipt_path = folder / (name + '-receipt.json')
        shutil.copy2(REPO / output / 'compatibility.json', receipt_path)
        shutil.copy2(REPO / output / 'compatibility-analysis.log', compat_log)
        negative = folder / (name + '-negative.log')
        negative.write_bytes((REPO / output / 'negative-analysis.log').read_bytes())
        if number:
            item['compatibility'] = {'receipt': str(receipt_path.relative_to(ROOT)), 'sha256': sha(receipt_path),
                                     'log': str(compat_log.relative_to(ROOT)),
                                     'negative_log': str(negative.relative_to(ROOT))}
        print(device, name, 'offline and compatibility passed', flush=True)
    manifest.write_text(json.dumps(obj, indent=2) + '\n')
