"""Exercise the original-source sight meter with actor and occluder joins."""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from measure_sight_point import measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


def run():
    scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve() / 'sight-native-source-proof'
    if '.runtime-work' not in scratch.parts:
        raise ValueError('Proof scratch must remain under .runtime-work')
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    case = HERE.name + '__sight_stop'
    source = HERE / 'selected-source-sight_stop'
    for name in ('road.xodr', 'native_samples.jsonl', 'video_frames.jsonl',
                 'sight_samples.jsonl', 'diagnostic-source-manifest.json'):
        shutil.copyfile(source / name, scratch / name)
    sight_path = scratch / 'sight_samples.jsonl'
    rows = [json.loads(line) for line in sight_path.read_text().splitlines()]
    for row in rows:
        row.update({'view_source_kind': 'native_actor_ray_proxy',
                    'intersecting_actor_id': 1001,
                    'occluder_actor_id': 1002,
                    'intersecting_actor_velocity_x_mps': 0.4})
    write(sight_path, rows)
    manifest_path = scratch / 'diagnostic-source-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['source_kind'] = 'native_observation'
    manifest['sha256']['sight_samples.jsonl'] = sha(sight_path)
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    measured = measure(scratch, case)
    if not measured['halt_at_view_point_observed']:
        raise AssertionError('Source-bound Native-shaped halt not measured')
    failures = []
    for change, expected in (('missing_actor_id', 'Original intersecting actor'),
                             ('bad_ray', 'Sight ray/occluder')):
        altered = [dict(row) for row in rows]
        if change == 'missing_actor_id':
            altered[100].pop('intersecting_actor_id')
        else:
            altered[100]['view_open'] = not altered[100]['view_open']
        write(sight_path, altered)
        manifest['sha256']['sight_samples.jsonl'] = sha(sight_path)
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        try:
            measure(scratch, case)
        except ValueError as error:
            if expected not in str(error):
                raise
            failures.append(change)
        else:
            raise AssertionError('Changed original source accepted: ' + change)
    report = {'format': 'c111325-sight-native-source-cpu-v1',
              'case_id': case, 'source_kind': 'native_shaped_fixture',
              'positive_halt_frames': measured['longest_halt_after_view_open_frames'],
              'negative_rejections': failures,
              'original_pixels_reviewed': False,
              'physical_visibility_verified': False,
              'legal_verdict_claimed': False}
    target = HERE / 'sight-native-source-proof.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    return {'passed': True, 'proof_sha256': sha(target)}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
