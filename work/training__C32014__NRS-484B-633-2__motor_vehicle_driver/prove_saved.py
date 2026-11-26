"""Test exact selected recorded-only finalization without Native replay."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNTIME_WORK = ROOT / '.runtime-work'
assert Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve().is_relative_to(RUNTIME_WORK)
MANIFEST = HERE / 'execution-manifest.json'
PYTHON = ROOT / '.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    with Path(log).open('w') as stream:
        complete = subprocess.run(command, cwd=ROOT, env=os.environ.copy(),
                                  stdout=stream, stderr=subprocess.STDOUT)
    if complete.returncode:
        raise RuntimeError(f'{log} failed: {Path(log).read_text()[-1600:]}')


def main():
    for suffix in ('probe_01', 'probe_02'):
        case = HERE.name + '__' + suffix
        fixture = RUNTIME_WORK / ('c32014-saved-fixture-' + suffix[-2:])
        attempt = RUNTIME_WORK / ('c32014-final-attempt-' + suffix[-2:])
        output = RUNTIME_WORK / ('c32014-final-output-' + suffix[-2:])
        if attempt.exists():
            raise ValueError('Retain previous exact attempt; choose a fresh proof output')
        materialize = [str(PYTHON), '-B', str(ROOT / 'runtime.py'), 'materialize',
                       '--manifest', str(MANIFEST), '--case', case, '--output', str(attempt)]
        run(materialize, RUNTIME_WORK / ('c32014-final-materialize-' + suffix[-2:] + '.log'))
        for source in fixture.iterdir():
            destination = attempt / source.name
            if destination.exists():
                raise ValueError('Source shadows selected package: ' + source.name)
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)
        processing = [str(PYTHON), '-B', str(ROOT / 'runtime.py'), 'process-saved',
                      '--manifest', str(MANIFEST), '--case', case, '--attempt', str(attempt),
                      '--output', str(output), '--library', str(ROOT / 'runtime/library'),
                      '--validator', str(RUNTIME_WORK / 'c32014-decoder/.lake/build/bin/adapterCheck')]
        log = HERE / 'proof' / suffix / 'saved-final.log'
        run(processing, log)
        receipt = json.loads((output / 'v0001/processing.json').read_text())
        if (receipt.get('passed') is not True or receipt.get('recorded_only') is not True
                or receipt.get('originals_preserved') is not True
                or receipt.get('final_video_checks', {}).get('frames') != 600):
            raise ValueError('Recorded-only proof did not preserve and fully decode the exact source')
        print(json.dumps({'case_id': case, 'saved_log_sha256': sha(log),
                          'processing_sha256': sha(output / 'v0001/processing.json')}), flush=True)


if __name__ == '__main__':
    main()
