"""Run recorded-only saved processing on both pinned diagnostic sources."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'current-v2-probe-manifest.json'
SCRATCH = ROOT / '.runtime-work/c110919-3a-owner/saved-matrix'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, env):
    completed = subprocess.run([sys.executable, str(ROOT / 'runtime.py')] + args,
                               cwd=ROOT, env=env, text=True, capture_output=True,
                               timeout=600)
    if completed.returncode:
        raise ValueError(completed.stdout[-2000:] + completed.stderr[-2000:])
    return json.loads(completed.stdout)


def stage(case, folder, env, candidate):
    case_id = HERE.name + '__' + case
    recipe = HERE / f'current-v2-{case}-recipe.json'
    fixture = folder / (case + '-fixture')
    source = command(['fixture', '--recipe', str(recipe), '--output', str(fixture)], env)
    attempt = folder / (case + '-attempt')
    command(['materialize', '--manifest', str(MANIFEST), '--case', case_id,
             '--candidate', candidate, '--output', str(attempt)], env)
    for path in fixture.iterdir():
        target = attempt / path.name
        if target.exists():
            raise ValueError('Fixture shadows construction: ' + path.name)
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copy2(path, target)
    return case_id, attempt, source


def prove(case, folder, env, candidate):
    case_id, attempt, source = stage(case, folder, env, candidate)
    original = {p.relative_to(attempt).as_posix(): sha(p)
                for p in attempt.rglob('*') if p.is_file()}
    receipt = command(['process-saved', '--manifest', str(MANIFEST), '--case', case_id,
                       '--attempt', str(attempt), '--output', str(folder / (case + '-saved')),
                       '--library', str(ROOT / 'runtime/library'),
                       '--validator', str(ROOT / '.runtime-work/c110919-owner104/decoder/.lake/build/bin/adapterCheck')], env)
    if receipt['missing_evidence'] or not receipt['recorded_only'] or not receipt['originals_preserved']:
        raise ValueError('Positive saved processing was incomplete')
    if original != {p.relative_to(attempt).as_posix(): sha(p)
                    for p in attempt.rglob('*') if p.is_file()}:
        raise ValueError('Saved processing changed original acquisition')
    negative = folder / (case + '-negative')
    shutil.copytree(attempt, negative)
    (negative / 'road_geometry.json').unlink()
    missing = subprocess.run([sys.executable, str(negative / 'finalize.py'),
                              '--attempt', str(negative),
                              '--output', str(negative / 'analysis-report.json')],
                             cwd=negative, env=env, text=True, capture_output=True,
                             timeout=300)
    if missing.returncode == 0 or 'Missing required source: road_geometry.json' not in missing.stdout + missing.stderr:
        raise ValueError('Missing geometry was accepted by saved analyzer')
    result = json.loads(Path(receipt['result']).read_text())
    return {'case_id': case_id, 'candidate_id': candidate,
            'fixture_sha256': source['fixture_sha256'],
            'recipe_sha256': sha(HERE / f'current-v2-{case}-recipe.json'),
            'processing_sha256': sha(Path(receipt['version']) / 'processing.json'),
            'result_sha256': receipt['result_sha256'],
            'frames': receipt['timestamp_joins']['frames'],
            'final_video_frames': receipt['final_video_checks']['frames'],
            'yielded_to_pedestrian': result['measured_values']['turn_yield']['yielded_to_pedestrian'],
            'originals_preserved': True, 'missing_road_geometry_rejected': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', default='primary', choices=('primary', 'fallback1', 'fallback3'))
    args = parser.parse_args()
    SCRATCH.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(SCRATCH)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['TMPDIR'] = str(SCRATCH)
    with tempfile.TemporaryDirectory(dir=SCRATCH, prefix='saved-proof-') as temp:
        labels = ('witness_1', 'witness_2')
        cases = [prove(case, Path(temp), env, args.candidate) for case in labels]
    if [case['yielded_to_pedestrian'] for case in cases] != [True, False]:
        raise ValueError('Controlled witness variable differs')
    result = {'format': 'c110919-current-v2-recorded-only-saved-proof',
              'passed': True, 'cases': cases, 'selected': False,
              'scope': 'Synthetic source-hashed software proof; physical arrow glyph and acceptance unproved'}
    filename = 'current-runtime-' + args.candidate + '-saved-proof.json'
    (HERE / filename).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
