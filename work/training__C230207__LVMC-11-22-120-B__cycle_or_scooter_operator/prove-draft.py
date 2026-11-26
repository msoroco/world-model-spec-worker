"""Reproduce the two-case CPU construction and saved-source draft proofs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work'
PYTHON = ROOT / '.venv-cpu/bin/python'


def run(name, args, scratch):
    env = os.environ.copy()
    env.update(SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch / 'pipeline-output'),
               TMPDIR=str(scratch), PYTHONDONTWRITEBYTECODE='1',
               PYTHONPATH=str(HERE / 'native'))
    completed = subprocess.run([str(PYTHON), '-B', *args], cwd=ROOT, env=env,
                               text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, check=False)
    text = completed.stdout.rstrip('\n') + '\n'
    staged = scratch / name
    staged.write_text(text)
    staged.replace(HERE / name)
    if completed.returncode:
        raise RuntimeError(f'{name}: exit {completed.returncode}: {text[-600:]}')
    return {'command': '.venv-cpu/bin/python -B ' + ' '.join(args),
            'exit_code': 0, 'log': name,
            'sha256': hashlib.sha256((HERE / name).read_bytes()).hexdigest()}


def main():
    SCRATCH.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='c230207-proof-', dir=SCRATCH) as temporary:
        scratch = Path(temporary)
        results = [run('native-tests-current.log', ['-m', 'unittest', 'discover',
            '-s', str(HERE / 'native/tests'), '-v'], scratch),
            run('saved-source-proof-current.log', [str(HERE / 'prove-measure.py')], scratch)]
        for suffix in ('probe_01', 'probe_02'):
            case_id = HERE.name + '__' + suffix
            results.append(run(f'proof-offline-{suffix}-current.log', [
                'runtime.py', 'offline', '--manifest', str(HERE / 'draft-signed-roadway-manifest.json'),
                '--case', case_id, '--output', str(scratch / ('offline-' + suffix)),
                '--python', str(PYTHON)], scratch))
        print(json.dumps({'passed': True, 'tests': results}, indent=2))


if __name__ == '__main__':
    main()
