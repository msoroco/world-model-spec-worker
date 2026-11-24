"""Build explicit CPU diagnostic sources for exact departure compatibility.

The borrowed frame/graph scaffold is diagnostic software input. It is never
treated as a recording or as evidence that the reviewed highway exists.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OLD = REPO / 'work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver'
NAMES = ('near_centerline', 'farther_from_centerline',
         'imaginary_near_centerline', 'imaginary_farther_from_centerline')


def _sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def build():
    for name in NAMES:
        old_case = OLD.name + '__' + name
        case = HERE.name + '__' + name
        donor = json.loads((OLD / 'cases' / name / 'diagnostic.json').read_text())
        files = {path: value.replace(old_case, case).replace('NRS-484B-400-2a', 'NRS-484B-400-2b')
                 for path, value in donor['files'].items()}
        history = [json.loads(line) for line in files.pop('approach-history.jsonl').splitlines()]
        files.pop('intersection-context.json')
        kind = ('source_derived_imaginary' if name.startswith('imaginary_') else 'mapped')
        map_source = files['road.xodr']
        files['original-map.xodr'] = map_source
        map_packet = {
            'case_id': case, 'road_kind': 'two_directional_intersection',
            'approach_road_id': 'approach', 'destination_road_id': 'departure',
            'approach_two_directional': True, 'destination_two_directional': True,
            'approach_highway_status': 'source_verified',
            'destination_highway_status': 'source_verified',
            'source_path': 'original-map.xodr', 'source_sha256': _sha(map_source),
            'centerline_kind': kind, 'centerline_origin_xy_m': [0.0, 0.0],
            'destination_direction_xy': [0.0, -1.0],
            'centerline_source': 'diagnostic sourced geometry',
            'direction_source': 'diagnostic sourced direction',
        }
        samples = []
        for index, row in enumerate(history):
            phase = 'approach' if index < 449 else ('intersection_entry' if index == 449 else 'departure')
            corners = row['ego_body_vertices_xy_m']
            center = [sum(point[axis] for point in corners) / len(corners) for axis in (0, 1)]
            samples.append({
                'frame': row['frame'], 'phase': phase,
                'road_id': 'approach' if phase == 'approach' else 'departure',
                'position_xy_m': center, 'body_corners_xy_m': corners,
                'heading_rad': row['ego_heading_rad'], 'speed_mps': 0.0,
                'elapsed_seconds': row['time_s'],
            })
        trace = {'case_id': case, 'approach_road_id': 'approach',
                 'destination_road_id': 'departure', 'maneuver': 'left_turn',
                 'driver_control': True, 'rate_hz': 20, 'samples': samples}
        camera = {'case_id': case, 'channels': {
            channel: [{'frame': row['frame'], 'channel': channel,
                       'source_path': f'diagnostic/{channel}/{index:08d}.png',
                       'source_sha256': 'diagnostic-only'}
                      for index, row in enumerate(history)]
            for channel in ('dash', 'front', 'left', 'right')}}
        packets = {'original-map-packet.json': json.dumps(map_packet, sort_keys=True) + '\n',
                   'original-trace.json': json.dumps(trace, sort_keys=True) + '\n',
                   'original-camera-index.json': json.dumps(camera, sort_keys=True) + '\n'}
        files.update(packets)
        source_manifest = {
            'case_id': case, 'acquisition_kind': 'diagnostic_fixture',
            'rate_hz': 20, 'duration_s': 45, 'camera_media_kind': 'generated_video',
            'diagnostic_fixture': True,
            'map': {'path': 'original-map-packet.json', 'sha256': _sha(packets['original-map-packet.json'])},
            'trace': {'path': 'original-trace.json', 'sha256': _sha(packets['original-trace.json'])},
            'camera_index': {'path': 'original-camera-index.json', 'sha256': _sha(packets['original-camera-index.json'])},
        }
        files['original-bindings.json'] = json.dumps(source_manifest, sort_keys=True) + '\n'
        donor['files'] = files
        path = HERE / 'cases' / name / 'diagnostic.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(donor, separators=(',', ':'), allow_nan=False) + '\n')
        contract = HERE / 'cases' / name / 'measurement-contract.json'
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-contract-source.json',
                               'source': str(contract.relative_to(REPO)),
                               'sha256': hashlib.sha256(contract.read_bytes()).hexdigest()}],
                  'generator': {'source': str(path.relative_to(REPO)),
                                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}
        (path.parent / 'fixture-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
        print(name, path.stat().st_size)


if __name__ == '__main__':
    build()
