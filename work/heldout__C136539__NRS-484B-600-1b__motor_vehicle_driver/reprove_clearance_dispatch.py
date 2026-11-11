"""Reprove exact primary/fallback dispatch after adding clearance sweep points."""

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
VALIDATOR = ROOT / '.runtime-work/c125714-validator/.lake/build/bin/adapterCheck'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def run(selected, case, candidate):
    suffix = case.split('__')[-1]
    stem = suffix if candidate == 'primary' else suffix + '-' + candidate
    token = uuid4().hex[:8]
    common = ['--manifest', str(MANIFEST), '--case', case]
    if candidate != 'primary':
        common += ['--candidate', candidate]
    offline = ROOT / '.runtime-work' / f'c136539-{stem}-offline-sweep-{token}'
    args = ['offline', *common, '--output', str(offline), '--python', sys.executable]
    process = subprocess.run([sys.executable, str(ROOT / 'runtime.py'), *args], cwd=ROOT,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    offline_rel = selected.get('offline', {}).get('log',
        f'cases/{stem}-offline.log')
    (HERE / offline_rel).write_text(process.stdout)
    if process.returncode:
        raise ValueError(stem + ' offline: ' + process.stdout[-1000:])
    selected['offline'] = {
        'command': '.venv-cpu/bin/python runtime.py ' + ' '.join(args),
        'exit_code': 0, 'log': offline_rel,
        'log_sha256': sha(HERE / offline_rel),
        'construction_sha256': selected['construction_sha256']}
    compat = ROOT / '.runtime-work' / f'c136539-{stem}-compat-sweep-{token}'
    args = ['compatibility', *common, '--output', str(compat),
            '--library', str(LIBRARY), '--validator', str(VALIDATOR)]
    process = subprocess.run([sys.executable, str(ROOT / 'runtime.py'), *args], cwd=ROOT,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if process.returncode:
        raise ValueError(stem + ' compatibility: ' + process.stdout[-1300:])
    paths = selected.setdefault('compatibility', {
        'receipt': f'cases/fallback-compatibility-{stem}.json' if candidate != 'primary' else f'case-{suffix}-compatibility.json',
        'log': f'cases/fallback-compat-{stem}.log' if candidate != 'primary' else f'case-{suffix}-compat.log',
        'negative_log': f'cases/fallback-negative-{stem}.log' if candidate != 'primary' else f'case-{suffix}-negative.log'})
    shutil.copyfile(compat / 'compatibility.json', HERE / paths['receipt'])
    shutil.copyfile(compat / 'compatibility-analysis.log', HERE / paths['log'])
    shutil.copyfile(compat / 'negative-analysis.log', HERE / paths['negative_log'])
    paths['sha256'] = sha(HERE / paths['receipt'])
    print(stem, 'offline, compatibility, negative passed', flush=True)


manifest = json.loads(MANIFEST.read_text())
for entry in manifest['cases']:
    run(entry, entry['case_id'], 'primary')
    for candidate in entry['candidates']:
        run(candidate, entry['case_id'], candidate['id'])
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')

by_id = {entry['case_id']: entry for entry in manifest['cases']}
for name in ('probe-compatibility-manifest.json', 'fallback-constructions-manifest.json'):
    path = HERE / name
    family = json.loads(path.read_text())
    for index, entry in enumerate(family['cases']):
        current = by_id[entry['case_id']]
        family['cases'][index] = current if name.startswith('fallback') else {
            key: value for key, value in current.items() if key not in (
                'candidate_risk', 'candidates', 'offline', 'post_capture',
                'physical_preparation', 'delivery_acceptance', 'native_handoff')}
    path.write_text(json.dumps(family, indent=2) + '\n')
print('Rebound all nine exact primary and fallback dispatch receipts')
