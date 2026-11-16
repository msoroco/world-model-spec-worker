"""Run pinned four-camera CPU proof paths for signed-case fallbacks."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PYTHON = REPO / '.venv-cpu/bin/python'
CASE = ROOT.name + '__ordinary_red_signed'
VALIDATOR = REPO / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'


def command(label, args):
    log = ROOT / ('update023-signed-' + label + '.log')
    with log.open('w') as out:
        result = subprocess.run([str(PYTHON), *map(str, args)], cwd=REPO,
                                stdout=out, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'{label} exited {result.returncode}; inspect {log}')


def prove():
    command('fallbacks-build', [ROOT / 'build-signed-fallbacks.py'])
    for candidate in ('fallback1', 'fallback2', 'fallback3'):
        command(candidate + '-diagnostic-build',
                [ROOT / 'build-signed-diagnostic.py', candidate])
        manifest = ROOT / ('execution-manifest-diagnostic-ordinary_red_signed-' +
                           candidate + '.json')
        prefix = REPO / '.runtime-work' / ('C150142-u023-signed-' + candidate)
        common = ['--manifest', manifest, '--case', CASE, '--candidate', candidate]
        command(candidate + '-offline',
                [REPO / 'runtime.py', 'offline', *common,
                 '--output', str(prefix) + '-offline'])
        command(candidate + '-compat',
                [REPO / 'runtime.py', 'compatibility', *common,
                 '--output', str(prefix) + '-compat',
                 '--library', REPO / 'runtime/pipeline/library',
                 '--validator', VALIDATOR])
        command(candidate + '-prepare',
                [ROOT / 'prepare-selected-saved.py',
                 '--witness', 'ordinary_red_signed', '--candidate', candidate,
                 '--attempt', str(prefix) + '-attempt',
                 '--fixture', str(prefix) + '-fixture'])
        command(candidate + '-saved',
                [REPO / 'runtime.py', 'process-saved',
                 '--manifest', manifest, '--case', CASE,
                 '--attempt', str(prefix) + '-attempt',
                 '--output', str(prefix) + '-saved',
                 '--library', REPO / 'runtime/pipeline/library',
                 '--validator', VALIDATOR])
    return {'case_id': CASE, 'fallbacks_proved': 3}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
