"""Reprove both ordinary witnesses after signed-case plan selection."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PYTHON = REPO / '.venv-cpu/bin/python'
CASE = ROOT.name
VALIDATOR = REPO / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'


def command(label, args):
    log = ROOT / ('update023-' + label + '.log')
    with log.open('w') as out:
        run = subprocess.run([str(PYTHON), *map(str, args)], cwd=REPO,
                             stdout=out, stderr=subprocess.STDOUT)
    if run.returncode:
        raise RuntimeError(f'{label} exited {run.returncode}; inspect {log}')


def refresh():
    command('ordinary-native-build', [ROOT / 'native/build.py'])
    command('ordinary-native-check', [ROOT / 'native/check.py'])
    for witness in ('reference', 'contrast'):
        command(witness + '-build-primary', [ROOT / 'build-selected-primary.py', witness])
        command(witness + '-build-fallbacks', [ROOT / 'build-selected-fallbacks.py', witness])
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            command(witness + '-' + candidate + '-build-diagnostic',
                    [ROOT / 'build-selected-diagnostic.py', candidate, witness])
            suffix = '' if candidate == 'primary' else '-' + candidate
            manifest = ROOT / ('execution-manifest-diagnostic-' + witness + suffix + '.json')
            prefix = REPO / '.runtime-work' / (
                'C150142-u023-' + witness + '-' + candidate)
            common = ['--manifest', manifest, '--case', CASE + '__' + witness,
                      '--candidate', candidate]
            command(witness + '-' + candidate + '-offline',
                    [REPO / 'runtime.py', 'offline', *common,
                     '--output', str(prefix) + '-offline'])
            command(witness + '-' + candidate + '-compat',
                    [REPO / 'runtime.py', 'compatibility', *common,
                     '--output', str(prefix) + '-compat',
                     '--library', REPO / 'runtime/pipeline/library',
                     '--validator', VALIDATOR])
            command(witness + '-' + candidate + '-prepare',
                    [ROOT / 'prepare-selected-saved.py', '--witness', witness,
                     '--candidate', candidate, '--attempt', str(prefix) + '-attempt',
                     '--fixture', str(prefix) + '-fixture'])
            command(witness + '-' + candidate + '-saved',
                    [REPO / 'runtime.py', 'process-saved',
                     '--manifest', manifest, '--case', CASE + '__' + witness,
                     '--attempt', str(prefix) + '-attempt',
                     '--output', str(prefix) + '-saved',
                     '--library', REPO / 'runtime/pipeline/library',
                     '--validator', VALIDATOR])
    command('bind-current', [ROOT / 'bind-selected-current.py'])
    command('audit-current', [ROOT / 'audit-selected-current.py'])
    return {'case_id': CASE, 'ordinary_candidates_reproved': 8}


if __name__ == '__main__':
    print(json.dumps(refresh(), sort_keys=True))
