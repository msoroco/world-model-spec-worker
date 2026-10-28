"""Run every exact speed case through pinned offline and compatibility gates."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PYTHON = REPO / '.venv-cpu/bin/python'
RUNTIME = REPO / 'runtime/main-pipeline-v1'
VALIDATOR = REPO / '.runtime-work/decoder-v3/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log):
    with log.open('x') as output:
        completed = subprocess.run(command, cwd=REPO, stdout=output,
                                   stderr=subprocess.STDOUT, text=True)
    return {'command': ' '.join(str(x) for x in command),
            'exit_code': completed.returncode,
            'log': str(log.relative_to(ROOT)), 'sha256': sha(log)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prefix', required=True)
    args = parser.parse_args()
    attempts = REPO / '.runtime-work' / args.prefix
    attempts.mkdir(parents=True, exist_ok=False)
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    fixture = ROOT / 'fixture-diagnostic'
    logs = ROOT / 'tests'
    results = ROOT / 'results'
    results.mkdir(exist_ok=True)
    checks = []
    for entry in manifest['cases']:
        ident = entry['case_id']
        label = ident.rsplit('__', 1)[-1]
        offline_dir = attempts / (label + '-offline')
        compatibility_dir = attempts / (label + '-compatibility')
        offline = [str(PYTHON), str(REPO / 'runtime.py'), 'offline',
                   '--manifest', str(manifest_path), '--case', ident,
                   '--output', str(offline_dir)]
        compatible = [str(PYTHON), str(REPO / 'runtime.py'), 'compatibility',
                      '--manifest', str(manifest_path), '--case', ident,
                      '--fixture', str(fixture), '--output', str(compatibility_dir),
                      '--library', str(RUNTIME / 'library'), '--validator', str(VALIDATOR)]
        offline_record = run(offline, logs / (label + '.offline-command.log'))
        if offline_dir.joinpath('offline.log').is_file():
            shutil.copyfile(offline_dir / 'offline.log', logs / (label + '.offline.log'))
            offline_record['runner_log'] = 'tests/' + label + '.offline.log'
            offline_record['runner_log_sha256'] = sha(logs / (label + '.offline.log'))
        compatibility_record = run(compatible, logs / (label + '.compatibility-command.log'))
        if compatibility_record['exit_code'] == 0:
            receipt = results / (label + '.compatibility.json')
            analysis_log = results / (label + '.analysis.log')
            shutil.copyfile(compatibility_dir / 'compatibility.json', receipt)
            shutil.copyfile(compatibility_dir / 'compatibility-analysis.log', analysis_log)
            entry['compatibility'] = {'receipt': str(receipt.relative_to(ROOT)),
                'sha256': sha(receipt),
                'fixture': str(fixture.relative_to(REPO)),
                'log': str(analysis_log.relative_to(ROOT))}
        checks.append({'case_id': ident, 'offline': offline_record,
                       'compatibility': compatibility_record,
                       'receipt': entry.get('compatibility')})
        print(label, offline_record['exit_code'], compatibility_record['exit_code'], flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    (ROOT / 'checks.json').write_text(json.dumps({'format': 'speed-exact-case-checks-v1',
        'checks': checks}, indent=2) + '\n')


if __name__ == '__main__':
    main()
