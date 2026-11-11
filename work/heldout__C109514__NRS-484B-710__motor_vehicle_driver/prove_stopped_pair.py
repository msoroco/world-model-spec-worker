"""Prove the 499 and 501 ft stopped drive-to cases and risk variants."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
for target in (499, 501):
 CASE = HERE.name + '__stopped_drive_to_' + str(target) + 'ft'
 DEST = HERE / 'cases' / ('stopped_drive_to_' + str(target) + 'ft')
 entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
 for candidate, row in [('primary', entry), *[(c['id'], c) for c in entry['candidates']]]:
    name = 'c109514-stopped-drive-' + str(target) + '-' + candidate
    command = ['.venv-cpu/bin/python', 'runtime.py', 'offline', '--manifest',
               str(MANIFEST.relative_to(ROOT)), '--case', CASE, '--candidate', candidate,
               '--output', '.runtime-work/' + name + '-offline',
               '--python', str(ROOT / '.venv-cpu/bin/python')]
    finished = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    log = DEST / (candidate + '-offline.log')
    log.write_text(finished.stdout + finished.stderr)
    if finished.returncode:
        raise ValueError(candidate + ' offline failed: ' + log.read_text()[-1000:])
    row['offline'] = {'command': ' '.join(command), 'exit_code': 0,
                      'log': log.relative_to(HERE).as_posix(),
                      'log_sha256': digest(log),
                      'construction_sha256': row['construction_sha256']}
    output = ROOT / '.runtime-work' / (name + '-compat')
    command = ['.venv-cpu/bin/python', 'runtime.py', 'compatibility', '--manifest',
               str(MANIFEST.relative_to(ROOT)), '--case', CASE, '--candidate', candidate,
               '--output', str(output.relative_to(ROOT)), '--library', 'runtime/library',
               '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    finished = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    command_log = DEST / (candidate + '-compat-command.log')
    command_log.write_text(finished.stdout + finished.stderr)
    if finished.returncode:
        raise ValueError(candidate + ' compatibility failed: ' + command_log.read_text()[-1000:])
    analysis_log = DEST / (candidate + '-compat.log')
    negative_log = DEST / (candidate + '-negative.log')
    receipt = DEST / (candidate + '-compatibility.json')
    shutil.copy2(output / 'compatibility-analysis.log', analysis_log)
    shutil.copy2(output / 'negative-analysis.log', negative_log)
    shutil.copy2(output / 'compatibility.json', receipt)
    row['compatibility'] = {'receipt': receipt.relative_to(HERE).as_posix(),
                            'sha256': digest(receipt),
                            'log': analysis_log.relative_to(HERE).as_posix(),
                            'negative_log': negative_log.relative_to(HERE).as_posix()}
    if candidate == 'primary':
        entry['negative'] = {'log': negative_log.relative_to(HERE).as_posix()}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(candidate + ' offline and compatibility passed')
