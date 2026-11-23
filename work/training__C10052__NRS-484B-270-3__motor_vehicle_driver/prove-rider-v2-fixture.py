"""Check the current pinned fixture recipe for one unselected rider case."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RECIPE = HERE / 'rider-v2-bicycle-clear-primary/fixture-recipe.json'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(recipe, output):
    return [sys.executable, str(ROOT / 'runtime.py'), 'fixture',
            '--recipe', str(recipe), '--output', str(output)]


def frame_count(video):
    probe = subprocess.run(
        ['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
         '-show_entries', 'stream=width,height,r_frame_rate,nb_read_frames',
         '-of', 'json', str(video)], check=True, capture_output=True, text=True)
    stream = json.loads(probe.stdout)['streams'][0]
    assert (stream['width'], stream['height'], stream['r_frame_rate'],
            int(stream['nb_read_frames'])) == (1920, 1080, '20/1', 480)
    return int(stream['nb_read_frames'])


def main():
    assert RECIPE.is_file()
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c10052-v2-fixture-proof')
    (ROOT / '.runtime-work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c10052-v2-proof-') as temp:
        scratch = Path(temp)
        positive = scratch / 'positive'
        run = subprocess.run(command(RECIPE, positive), cwd=ROOT, env=env,
                             capture_output=True, text=True, timeout=180)
        if run.returncode:
            raise AssertionError(run.stdout + run.stderr)
        receipt = json.loads(run.stdout)
        assert receipt['recipe_sha256'] == sha(RECIPE)
        assert len((positive / 'native_samples.jsonl').read_text().splitlines()) == 480
        assert len((positive / 'rider_native_samples.jsonl').read_text().splitlines()) == 480
        assert len((positive / 'video_frames.jsonl').read_text().splitlines()) == 480
        assert not (positive / 'channels').exists()
        frames = {name: frame_count(positive / (name + '.mkv')) for name in CAMERAS}
        recipe = json.loads(RECIPE.read_text())
        recipe['sources'][0]['sha256'] = '0' * 64
        changed = scratch / 'changed-recipe.json'
        changed.write_text(json.dumps(recipe, indent=2) + '\n')
        rejected = subprocess.run(command(changed, scratch / 'negative'),
                                  cwd=ROOT, env=env, capture_output=True, text=True,
                                  timeout=60)
        failure = rejected.stdout + rejected.stderr
        assert rejected.returncode != 0 and 'Fixture source missing/changed' in failure
        assert not (scratch / 'negative').exists()
        result = {
            'format': 'c10052-rider-current-recipe-foundation-v1',
            'case_id': HERE.name + '__rider_bicycle_clear',
            'selected': False,
            'recipe_sha256': sha(RECIPE),
            'source_count': len(recipe['sources']),
            'fixture_sha256': receipt['fixture_sha256'],
            'source_frames': 480,
            'camera_frames': frames,
            'derived_channels_supplied': False,
            'changed_source_rejected': True,
            'negative_error': 'Fixture source missing/changed',
            'positive_exit_code': run.returncode,
            'negative_exit_code': rejected.returncode,
            'scope': 'synthetic fixture materialization only; no exact v2 compatibility or physical claim',
        }
    path = HERE / 'rider-v2-fixture-proof.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
