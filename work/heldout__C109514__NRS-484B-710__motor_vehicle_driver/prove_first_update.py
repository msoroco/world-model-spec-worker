"""Refresh exact first-case proofs after source-bound exception validation changes."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
manifest = json.loads(MANIFEST.read_text())
entry = manifest['cases'][0]
case = entry['case_id']

def digest(path):
    return sha256(path.read_bytes()).hexdigest()

for label, row in [('primary', entry), *[(x['id'], x) for x in entry['candidates']]]:
    stem = 'c109514-exception-source-' + row['construction_sha256'][:12] + '-' + label
    offline = ['.venv-cpu/bin/python', 'runtime.py', 'offline', '--manifest',
               MANIFEST.relative_to(ROOT).as_posix(), '--case', case, '--candidate', label,
               '--output', '.runtime-work/' + stem + '-offline',
               '--python', str(ROOT / '.venv-cpu/bin/python')]
    proc = subprocess.run(offline, cwd=ROOT, text=True, capture_output=True)
    prefix = 'first-' + ('' if label == 'primary' else label + '-')
    log = HERE / (prefix + 'offline.log')
    log.write_text(proc.stdout + proc.stderr)
    if proc.returncode:
        raise ValueError(label + ' offline failed: ' + log.read_text()[-1200:])
    row['offline'] = {'command': ' '.join(offline), 'exit_code': 0,
                      'log': log.name, 'log_sha256': digest(log),
                      'construction_sha256': row['construction_sha256']}
    output = ROOT / '.runtime-work' / (stem + '-compat')
    command = ['.venv-cpu/bin/python', 'runtime.py', 'compatibility', '--manifest',
               MANIFEST.relative_to(ROOT).as_posix(), '--case', case, '--candidate', label,
               '--output', output.relative_to(ROOT).as_posix(), '--library', 'runtime/library',
               '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    command_log = HERE / (prefix + 'compat-command.log')
    command_log.write_text(proc.stdout + proc.stderr)
    if proc.returncode:
        raise ValueError(label + ' compatibility failed: ' + command_log.read_text()[-1200:])
    receipt = HERE / (prefix + 'compatibility.json')
    analysis = HERE / (prefix + 'compat.log')
    negative = HERE / (prefix + 'negative.log')
    shutil.copy2(output / 'compatibility.json', receipt)
    shutil.copy2(output / 'compatibility-analysis.log', analysis)
    shutil.copy2(output / 'negative-analysis.log', negative)
    row['compatibility'] = {'receipt': receipt.name, 'sha256': digest(receipt),
                            'log': analysis.name, 'negative_log': negative.name}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(label, 'offline and positive/negative compatibility passed')
