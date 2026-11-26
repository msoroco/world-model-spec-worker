"""Run exact offline and current-runtime public compatibility for both candidates."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'draft-execution-manifest.json'
DECODER = ROOT / '.runtime-work/nrs-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(tokens, output):
    result = subprocess.run(tokens, cwd=ROOT, capture_output=True, text=True,
                            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    if result.returncode != 0:
        raise RuntimeError('Command failed: ' + ' '.join(tokens) + '\n' + result.stderr[-2000:])
    return result


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.split('__')[-1]
        proof = HERE / 'proofs' / suffix
        proof.mkdir(parents=True, exist_ok=True)
        for candidate, row in [('primary', entry), ('fallback1', entry['candidates'][0])]:
            short = 'primary' if candidate == 'primary' else 'fallback1'
            offline_out = ROOT / '.runtime-work' / ('c135709-v5-offline-' + suffix + '-' + short)
            command = [sys.executable, str(ROOT / 'runtime.py'), 'offline', '--manifest', str(MANIFEST),
                       '--case', case, '--candidate', candidate, '--output', str(offline_out)]
            run(command, offline_out)
            offline_log = proof / (short + '-offline.log')
            shutil.copyfile(offline_out / 'offline.log', offline_log)
            row['offline'] = {'exit_code': 0, 'construction_sha256': row['construction_sha256'],
                              'command': 'runtime.py offline --case ' + case + ' --candidate ' + candidate,
                              'log': str(offline_log.relative_to(HERE)), 'log_sha256': sha(offline_log)}
            compat_out = ROOT / '.runtime-work' / ('c135709-v5-compat-' + suffix + '-' + short)
            command = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility', '--manifest', str(MANIFEST),
                       '--case', case, '--candidate', candidate, '--output', str(compat_out),
                       '--library', str(ROOT / 'runtime/library'), '--validator', str(DECODER)]
            run(command, compat_out)
            receipt = proof / (short + '-compatibility.json')
            log = proof / (short + '-compatibility-analysis.log')
            negative = proof / (short + '-negative-analysis.log')
            for source, target in ((compat_out / 'compatibility.json', receipt),
                                   (compat_out / 'compatibility-analysis.log', log),
                                   (compat_out / 'negative-analysis.log', negative)):
                shutil.copyfile(source, target)
            row['compatibility'] = {'receipt': str(receipt.relative_to(HERE)), 'sha256': sha(receipt),
                                    'log': str(log.relative_to(HERE)),
                                    'negative_log': str(negative.relative_to(HERE))}
            if candidate == 'primary':
                entry['negative'] = {'log': str(negative.relative_to(HERE)), 'log_sha256': sha(negative)}
            MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
            print(suffix, candidate, 'offline and public compatibility passed', flush=True)


if __name__ == '__main__':
    main()
