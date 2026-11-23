"""Current-runtime 600-frame saved finalization on diagnostic JSON graph sources."""
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


def run_finalizer(folder, env):
    return subprocess.run([sys.executable, str(HERE / 'native/finalize.py'),
                           '--attempt', str(folder),
                           '--output', str(folder / 'analysis-report.json')],
                          cwd=folder, env=env, capture_output=True, text=True,
                          timeout=300)


def source_hashes(folder):
    return {path.relative_to(folder).as_posix(): sha(path) for path in folder.rglob('*')
            if path.is_file() and path.name not in ('result.json', 'analysis-report.json')
            and 'channels' not in path.relative_to(folder).parts}


def prove(suffix, scratch, env):
    case = HERE.name + '__' + suffix
    recipe = HERE / ('current-' + suffix + '-recipe.json')
    fixture = scratch / (suffix + '-fixture')
    command = [sys.executable, str(ROOT / 'runtime.py'), 'fixture',
               '--recipe', str(recipe), '--output', str(fixture)]
    built = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                           text=True, timeout=300)
    if built.returncode:
        raise RuntimeError(built.stdout + built.stderr)
    construction = json.loads((HERE / 'draft-bundles' / suffix /
                               'primary/construction.json').read_text())
    config = next(item['content'] for item in construction['files']
                  if item['path'] == 'config.json')
    (fixture / 'config.json').write_text(config)
    (fixture / 'road.xodr').write_bytes((HERE / 'native/road.xodr').read_bytes())
    for old, new in (('reference_corner.mkv', 'crosswalk_side.mkv'),
                     ('driver_reference.mkv', 'display_close.mkv')):
        (fixture / old).rename(fixture / new)
    before = source_hashes(fixture)
    positive = run_finalizer(fixture, env)
    if positive.returncode:
        raise RuntimeError(positive.stdout + positive.stderr)
    if source_hashes(fixture) != before:
        raise RuntimeError('Saved finalization changed retained acquisition')
    report = json.loads((fixture / 'analysis-report.json').read_text())
    result = json.loads((fixture / 'result.json').read_text())
    if result['accepted'] or result['legal_verdict_claimed'] or result['setup_confirmed']:
        raise RuntimeError('Synthetic source claimed physical or legal completion')
    if report['original_joins']['frames'] != 600 or len(report['derived_channel_sha256']) != 5:
        raise RuntimeError('Full source join or derived channels missing')
    for name, digest in report['derived_channel_sha256'].items():
        if sha(fixture / 'channels' / (name + '.jsonl')) != digest:
            raise RuntimeError('Derived channel digest mismatch')
    negatives = {}
    for label, removed, expected in (
        ('missing-samples', 'steady-samples.jsonl', 'Missing required source: steady-samples.jsonl'),
        ('missing-video', 'overview.mkv', 'Missing required source: overview.mkv'),
    ):
        target = scratch / (suffix + '-' + label)
        shutil.copytree(fixture, target, ignore=shutil.ignore_patterns(
            'result.json', 'analysis-report.json', 'channels'))
        (target / removed).unlink()
        failed = run_finalizer(target, env)
        if failed.returncode == 0 or expected not in failed.stdout + failed.stderr:
            raise RuntimeError(label + ' negative failed: ' + failed.stdout + failed.stderr)
        negatives[label] = {'exit_code': failed.returncode, 'expected_error': expected}
    return {'case_id': case, 'recipe_sha256': sha(recipe),
            'construction_sha256': sha(HERE / 'draft-bundles' / suffix /
                                       'primary/construction.json'),
            'source_frames': 600, 'camera_decodes': 4,
            'derived_channel_sha256': report['derived_channel_sha256'],
            'analysis_report_sha256': sha(fixture / 'analysis-report.json'),
            'result_sha256': sha(fixture / 'result.json'),
            'source_unchanged': True, 'negatives': negatives,
            'scope': 'synthetic saved-only finalizer proof; no physical signal or acceptance'}


if __name__ == '__main__':
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c10316-d4-saved-proof')
    env['PYTHONPATH'] = os.pathsep.join((str(ROOT / 'runtime/pipeline/scenario_pipeline'),
                                        str(ROOT / 'runtime/pipeline/python'),
                                        str(ROOT / 'runtime/pipeline'),
                                        str(HERE / 'native'), env.get('PYTHONPATH', '')))
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                     prefix='c10316-d4-current-saved-') as temp:
        scratch = Path(temp)
        rows = [prove(suffix, scratch, env) for suffix in ('witness_1', 'witness_2')]
    summary = {'format': 'c10316-d4-current-saved-steady-v1', 'passed': True,
               'cases': rows, 'selected': False}
    (HERE / 'current-saved-steady-proof.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
