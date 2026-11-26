"""Synthetic source-shaped CPU fixtures, never original CARLA evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c190631-measure-fixtures'
SCRATCH.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(HERE / 'native'))
from geometry import geometry
from measure import measure


def fixtures(label, y):
    folder = SCRATCH / label
    folder.mkdir(exist_ok=True)
    geometry_path = folder / 'surface-geometry.json'
    pose_path = folder / 'pedestrian-poses.jsonl'
    g = geometry()
    g['native_readback'] = {'roadway': [{'lane_id': -1}] * 3,
                            'sidewalk': [{'lane_id': -3}] * 3,
                            'lower_road': [{'lane_id': -1, 'road_id': 2,
                                            'native_xyz_m': [1.75, q, 0]}
                                           for q in (-20, 0, 20)]}
    geometry_path.write_text(json.dumps(g) + '\n')
    with pose_path.open('w') as out:
        for i in range(600):
            x = -30 + i * .1
            footprint = [[x + dx, y + dy] for dx, dy in
                         ((-.1, -.1), (-.1, .1), (.1, -.1), (.1, .1))]
            out.write(json.dumps({'video_frame': i, 'native_frame': 1000 + i,
                                  'time_s': i / 20, 'pedestrian_xy_m': [x, y],
                                  'pedestrian_footprint_xy_m': footprint,
                                  'walker_actor_id': 14,
                                  'provenance': 'synthetic_native_sample'}) + '\n')
    return pose_path, geometry_path


def main():
    road_pose, road_geom = fixtures('roadway', -2)
    sidewalk_pose, sidewalk_geom = fixtures('sidewalk', -5)
    road = measure(road_pose, road_geom)
    sidewalk = measure(sidewalk_pose, sidewalk_geom)
    assert road['roadway_occupied_frames'] == 600
    assert road['sidewalk_occupied_frames'] == 0
    assert sidewalk['sidewalk_occupied_frames'] == 600
    assert sidewalk['roadway_occupied_frames'] == 0
    assert road['path_length_m'] > 59
    lines = road_pose.read_text().splitlines()
    (SCRATCH / 'missing-pedestrian-poses.jsonl').write_text('\n'.join(lines[:-1]) + '\n')
    try:
        measure(SCRATCH / 'missing-pedestrian-poses.jsonl', road_geom)
    except ValueError as exc:
        assert 'missing or unordered original pedestrian frames' in str(exc)
        negative = str(exc)
    else:
        raise AssertionError('missing original frame was accepted')
    missing_body = json.loads(lines[0])
    del missing_body['pedestrian_footprint_xy_m']
    (SCRATCH / 'missing-footprint.jsonl').write_text('\n'.join(
        [json.dumps(missing_body), *lines[1:]]) + '\n')
    try:
        measure(SCRATCH / 'missing-footprint.jsonl', road_geom)
    except ValueError as exc:
        assert 'original pedestrian footprint source missing' in str(exc)
        negative_footprint = str(exc)
    else:
        raise AssertionError('missing footprint was accepted')
    broken = json.loads(road_geom.read_text())
    broken['sidewalk_provided'] = False
    (SCRATCH / 'missing-provided-sidewalk.json').write_text(json.dumps(broken) + '\n')
    try:
        measure(road_pose, SCRATCH / 'missing-provided-sidewalk.json')
    except ValueError as exc:
        assert 'provided adjacent sidewalk source missing' in str(exc)
        negative_sidewalk = str(exc)
    else:
        raise AssertionError('missing provided sidewalk was accepted')
    broken_survey = json.loads(road_geom.read_text())
    del broken_survey['native_readback']
    (SCRATCH / 'missing-survey.json').write_text(json.dumps(broken_survey) + '\n')
    try:
        measure(road_pose, SCRATCH / 'missing-survey.json')
    except ValueError as exc:
        assert 'Native roadway/sidewalk survey source missing' in str(exc)
        negative_survey = str(exc)
    else:
        raise AssertionError('missing Native survey was accepted')
    broken_lower = json.loads(road_geom.read_text())
    broken_lower['native_readback']['lower_road'][1]['native_xyz_m'][2] = 8
    (SCRATCH / 'wrong-lower-road.json').write_text(json.dumps(broken_lower) + '\n')
    try:
        measure(road_pose, SCRATCH / 'wrong-lower-road.json')
    except ValueError as exc:
        assert 'Native lower overpass road source differs' in str(exc)
        negative_lower = str(exc)
    else:
        raise AssertionError('wrong lower road was accepted')
    print(json.dumps({'passed': True, 'fixture_kind': 'synthetic_native_sample',
                      'roadway': road, 'sidewalk': sidewalk,
                      'negative_missing_frame': negative,
                      'negative_missing_footprint': negative_footprint,
                      'negative_missing_sidewalk': negative_sidewalk,
                      'negative_missing_survey': negative_survey,
                      'negative_wrong_lower_road': negative_lower,
                      'measure_sha256': hashlib.sha256((HERE / 'native/measure.py').read_bytes()).hexdigest()},
                     sort_keys=True))


if __name__ == '__main__':
    main()
