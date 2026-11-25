"""Run exact selected manifest CPU paths into scratch and retain bounded logs."""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = 'work/' + ROOT.name + '/execution-manifest.json'
SCRATCH = REPO / '.runtime-work/c111329-selected-runtime'
if SCRATCH.exists():
    shutil.rmtree(SCRATCH)
SCRATCH.mkdir(parents=True, exist_ok=True)
VALIDATOR = '.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'
RECEIPTS = []


def run(args, label):
    command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py')] + args
    proc = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                          env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
                               'TMPDIR': str(SCRATCH)})
    log = ROOT / ('nov25-selected-' + label + '.log')
    log.write_text(((proc.stdout + proc.stderr).strip() or 'no output') + '\n')
    if proc.returncode:
        raise RuntimeError(str(log) + ': ' + log.read_text()[-1200:])
    RECEIPTS.append({'command': ' '.join(command), 'exit_code': 0,
                     'log': log.name, 'sha256': hashlib.sha256(log.read_bytes()).hexdigest()})


manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
for entry in manifest['cases']:
    case = entry['case_id']
    suffix = case.rsplit('__', 1)[-1]
    base = '.runtime-work/c111329-selected-runtime/' + suffix
    run(['offline', '--manifest', MANIFEST, '--case', case,
         '--output', base + '-offline', '--python', str(REPO / '.venv-cpu/bin/python')],
        'offline-' + suffix)
    run(['compatibility', '--manifest', MANIFEST, '--case', case,
         '--output', base + '-compat', '--library', 'runtime/library',
         '--validator', VALIDATOR], 'compat-' + suffix)
    source = REPO / (base + '-compat')
    saved_source = REPO / (base + '-saved-source')
    shutil.copytree(source, saved_source)
    (saved_source / 'candidate-selection.json').unlink(missing_ok=True)
    run(['process-saved', '--manifest', MANIFEST, '--case', case,
         '--attempt', str(saved_source.relative_to(REPO)),
         '--output', base + '-saved', '--library', 'runtime/library',
         '--validator', VALIDATOR], 'saved-' + suffix)
    run(['offline', '--manifest', MANIFEST, '--case', case, '--candidate', 'fallback1',
         '--output', base + '-fallback-offline', '--python', str(REPO / '.venv-cpu/bin/python')],
        'fallback-offline-' + suffix)
    run(['compatibility', '--manifest', MANIFEST, '--case', case, '--candidate', 'fallback1',
         '--output', base + '-fallback-compat', '--library', 'runtime/library',
         '--validator', VALIDATOR], 'fallback-compat-' + suffix)

(ROOT / 'selected-runtime-receipts.json').write_text(json.dumps({
    'scope': 'synthetic diagnostic selected-manifest CPU proof; no original physical or legal acceptance',
    'tests': RECEIPTS}, indent=2) + '\n')
print('selected manifest: 3 primary/fallback offline, 3 primary/fallback compatibility, 3 saved-only CPU paths passed')
