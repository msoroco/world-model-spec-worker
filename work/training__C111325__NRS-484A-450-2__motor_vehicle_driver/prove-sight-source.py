"""Diagnostic fixture for the no-crosswalk/no-line sight-point branch."""
import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c111325-sight-source'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_meter():
    spec = importlib.util.spec_from_file_location('sight_meter', HERE / 'native/measure_sight_point.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.measure


def fixture(label):
    source = HERE / f'selected-source-line_{label}'
    target = SCRATCH / label
    shutil.copytree(source, target)
    shutil.copyfile(HERE / 'native/road_sight_point.xodr', target / 'road.xodr')
    samples = [json.loads(line) for line in (target / 'native_samples.jsonl').read_text().splitlines()]
    sight = []
    for sample in samples:
        center_y = sum(vertex[1] for vertex in sample['body_vertices_m']) / 8
        frame = sample['video_frame']
        actor_x = -20 + 0.02 * frame
        def at_x(x):
            return center_y + (x - 1.75) / (actor_x - 1.75) * (0 - center_y)
        low, high = sorted((at_x(-0.5), at_x(0)))
        occluded = high >= -40 and low <= -13
        sight.append({'native_frame': sample['native_frame'], 'time_s': sample['time_s'],
                      'approaching_traffic': True,
                      'view_open': not occluded,
                      'view_source_kind': 'synthetic_view_proxy',
                      'intersecting_actor_approach': 'west_to_east',
                      'intersecting_actor_xy_m': [actor_x, 0],
                      'observer_eye_xy_m': [1.75, center_y],
                      'occluder_xy_bounds_m': [-0.5, 0, -40, -13]})
    (target / 'sight_samples.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in sight))
    case_id = HERE.name + f'__sight_{label}'
    names = ('road.xodr', 'native_samples.jsonl', 'sight_samples.jsonl', 'video_frames.jsonl')
    manifest = {'case_id': case_id, 'source_kind': 'synthetic_native_sample',
                'sha256': {name: sha(target / name) for name in names}}
    (target / 'diagnostic-source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return target, case_id


def prove():
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    measure = load_meter()
    outcomes = {}
    for label in ('stop', 'pass'):
        target, case_id = fixture(label)
        outcomes[label] = measure(target, case_id)
    if not outcomes['stop']['halt_at_view_point_observed'] or outcomes['pass']['halt_at_view_point_observed']:
        raise AssertionError('Controlled synthetic view-point stop contrast absent')
    negatives = []
    target = SCRATCH / 'stop'
    try:
        measure(target, HERE.name + '__sight_wrong')
    except ValueError as error:
        negatives.append(str(error))
    (target / 'sight_samples.jsonl').unlink()
    try:
        measure(target, HERE.name + '__sight_stop')
    except (ValueError, FileNotFoundError) as error:
        negatives.append(type(error).__name__ + ': ' + str(error))
    if len(negatives) != 2:
        raise AssertionError('Sight negative source tests failed')
    report = {'format': 'c111325-sight-point-source-only-proof-v1',
              'cases': outcomes, 'negative_rejections': negatives,
              'source_kind': 'synthetic_view_proxy',
              'physical_visibility_verified': False, 'legal_verdict': None}
    path = HERE / 'sight-point-source-proof.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    return {'proof_sha256': sha(path), 'synthetic_cases': 2, 'negative_rejections': 2}


if __name__ == '__main__':
    root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    if '.runtime-work' not in root.parts:
        raise ValueError('Runtime output must remain under .runtime-work')
    print(json.dumps(prove(), sort_keys=True))
