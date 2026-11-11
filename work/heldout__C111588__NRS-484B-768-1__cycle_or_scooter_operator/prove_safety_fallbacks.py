"""Exact offline and compatibility proof for wide/narrow safety candidates."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

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
        raise RuntimeError(str(cmd) + '\n' + log.read_text()[-1500:])


for slug in ('safety_wide', 'safety_narrow'):
    case = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__' + slug
    manifest = ROOT / (slug.replace('_', '-') + '-manifest.json')
    folder = ROOT / 'cases' / slug
    obj = json.loads(manifest.read_text())
    entry = obj['cases'][0]
    for number in range(4):
        name = 'primary' if number == 0 else 'fallback' + str(number)
        candidate = [] if number == 0 else ['--candidate', name]
        offline_output = '.runtime-work/c111588-' + slug + '-' + name + '-offline-h'
        offline = [PY, 'runtime.py', 'offline', '--manifest', str(manifest.relative_to(REPO)),
                   '--case', case, '--output', offline_output, '--python', PY] + candidate
        test_log = folder / (name + '-tests.log')
        run(offline, test_log)
        if number:
            item = entry['candidates'][number-1]
            item['offline'] = {'command': ' '.join(offline), 'exit_code': 0,
                               'log': str(test_log.relative_to(ROOT)),
                               'log_sha256': sha(test_log), 'construction_sha256': item['construction_sha256']}
        output = '.runtime-work/c111588-' + slug + '-' + name + '-compat-h'
        compat = [PY, 'runtime.py', 'compatibility', '--manifest', str(manifest.relative_to(REPO)),
                  '--case', case, '--output', output, '--library', 'runtime/library',
                  '--validator', VALIDATOR] + candidate
        stdout = folder / (name + '-compatibility-stdout.log')
        run(compat, stdout)
        receipt_path = folder / (name + '-receipt.json')
        compat_log = folder / (name + '-analysis.log')
        negative = folder / (name + '-negative.log')
        shutil.copy2(REPO / output / 'compatibility.json', receipt_path)
        shutil.copy2(REPO / output / 'compatibility-analysis.log', compat_log)
        shutil.copy2(REPO / output / 'negative-analysis.log', negative)
        if number:
            item['compatibility'] = {'receipt': str(receipt_path.relative_to(ROOT)), 'sha256': sha(receipt_path),
                                     'log': str(compat_log.relative_to(ROOT)),
                                     'negative_log': str(negative.relative_to(ROOT))}
        print(slug, name, 'offline and compatibility passed', flush=True)
    manifest.write_text(json.dumps(obj, indent=2) + '\n')
