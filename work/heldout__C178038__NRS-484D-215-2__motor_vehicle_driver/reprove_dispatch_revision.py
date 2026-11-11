"""Reprove all selected constructions after changing Native CLI dispatch."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
LIBRARY = ROOT / 'runtime/library'
VALIDATOR = ROOT / '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck'
manifest = json.loads(MANIFEST.read_text())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def command_text(args):
    return '.venv-cpu/bin/python runtime.py ' + ' '.join(args)


def run_case(entry, candidate):
    case = entry['case_id']
    suffix = case.split('__')[-1]
    selected = entry if candidate == 'primary' else next(
        item for item in entry['candidates'] if item['id'] == candidate)
    stem = suffix if candidate == 'primary' else f'{suffix}-{candidate}'
    token = uuid4().hex[:8]
    offline = ROOT / '.runtime-work' / f'c178038-{stem}-dispatch-offline-{token}'
    compat = ROOT / '.runtime-work' / f'c178038-{stem}-dispatch-compat-{token}'
    common = ['--manifest', str(MANIFEST), '--case', case]
    if candidate != 'primary':
        common += ['--candidate', candidate]
    offline_args = ['offline', *common, '--output', str(offline), '--python', sys.executable]
    process = subprocess.run([sys.executable, str(ROOT / 'runtime.py'), *offline_args],
                             cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True)
    log = HERE / selected['offline']['log']
    log.write_text(process.stdout)
    if process.returncode:
        raise ValueError(f'{stem} offline failed: {process.stdout[-1200:]}')
    selected['offline'] = {'command': command_text(offline_args), 'exit_code': 0,
                           'log': str(log.relative_to(HERE)), 'log_sha256': digest(log),
                           'construction_sha256': selected['construction_sha256']}
    compat_args = ['compatibility', *common, '--output', str(compat),
                   '--library', str(LIBRARY), '--validator', str(VALIDATOR)]
    process = subprocess.run([sys.executable, str(ROOT / 'runtime.py'), *compat_args],
                             cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True)
    if process.returncode:
        raise ValueError(f'{stem} compatibility failed: {process.stdout[-1200:]}')
    receipt = HERE / selected['compatibility']['receipt']
    shutil.copy2(compat / 'compatibility.json', receipt)
    shutil.copy2(compat / 'compatibility-analysis.log', HERE / selected['compatibility']['log'])
    shutil.copy2(compat / 'negative-analysis.log', HERE / selected['compatibility']['negative_log'])
    selected['compatibility']['sha256'] = digest(receipt)
    print(stem, 'offline and positive/negative compatibility passed', flush=True)


for entry in manifest['cases']:
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        run_case(entry, candidate)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')

# Keep the two case-family manifests current for saved and comparison proof scripts.
for name in ('night-all-fallback-manifest.json', 'context-fallback-manifest.json'):
    path = HERE / name
    family = json.loads(path.read_text())
    by_id = {item['case_id']: item for item in manifest['cases']}
    family['cases'] = [by_id[item['case_id']] for item in family['cases']]
    path.write_text(json.dumps(family, indent=2) + '\n')
print('Updated six-case execution and two family manifests')
