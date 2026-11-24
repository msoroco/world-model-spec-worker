"""Exercise the pinned JSON-graph fixture path and a changed-source rejection."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(recipe, output, env):
    return subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'fixture',
                           '--recipe', str(recipe), '--output', str(output)],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)


def prove(suffix):
    recipe_path = HERE / ('current-' + suffix + '-recipe.json')
    spec_path = HERE / ('current-' + suffix + '-diagnostic.json')
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c10316-d4-recipe-proof')
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c10316-d4-v2-proof-') as temp:
        scratch = Path(temp)
        positive = scratch / 'positive'
        passed = run(recipe_path, positive, env)
        if passed.returncode:
            raise AssertionError(passed.stdout + passed.stderr)
        receipt = json.loads(passed.stdout)
        assert receipt['recipe_sha256'] == sha(recipe_path)
        assert len((positive / 'exception-samples.jsonl').read_text().splitlines()) == 600
        assert len((positive / 'capture/native/frames.jsonl').read_text().splitlines()) == 600
        assert not (positive / 'channels').exists()
        frames = [json.loads(line) for line in
                  (positive / 'capture/native/frames.jsonl').read_text().splitlines()]
        assert all(row['base'].endswith('.adapter.json') and
                   (positive / 'capture/native' / row['base']).is_file() for row in frames)
        evidence = [json.loads(line) for line in
                    (positive / 'capture/evidence.jsonl').read_text().splitlines()]
        assert len(evidence) == 600
        assert all(row['ego']['speed_provenance'] == 'synthetic_native_sample'
                   for row in evidence)
        recipe = json.loads(recipe_path.read_text())
        recipe['sources'][0]['sha256'] = '0' * 64
        changed = scratch / 'changed-recipe.json'
        changed.write_text(json.dumps(recipe, indent=2) + '\n')
        failed = run(changed, scratch / 'negative', env)
        assert failed.returncode != 0 and 'Fixture source missing/changed' in failed.stdout + failed.stderr
        assert not (scratch / 'negative').exists()
        return {'format': 'c10316-d4-current-exception-recipe-foundation-v1', 'passed': True,
                'case_id': HERE.name + '__' + suffix, 'selected': False,
                'recipe_sha256': sha(recipe_path), 'diagnostic_sha256': sha(spec_path),
                'fixture_sha256': receipt['fixture_sha256'],
                'source_frames': 600, 'json_graphs': 600,
                'camera_sources': 4, 'derived_channels_supplied': False,
                'invented_speed_provenance': 'synthetic_native_sample',
                'changed_source_rejected': True,
                'scope': 'synthetic fixture materialization; not exact v2 compatibility or physical evidence'}


if __name__ == '__main__':
    results = [prove(suffix) for suffix in ('exception_1_1', 'exception_1_2')]
    summary = {'format': 'c10316-d4-current-exception-recipe-foundation-v2',
               'passed': all(row['passed'] for row in results), 'results': results}
    (HERE / 'current-exception-recipe-proof.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
