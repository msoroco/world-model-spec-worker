"""Run the six exact selected bundles against pinned CPU offline/compatibility paths."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'selected-30s-draft-execution-manifest.json'
SCRATCH = REPO / '.runtime-work/c422978-selected'
VALIDATOR = SCRATCH / 'validator/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if not VALIDATOR.is_file():
        raise ValueError('Build pinned validator in .runtime-work first')
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(SCRATCH)
    for entry in manifest['cases']:
        witness = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ['primary', *[x['id'] for x in entry['candidates']]]:
            key = witness + '-' + candidate
            target = HERE / 'selected-30s/proof' / witness / candidate
            target.mkdir(parents=True, exist_ok=True)
            offline_out = SCRATCH / (key + ('-offline-v2' if key == 'witness_1-primary' else '-offline-proof'))
            compat_out = SCRATCH / (key + ('-compat-v3' if key == 'witness_1-primary' else '-compat-proof'))
            commands = [
                ['offline', '--manifest', str(MANIFEST), '--case', entry['case_id'],
                 '--candidate', candidate, '--output', str(offline_out), '--python', sys.executable],
                ['compatibility', '--manifest', str(MANIFEST), '--case', entry['case_id'],
                 '--candidate', candidate, '--output', str(compat_out),
                 '--library', str(REPO / 'runtime/library'), '--validator', str(VALIDATOR)],
            ]
            if not offline_out.exists():
                with (target / 'build-command.log').open('w', encoding='utf-8') as stream:
                    result = subprocess.run([sys.executable, str(REPO / 'runtime.py'), *commands[0]],
                                            cwd=REPO, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                            timeout=300)
                if result.returncode:
                    raise ValueError(f'Offline failed: {key}')
            else:
                if not (target / 'build-command.log').exists():
                    (target / 'build-command.log').write_text('Reused exact selected offline diagnostic\n')
            if not compat_out.exists():
                with (target / 'compat-command.log').open('w', encoding='utf-8') as stream:
                    result = subprocess.run([sys.executable, str(REPO / 'runtime.py'), *commands[1]],
                                            cwd=REPO, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                            timeout=360)
                if result.returncode:
                    raise ValueError(f'Compatibility failed: {key}')
            for source, name in [(offline_out / 'offline.log', 'offline.log'),
                                 (compat_out / 'compatibility.json', 'compatibility.json'),
                                 (compat_out / 'compatibility-analysis.log', 'positive.log'),
                                 (compat_out / 'negative-analysis.log', 'negative.log')]:
                if not source.is_file():
                    raise ValueError(f'Missing exact receipt: {source}')
                shutil.copy2(source, target / name)
            receipt = json.loads((target / 'compatibility.json').read_text())
            assert receipt['passed'] and receipt['construction_sha256'] == (
                entry['construction_sha256'] if candidate == 'primary' else
                next(x['construction_sha256'] for x in entry['candidates'] if x['id'] == candidate))
            rows.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                         'offline_log_sha256': sha(target / 'offline.log'),
                         'compatibility_receipt_sha256': sha(target / 'compatibility.json'),
                         'positive_log_sha256': sha(target / 'positive.log'),
                         'negative_log_sha256': sha(target / 'negative.log')})
            print(json.dumps({'selected_case': key, 'passed': True}), flush=True)
    path = HERE / 'selected-30s/proof/index.json'
    path.write_text(json.dumps({'format': 'c422978-selected-30s-compat-proof-v1',
                                'rows': rows, 'passed': True,
                                'original_native_observed': False}, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'selected_receipts': len(rows), 'index_sha256': sha(path)}))


if __name__ == '__main__':
    main()
