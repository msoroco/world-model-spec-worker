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
RECIPE = HERE / 'current-witness_1-recipe.json'
SPEC = HERE / 'current-witness_1-diagnostic.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(recipe, output, env):
    return subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'fixture',
                           '--recipe', str(recipe), '--output', str(output)],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)


def prove():
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c10316-d4-recipe-proof')
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c10316-d4-v2-proof-') as temp:
        scratch = Path(temp)
        positive = scratch / 'positive'
        passed = run(RECIPE, positive, env)
        if passed.returncode:
            raise AssertionError(passed.stdout + passed.stderr)
        receipt = json.loads(passed.stdout)
        assert receipt['recipe_sha256'] == sha(RECIPE)
        assert len((positive / 'steady-samples.jsonl').read_text().splitlines()) == 240
        assert len((positive / 'capture/native/frames.jsonl').read_text().splitlines()) == 240
        assert not (positive / 'channels').exists()
        frames = [json.loads(line) for line in
                  (positive / 'capture/native/frames.jsonl').read_text().splitlines()]
        assert all(row['base'].endswith('.adapter.json') and
                   (positive / 'capture/native' / row['base']).is_file() for row in frames)
        evidence = [json.loads(line) for line in
                    (positive / 'capture/evidence.jsonl').read_text().splitlines()]
        assert len(evidence) == 240
        assert all(row['ego']['speed_provenance'] == 'synthetic_native_sample'
                   for row in evidence)
        recipe = json.loads(RECIPE.read_text())
        recipe['sources'][0]['sha256'] = '0' * 64
        changed = scratch / 'changed-recipe.json'
        changed.write_text(json.dumps(recipe, indent=2) + '\n')
        failed = run(changed, scratch / 'negative', env)
        assert failed.returncode != 0 and 'Fixture source missing/changed' in failed.stdout + failed.stderr
        assert not (scratch / 'negative').exists()
        return {'format': 'c10316-d4-current-recipe-foundation-v1', 'passed': True,
                'case_id': HERE.name + '__witness_1', 'selected': False,
                'recipe_sha256': sha(RECIPE), 'diagnostic_sha256': sha(SPEC),
                'fixture_sha256': receipt['fixture_sha256'],
                'source_frames': 240, 'json_graphs': 240,
                'camera_sources': 4, 'derived_channels_supplied': False,
                'invented_speed_provenance': 'synthetic_native_sample',
                'changed_source_rejected': True,
                'scope': 'synthetic fixture materialization; not exact v2 compatibility or physical evidence'}


if __name__ == '__main__':
    result = prove()
    (HERE / 'current-steady-recipe-proof.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
