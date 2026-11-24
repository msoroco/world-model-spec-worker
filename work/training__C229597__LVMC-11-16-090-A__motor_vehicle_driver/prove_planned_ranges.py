"""Extract provisional physical sweep ranges from source-hashed CPU fixtures.

These are engineering planning bounds, not Native feasibility or legal cutoffs.
"""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
CASES = ('reference', 'contrast')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def examine(fixtures):
    episodes = []
    road_sources = set()
    for case, fixture in fixtures.items():
        files = fixture['files']
        trace = [json.loads(line) for line in files['trace.jsonl'].splitlines()]
        frame_map = [json.loads(line) for line in files['video_frames.jsonl'].splitlines()]
        if len(trace) != 600 or len(frame_map) != 600:
            raise ValueError('Full 600-frame physical source required')
        if any(row['video_frame'] != i or row['carla_frame'] != trace[i]['frame']
               for i, row in enumerate(frame_map)):
            raise ValueError('Original trace and frame-map identity differs')
        accelerations = [float(row['acceleration_mps2'][0]) for row in trace[160:440]]
        positions = [float(row['position']['x']) for row in trace]
        if min(positions) < 0 or max(positions) <= 0:
            raise ValueError('Diagnostic route has no forward position span')
        road_sources.add(files['road.xodr'])
        episodes.append({'case': case, 'minimum_acceleration_mps2': min(accelerations),
                         'maximum_acceleration_mps2': max(accelerations),
                         'minimum_route_x_m': min(positions),
                         'maximum_route_x_m': max(positions),
                         'sample_window_frames': [160, 439]})
    if len(road_sources) != 1:
        raise ValueError('Compared cases require one fixed diagnostic road source')
    root = ET.fromstring(next(iter(road_sources)))
    roads = root.findall('road')
    if len(roads) != 1 or roads[0].get('name') != 'straight-diagnostic':
        raise ValueError('Diagnostic road geometry differs')
    length = float(roads[0].get('length'))
    if length < 210:
        raise ValueError('Diagnostic source does not cover proposed route span')
    acceleration_points = [0.1, 0.15, 0.2]
    route_points = [25.0, 100.0, 175.0]
    if not (min(e['minimum_acceleration_mps2'] for e in episodes)
            <= acceleration_points[0] < acceleration_points[-1]
            <= max(e['maximum_acceleration_mps2'] for e in episodes)):
        raise ValueError('Proposed acceleration range exceeds synthetic observation')
    if route_points[-1] >= min(length, max(e['maximum_route_x_m'] for e in episodes)):
        raise ValueError('Proposed route coordinate exceeds synthetic observation')
    return {'episodes': episodes,
            'acceleration_plan': {'setpoints_mps2': acceleration_points,
                                  'unit': 'm/s2',
                                  'source_role': 'synthetic observed range for engineering planning only',
                                  'native_target_controller_implemented': False,
                                  'native_realization_verified': False},
            'route_plan': {'coordinates_m': route_points,
                           'unit': 'm', 'diagnostic_road_length_m': length,
                           'source_role': 'synthetic route coordinate coverage only',
                           'native_route_selector_implemented': False,
                           'native_geometry_verified': False,
                           'highway_classification': 'unknown'},
            'statutory_threshold_claimed': False}


def main():
    paths = {name: HERE / f'selected-{name}-fixture.json' for name in CASES}
    fixtures = {name: json.loads(path.read_text()) for name, path in paths.items()}
    positive = examine(fixtures)
    changed = json.loads(json.dumps(fixtures))
    changed['reference']['files']['road.xodr'] = changed['reference']['files']['road.xodr'].replace(
        'length="300"', 'length="100"')
    negatives = []
    for label, candidate in [('changed_road_geometry', changed)]:
        try:
            examine(candidate)
        except ValueError as error:
            negatives.append({'name': label, 'rejected': True, 'error': str(error)})
        else:
            raise AssertionError(label + ' was accepted')
    changed = json.loads(json.dumps(fixtures))
    lines = changed['contrast']['files']['trace.jsonl'].splitlines()
    changed['contrast']['files']['trace.jsonl'] = '\n'.join(lines[:-1]) + '\n'
    try:
        examine(changed)
    except ValueError as error:
        negatives.append({'name': 'shortened_motion_source', 'rejected': True,
                          'error': str(error)})
    else:
        raise AssertionError('Shortened motion source was accepted')
    output = {'format': 'c229597-provisional-physical-range-proof-v1',
              'fixture_sha256': {name: sha(path) for name, path in paths.items()},
              'positive': positive, 'negative_cases': negatives,
              'synthetic_only': True, 'native_executed': False,
              'legal_verdict_claimed': False, 'delivery_ready': False}
    path = HERE / 'sweep-physical/planned-ranges.json'
    path.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'proof_sha256': sha(path),
                      'acceleration_setpoints': positive['acceleration_plan']['setpoints_mps2'],
                      'route_coordinates': positive['route_plan']['coordinates_m'],
                      'negative_rejections': len(negatives)}))


if __name__ == '__main__':
    main()
