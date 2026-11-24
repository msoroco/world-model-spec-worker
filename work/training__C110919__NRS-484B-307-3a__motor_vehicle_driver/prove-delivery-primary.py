"""Run saved-only selected primaries and independent audit positive/negative."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c110919-3a-owner/delivery'
MANIFEST = HERE / 'execution-manifest.json'
VALIDATOR = ROOT / '.runtime-work/c110919-owner104/decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_cli(args, env, timeout=900):
    result = subprocess.run([sys.executable, str(ROOT / 'runtime.py'), *args],
                            cwd=ROOT, env=env, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise ValueError(result.stderr[-2000:] + result.stdout[-2000:])
    return json.loads(result.stdout)


def run(witness):
    if witness not in ('witness_1', 'witness_2'):
        raise ValueError('Unknown exact witness')
    case = HERE.name + '__' + witness
    output = SCRATCH / witness
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT / '.runtime-work'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH))
    recipe = HERE / f'current-v2-{witness}-recipe.json'
    fixture = output / 'fixture'
    source = run_cli(['fixture', '--recipe', str(recipe), '--output', str(fixture)], env)
    attempt = output / 'attempt'
    run_cli(['materialize', '--manifest', str(MANIFEST), '--case', case,
             '--candidate', 'primary', '--output', str(attempt)], env)
    for path in fixture.iterdir():
        target = attempt / path.name
        if target.exists():
            raise ValueError('Fixture shadows selected construction')
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copy2(path, target)
    originals = {path.relative_to(attempt).as_posix(): sha(path)
                 for path in attempt.rglob('*') if path.is_file()}
    receipt = run_cli(['process-saved', '--manifest', str(MANIFEST), '--case', case,
                       '--attempt', str(attempt), '--output', str(output / 'processed'),
                       '--library', str(ROOT / 'runtime/library'),
                       '--validator', str(VALIDATOR)], env)
    if (not receipt['recorded_only'] or not receipt['originals_preserved']
            or receipt['missing_evidence'] or receipt['timestamp_joins']['frames'] != 600):
        raise ValueError('Selected saved processing incomplete')
    if originals != {path.relative_to(attempt).as_posix(): sha(path)
                     for path in attempt.rglob('*') if path.is_file()}:
        raise ValueError('Selected processing changed original source')
    processing = Path(receipt['version']) / 'processing.json'
    script = HERE / 'delivery_audit.py'
    positive = [sys.executable, str(script), '--case', case, '--candidate', 'primary',
                '--attempt', str(attempt), '--processing', str(processing),
                '--output', str(output / 'positive.json'), '--diagnostic']
    result = subprocess.run(positive, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=60)
    positive_log = HERE / f'current-delivery-{witness}-positive.log'
    positive_log.write_text(result.stdout.rstrip() + '\n')
    if result.returncode or not json.loads((output / 'positive.json').read_text()).get('diagnostic_only'):
        raise ValueError('Diagnostic delivery positive failed: ' + result.stdout[-1000:])
    negative_attempt = output / 'negative-attempt'
    shutil.copytree(attempt, negative_attempt, copy_function=os.link)
    (negative_attempt / 'road_geometry.json').unlink()
    negative = [sys.executable, str(script), '--case', case, '--candidate', 'primary',
                '--attempt', str(negative_attempt), '--processing', str(processing),
                '--output', str(output / 'negative.json'), '--diagnostic']
    result = subprocess.run(negative, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=60)
    negative_log = HERE / f'current-delivery-{witness}-negative.log'
    negative_log.write_text(result.stdout.rstrip() + '\n')
    if result.returncode == 0 or 'Missing original source: road_geometry.json' not in result.stdout:
        raise ValueError('Missing-road acceptance negative failed')
    return {'case_id': case, 'fixture_sha256': source['fixture_sha256'],
            'positive_log_sha256': sha(positive_log), 'negative_log_sha256': sha(negative_log),
            'processing_sha256': sha(processing), 'originals_preserved': True}


if __name__ == '__main__':
    print(json.dumps(run(sys.argv[1])))
