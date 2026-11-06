"""Generate source-hashed 480-frame CPU diagnostics and adversarial negatives."""
import importlib.util
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
OUT = ROOT / '.runtime-work/c102372-truck-gap'


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, FOLDER / 'native' / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


geometry = module('truck_geometry', 'geometry.py')
measurement = module('truck_measurement', 'measure_gap.py')


def write_case(case):
    folder = OUT / case
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    rows = []
    for frame in range(geometry.FRAMES):
        ego_x, lead_x = geometry.positions(case, frame)
        rows.append({'native_frame': frame, 'time_s': frame/geometry.RATE_HZ,
                     'ego': {'actor_class': 'truck_or_combination', 'road_id': 1, 'lane_id': -1,
                             'speed_mps': geometry.SPEED_MPS, 'body_xy_m': geometry.body(ego_x)},
                     'lead': {'actor_class': 'truck_or_combination', 'road_id': 1, 'lane_id': -1,
                              'speed_mps': geometry.SPEED_MPS, 'body_xy_m': geometry.body(lead_x)}})
    (folder / 'native_samples.jsonl').write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))
    (folder / 'following_context.json').write_text(json.dumps({
        'source_kind': 'synthetic_cpu_fixture', 'road_id': 1, 'lane_id': -1,
        'same_direction_lane_count': 1, 'overtaking': False,
        'conditions_permit_source': 'synthetic_assertion'}, sort_keys=True)+'\n')
    shutil.copyfile(FOLDER / 'native/road.xodr', folder / 'road.xodr')
    resign(folder)
    return folder


def resign(folder):
    names = ('native_samples.jsonl', 'following_context.json', 'road.xodr')
    (folder / 'source-manifest.json').write_text(json.dumps({
        'format': 'c102372-truck-follow-source-v1',
        'sha256': {name: measurement.sha(folder / name) for name in names}}, sort_keys=True)+'\n')


def must_reject(folder, expected):
    try:
        measurement.measure(folder)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f'Wrong rejection: {error}') from error
    else:
        raise AssertionError('Damaged source was accepted')


def main():
    geometry.check()
    results = {}
    for case in geometry.GAP_TARGET_M:
        folder = write_case(case)
        result = measurement.measure(folder)
        assert result['relation_to_500ft'] == ('above' if case == 'probe_1' else 'below')
        assert not result['physical_conditions_verified'] and not result['legal_verdict_claimed']
        results[case] = result
        samples = folder / 'native_samples.jsonl'
        original = samples.read_text()
        samples.write_text('\n'.join(original.splitlines()[:-1])+'\n')
        must_reject(folder, 'Original source missing or changed')
        resign(folder)
        must_reject(folder, 'Full 480-frame original source required')
        samples.write_text(original)
        context = folder / 'following_context.json'
        original_context = context.read_text()
        data = json.loads(original_context);data['same_direction_lane_count'] = 2
        context.write_text(json.dumps(data)+'\n');resign(folder)
        must_reject(folder, 'Wrong statutory context')
        context.write_text(original_context)
        rows = [json.loads(line) for line in original.splitlines()]
        rows[0]['lead']['body_xy_m'] = [[x, -1.5+(y+2)*.1] for x, y in rows[0]['lead']['body_xy_m']]
        samples.write_text(''.join(json.dumps(row)+'\n' for row in rows));resign(folder)
        must_reject(folder, 'Truck below 80-inch width')
        samples.write_text(original);resign(folder)
        road_path = folder / 'road.xodr'
        original_road = road_path.read_text()
        road = ET.fromstring(original_road)
        road.findall('road/elevationProfile/elevation')[2].set('a', '0')
        road_path.write_text(ET.tostring(road, encoding='unicode')+'\n')
        resign(folder)
        must_reject(folder, 'Wrong original hill-crest road')
        road_path.write_text(original_road);resign(folder)
        assert measurement.measure(folder) == result
    print(json.dumps({'passed': True, 'cases': {case: {'gap_m': value['median_surface_gap_m'],
                                                   'relation': value['relation_to_500ft']}
                                       for case, value in results.items()},
                      'negatives_per_case': 4, 'physical_observation_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
