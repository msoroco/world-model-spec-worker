"""Run the exact current-runtime offline and source-bound public CPU checks."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNTIME_WORK = ROOT / '.runtime-work'
assert Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve().is_relative_to(RUNTIME_WORK)
MANIFEST = HERE / 'draft-bridge-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def run(command, log):
    with log.open('w') as stream:
        completed = subprocess.run(command, cwd=ROOT, env=os.environ.copy(),
                                   stdout=stream, stderr=subprocess.STDOUT)
    if completed.returncode:
        raise RuntimeError(f'{log} failed ({completed.returncode}): {log.read_text()[-1200:]}')
    return completed.returncode


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1'):
            selected = entry if candidate == 'primary' else entry['candidates'][0]
            output = RUNTIME_WORK / f'c32014-fresh-{suffix}-{candidate}'
            proof = HERE / 'proof' / suffix / candidate
            proof.mkdir(parents=True, exist_ok=True)
            offline_command = [str(ROOT / '.venv-cpu/bin/python'), '-B', str(ROOT / 'runtime.py'),
                               'offline', '--manifest', str(MANIFEST), '--case', case,
                               '--candidate', candidate, '--output', str(output / 'offline'),
                               '--python', str(ROOT / '.venv-cpu/bin/python')]
            offline_log = proof / 'offline.log'
            run(offline_command, offline_log)
            selected['offline'] = {'command': ' '.join(offline_command), 'exit_code': 0,
                                   'construction_sha256': selected['construction_sha256'],
                                   'log': str(offline_log.relative_to(HERE)),
                                   'log_sha256': sha(offline_log)}
            compatibility_command = [str(ROOT / '.venv-cpu/bin/python'), '-B', str(ROOT / 'runtime.py'),
                                     'compatibility', '--manifest', str(MANIFEST), '--case', case,
                                     '--candidate', candidate, '--output', str(output / 'compatibility'),
                                     '--library', str(ROOT / 'runtime/library'), '--validator',
                                     str(RUNTIME_WORK / 'c32014-decoder/.lake/build/bin/adapterCheck')]
            run(compatibility_command, RUNTIME_WORK / f'c32014-fresh-{suffix}-{candidate}.log')
            for source_name, destination_name in [('compatibility.json', 'compatibility.json'),
                                                   ('compatibility-analysis.log', 'analysis.log'),
                                                   ('negative-analysis.log', 'negative-analysis.log')]:
                shutil.copy2(output / 'compatibility' / source_name, proof / destination_name)
            selected['compatibility'] = {
                'receipt': str((proof / 'compatibility.json').relative_to(HERE)),
                'sha256': sha(proof / 'compatibility.json'),
                'log': str((proof / 'analysis.log').relative_to(HERE)),
                'negative_log': str((proof / 'negative-analysis.log').relative_to(HERE))}
            print(f'{suffix} {candidate}: offline and public positive/negative pass', flush=True)
    write(MANIFEST, manifest)


if __name__ == '__main__':
    main()
