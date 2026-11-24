"""Exercise current public fixture and raw-only saved finalization for both drafts."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_fixture(recipe, output, env):
    return subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'fixture',
                           '--recipe', str(recipe), '--output', str(output)],
                          cwd=ROOT, env=env, text=True, capture_output=True,
                          timeout=300)


def raw_hashes(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob('*')
            if p.is_file() and 'channels' not in p.relative_to(folder).parts
            and p.name not in ('result.json', 'analysis-report.json')}


def prove(case, scratch, env):
    recipe = HERE / f'current-{case}-recipe.json'
    fixture = scratch / (case + '-fixture')
    built = run_fixture(recipe, fixture, env)
    if built.returncode:
        raise ValueError(built.stdout + built.stderr)
    receipt = json.loads(built.stdout)
    if receipt['recipe_sha256'] != sha(recipe):
        raise ValueError('Recipe digest differs')
    if (fixture / 'channels').exists():
        raise ValueError('Fixture supplies derived channels')
    frames = [json.loads(line) for line in
              (fixture / 'capture/native/frames.jsonl').read_text().splitlines()]
    if len(frames) != 600 or any(not (fixture / 'capture/native' /
                    row['adapter_graph']).is_file() for row in frames):
        raise ValueError('Native graph/frame inventory incomplete')
    construction = json.loads((HERE / 'draft-candidates' / case /
                               'primary/construction.json').read_text())
    for item in construction['files']:
        target = fixture / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    before = raw_hashes(fixture)
    process = subprocess.run([sys.executable, str(fixture / 'finalize.py'),
                              '--attempt', str(fixture),
                              '--output', str(fixture / 'analysis-report.json')],
                             cwd=fixture, env=env, text=True, capture_output=True,
                             timeout=300)
    if process.returncode:
        raise ValueError(process.stdout + process.stderr)
    if raw_hashes(fixture) != before:
        raise ValueError('Saved finalizer rewrote raw acquisition')
    report = json.loads((fixture / 'analysis-report.json').read_text())
    result = json.loads((fixture / 'result.json').read_text())
    if report['original_joins']['frames'] != 600 or len(
        report['derived_channels']['channel_hashes']) != 10:
        raise ValueError('Saved source join or derived channels incomplete')
    if result['accepted'] or result['setup_confirmed'] or result['legal_verdict_claimed']:
        raise ValueError('Synthetic fixture claims physical or legal success')
    negative = scratch / (case + '-missing-raw')
    shutil.copytree(fixture, negative, ignore=shutil.ignore_patterns(
        'channels', 'result.json', 'analysis-report.json'))
    (negative / 'native_samples.jsonl').unlink()
    failed = subprocess.run([sys.executable, str(negative / 'finalize.py'),
                             '--attempt', str(negative),
                             '--output', str(negative / 'analysis-report.json')],
                            cwd=negative, env=env, text=True, capture_output=True,
                            timeout=300)
    if failed.returncode == 0:
        raise ValueError('Missing Native samples accepted')
    changed = json.loads(recipe.read_text())
    changed['sources'][0]['sha256'] = '0' * 64
    changed_path = scratch / (case + '-changed-recipe.json')
    changed_path.write_text(json.dumps(changed, indent=2) + '\n')
    rejected = run_fixture(changed_path, scratch / (case + '-changed-output'), env)
    if rejected.returncode == 0 or 'Fixture source missing/changed' not in rejected.stdout + rejected.stderr:
        raise ValueError('Changed diagnostic digest accepted')
    return {'case': case, 'recipe_sha256': sha(recipe),
            'construction_sha256': sha(HERE / 'draft-candidates' / case /
                                       'primary/construction.json'),
            'fixture_sha256': receipt['fixture_sha256'], 'frames': 600,
            'derived_channels': 10, 'original_sources_unchanged': True,
            'yielded_to_pedestrian': report['measurements'][
                'right_turn_arrow_and_yield']['value']['yielded_to_pedestrian'],
            'analysis_sha256': sha(fixture / 'analysis-report.json'),
            'missing_native_samples_rejected': True,
            'changed_diagnostic_digest_rejected': True,
            'selected': False, 'physical_arrow_observed': False}


if __name__ == '__main__':
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c110919-fixture-saved')
    env['PYTHONPATH'] = os.pathsep.join((str(ROOT / 'runtime/pipeline/scenario_pipeline'),
                                        str(ROOT / 'runtime/pipeline/python'),
                                        str(ROOT / 'runtime/pipeline'),
                                        env.get('PYTHONPATH', '')))
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                     prefix='c110919-current-saved-') as temp:
        cases = [prove(case, Path(temp), env) for case in ('witness_1', 'witness_2')]
    if [row['yielded_to_pedestrian'] for row in cases] != [True, False]:
        raise ValueError('Controlled pedestrian-yield contrast differs')
    result = {'format': 'c110919-current-public-fixture-saved-v1',
              'passed': True, 'cases': cases, 'selected': False,
              'scope': 'synthetic software proof; no physical arrow or lawful status'}
    (HERE / 'current-fixture-saved-proof.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
