"""Independent CPU audit of the two source-bound through-response histories."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRAMES = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_source(root, case):
    root = Path(root)
    required = ('road.xodr', 'native_samples.jsonl', 'video_frames.jsonl')
    manifest = json.loads((root / 'diagnostic-source-manifest.json').read_text())
    if manifest.get('case_id') != case:
        raise ValueError('Exact comparison case differs')
    if manifest.get('source_kind') != 'synthetic_native_sample':
        raise ValueError('Diagnostic comparison source kind differs')
    for name in ('road.xodr', 'native_samples.jsonl'):
        if not (root / name).is_file() or manifest.get('sha256', {}).get(name) != sha(root / name):
            raise ValueError('Source hash differs: ' + name)
    for name in required:
        if not (root / name).is_file():
            raise ValueError('Missing original source: ' + name)
    recipe_path = HERE / (root.name + '-recipe.json')
    recipe = json.loads(recipe_path.read_text())
    recipe_sources = {item['path']: item['sha256'] for item in recipe['sources']}
    for name in required:
        if recipe_sources.get(name) != sha(root / name):
            raise ValueError('Fixture recipe source hash differs: ' + name)
    samples = [json.loads(line) for line in (root / 'native_samples.jsonl').read_text().splitlines()]
    frames = [json.loads(line) for line in (root / 'video_frames.jsonl').read_text().splitlines()]
    if len(samples) != FRAMES or len(frames) != FRAMES:
        raise ValueError('Full 600-frame comparison absent')
    for index, (sample, frame) in enumerate(zip(samples, frames)):
        if sample['video_frame'] != index or frame['video_frame'] != index \
                or sample['native_frame'] != frame['native_frame'] \
                or sample['time_s'] != frame['time_s']:
            raise ValueError('Original source frame join differs')
    return {'samples': samples, 'road_sha256': sha(root / 'road.xodr'),
            'source_sha256': sha(root / 'native_samples.jsonl'),
            'frame_map_sha256': sha(root / 'video_frames.jsonl'),
            'fixture_recipe_sha256': sha(recipe_path)}


def audit(primary, controlled):
    if primary['road_sha256'] != controlled['road_sha256']:
        raise ValueError('Fixed authored road differs')
    baseline = primary['samples']
    contrast = controlled['samples']
    different = []
    for index, (left, right) in enumerate(zip(baseline, contrast)):
        if left['entrant'] != right['entrant']:
            raise ValueError('Fixed entrant source differs')
        if (left['native_frame'], left['time_s']) != (right['native_frame'], right['time_s']):
            raise ValueError('Fixed frame timing differs')
        if left['through'] != right['through']:
            different.append(index)
            if index < 142:
                raise ValueError('Through history changed before response')
        if left['through']['lane_id'] != 1 or right['through']['lane_id'] != 1 \
                or left['through']['road_id'] not in (4, 13, 1) \
                or right['through']['road_id'] not in (4, 13, 1):
            raise ValueError('Through route/lane role differs')
    if not different or min(different) != 142:
        raise ValueError('Controlled through response absent or mistimed')
    return {'format': 'c111294-independent-priority-comparison-v1',
            'passed': True, 'frames': FRAMES,
            'changed_variable': 'through_driver_yield_to_entering_vehicle_request',
            'first_changed_frame': min(different), 'changed_frames': len(different),
            'fixed_entrant_all_frames': True, 'fixed_through_pre_response': True,
            'fixed_authored_road_sha256': primary['road_sha256'],
            'primary_source_sha256': primary['source_sha256'],
            'controlled_source_sha256': controlled['source_sha256'],
            'primary_fixture_recipe_sha256': primary['fixture_recipe_sha256'],
            'controlled_fixture_recipe_sha256': controlled['fixture_recipe_sha256'],
            'physical_response_observed': False, 'legal_verdict_claimed': False}


def main():
    first = load_source(HERE / 'current-v2-probe-1-fixture', HERE.name + '__probe_1')
    second = load_source(HERE / 'current-v2-probe-2-fixture', HERE.name + '__probe_2')
    result = audit(first, second)
    negatives = []
    damaged = {'samples': [dict(row) for row in second['samples']],
               'road_sha256': second['road_sha256']}
    damaged['samples'][200] = dict(damaged['samples'][200])
    damaged['samples'][200]['entrant'] = {'x_m': -999}
    try:
        audit(first, damaged)
    except ValueError as exc:
        negatives.append(str(exc))
    else:
        raise AssertionError('Altered entrant passed')
    damaged = {'samples': [dict(row) for row in second['samples']],
               'road_sha256': second['road_sha256']}
    damaged['samples'][20] = dict(damaged['samples'][20])
    damaged['samples'][20]['through'] = {'x_m': -999}
    try:
        audit(first, damaged)
    except ValueError as exc:
        negatives.append(str(exc))
    else:
        raise AssertionError('Premature contrast passed')
    damaged = dict(second)
    damaged['road_sha256'] = '0' * 64
    try:
        audit(first, damaged)
    except ValueError as exc:
        negatives.append(str(exc))
    else:
        raise AssertionError('Wrong fixed road passed')
    result['negative_rejections'] = negatives
    result['audit_script_sha256'] = sha(Path(__file__))
    path = HERE / 'priority-comparison-audit.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'negative_count': len(negatives),
                      'receipt_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
