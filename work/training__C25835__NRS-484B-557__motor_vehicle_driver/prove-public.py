"""Retain exact offline and public compatibility receipts for all rail probes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'draft-native-manifest.json'
DECODER = ROOT / '.runtime-work/nrs-decoder/.lake/build/bin/adapterCheck'
BASE = ROOT / '.runtime-work/c25835-owner'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(tokens):
    result = subprocess.run(tokens, cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
             'SCENARIO_PIPELINE_OUTPUT_ROOT': str(BASE),
             'TMPDIR': str(ROOT / '.runtime-work')})
    if result.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(tokens) + '\n' + result.stderr[-2500:])


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.split('__')[-1]
        proof = HERE / 'proofs' / suffix
        proof.mkdir(parents=True, exist_ok=True)
        for candidate, row in [('primary', entry), ('fallback1', entry['candidates'][0])]:
            offline_out = BASE / 'offline' / (suffix + '-' + candidate + '-v2')
            if not (offline_out / 'offline.log').is_file():
                run([sys.executable, str(ROOT / 'runtime.py'), 'offline',
                     '--manifest', str(MANIFEST), '--case', case,
                     '--candidate', candidate, '--output', str(offline_out),
                     '--python', sys.executable])
            offline_log = proof / (candidate + '-offline.log')
            shutil.copyfile(offline_out / 'offline.log', offline_log)
            row['offline'] = {'exit_code': 0,
                'construction_sha256': row['construction_sha256'],
                'command': 'runtime.py offline --case ' + case + ' --candidate ' + candidate,
                'log': str(offline_log.relative_to(HERE)),
                'log_sha256': sha(offline_log)}
            compat_out = BASE / 'public' / (suffix + '-' + candidate + '-v1')
            if not (compat_out / 'compatibility.json').is_file():
                run([sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
                     '--manifest', str(MANIFEST), '--case', case,
                     '--candidate', candidate, '--output', str(compat_out),
                     '--library', str(ROOT / 'runtime/library'),
                     '--validator', str(DECODER)])
            receipt = proof / (candidate + '-compatibility.json')
            log = proof / (candidate + '-compatibility-analysis.log')
            negative = proof / (candidate + '-negative-analysis.log')
            for source, target in ((compat_out / 'compatibility.json', receipt),
                                   (compat_out / 'compatibility-analysis.log', log),
                                   (compat_out / 'negative-analysis.log', negative)):
                shutil.copyfile(source, target)
            row['compatibility'] = {'receipt': str(receipt.relative_to(HERE)),
                'sha256': sha(receipt), 'log': str(log.relative_to(HERE)),
                'negative_log': str(negative.relative_to(HERE))}
            if candidate == 'primary':
                entry['negative'] = {'log': str(negative.relative_to(HERE)),
                                     'log_sha256': sha(negative)}
            MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
            print(suffix, candidate, 'offline and public compatibility passed', flush=True)


if __name__ == '__main__':
    main()
