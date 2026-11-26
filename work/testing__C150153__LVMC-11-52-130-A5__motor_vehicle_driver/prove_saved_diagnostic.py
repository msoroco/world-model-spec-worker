"""Exercise recorded-only processing on an exact synthetic elevator case."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.source-bound-diagnostic.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(*args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
                             *map(str, args)], cwd=ROOT, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
    if result.returncode:
        raise ValueError(result.stdout[-2500:])
    return result.stdout


def prove(kind='west_inside', scratch_suffix=''):
    case = HERE.name + '__' + kind
    manifest = json.loads(MANIFEST.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == case)
    base = ROOT / '.runtime-work/c150153-owner'
    suffix = kind.replace('_', '-') + scratch_suffix
    attempt = base / ('saved-source-' + suffix)
    fixture = base / ('saved-fixture-' + suffix)
    output = base / ('saved-processing-' + suffix)
    if any(path.exists() for path in (attempt, fixture, output)):
        raise ValueError('Choose fresh synthetic saved-proof paths')
    command('materialize', '--manifest', MANIFEST, '--case', case, '--output', attempt)
    command('fixture', '--recipe', ROOT / entry['fixture_recipe'], '--output', fixture)
    for path in fixture.iterdir():
        target = attempt / path.name
        if target.exists():
            raise ValueError('Synthetic fixture shadows selected construction: ' + path.name)
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copy2(path, target)
    seal_path = attempt / 'capture-seal.json'
    seal = json.loads(seal_path.read_text())
    if seal.get('provenance_kind') != 'synthetic_fixture':
        raise ValueError('Only synthetic protocol fixture may use this proof')
    seal['events'] = ['capture_finished', 'encoders_closed', 'restoration_verified']
    seal['native_revision'] = {'construction_sha256': sha(attempt / 'construction.json'),
                               'runner_sha256': sha(attempt / 'runner.py')}
    seal_path.write_text(json.dumps(seal, indent=2) + '\n')
    sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
    from worker_exchange.saved_processing import record_native_exit
    record_native_exit(attempt)
    command('process-saved', '--manifest', MANIFEST, '--case', case,
            '--attempt', attempt, '--output', output, '--library', ROOT / 'runtime/library',
            '--validator', base / 'validator/.lake/build/bin/adapterCheck')
    receipt = output / 'v0001/processing.json'
    value = json.loads(receipt.read_text())
    if not (value['passed'] and value['recorded_only'] and value['originals_preserved']
            and value['case_id'] == case and value['missing_evidence'] is False):
        raise ValueError('Saved diagnostic proof incomplete')
    retained = HERE / ('cpu-saved-' + kind + '.json')
    shutil.copy2(receipt, retained)
    print(json.dumps({'case_id': case, 'receipt': str(retained.relative_to(ROOT)),
                      'sha256': sha(retained), 'recorded_only': True,
                      'physical_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    prove(sys.argv[1] if len(sys.argv) > 1 else 'west_inside',
          sys.argv[2] if len(sys.argv) > 2 else '')
