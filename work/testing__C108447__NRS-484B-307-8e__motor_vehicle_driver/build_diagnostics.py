"""Create six source-shaped diagnostic recipes with explicit synthetic provenance."""
from __future__ import annotations

import hashlib
import json
import copy
from pathlib import Path

from analysis import canonical_trace_rows

ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
ASSIGNMENT = FOLDER.name
SUFFIXES = ('private_bypass', 'public_bypass', 'ordinary_crossing',
            'no_approach_red', 'destination_red', 'other_purpose')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + '\n'


def build() -> dict:
    core_example = json.loads((ROOT / 'runtime/fixtures/example.json').read_text())
    for suffix in SUFFIXES:
        case_id = ASSIGNMENT + '__' + suffix
        folder = FOLDER / 'diagnostics' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        xodr = core_example['files']['road.xodr']
        property_status = 'public' if suffix == 'public_bypass' else 'private'
        connector = {'lot': [[-3, 5], [5, 5], [13, 5]]}
        roadway = [[-3, -2], [5, -2], [13, -2]]
        authority = {'format': 'diagnostic-parcel-authority-v1',
                     'diagnostic_fixture': True, 'opendrive_sha256': sha(xodr.encode()),
                     'map_name': 'C108447 diagnostic only', 'coordinate_frame': 'diagnostic-xy',
                     'intersecting_street_id': 'street-B',
                     'connector_routes': connector, 'roadway_route': roadway,
                     'properties': [{'id': 'lot', 'status': property_status,
                                     'authority': 'synthetic diagnostic classification',
                                     'polygon_xy_m': [[0, 0], [10, 0], [10, 10], [0, 10]]}]}
        authority_text = encoded(authority)
        packet = {'source': {'kind': 'original_native_map_and_property_authority',
                             'path': 'authority.json', 'sha256': sha(authority_text.encode())},
                  'native_map': {'path': 'road.xodr', 'sha256': sha(xodr.encode()),
                                 'map_name': authority['map_name']},
                  'authority_review': {'reviewer': 'diagnostic generator',
                                       'source': 'synthetic fixture', 'decision': 'diagnostic_only'},
                  'diagnostic_fixture': True, 'coordinate_frame': 'diagnostic-xy',
                  'intersecting_street_id': 'street-B', 'properties': authority['properties'],
                  'connector_routes': connector, 'roadway_route': roadway}
        y = -2 if suffix == 'ordinary_crossing' else 5
        samples = [{'frame': frame, 'time_s': (frame - 100) / 20,
                    'x': -3 if frame == 100 else 5 if frame == 101 else 13,
                    'y': y, 'speed_mps': 0 if frame > 102 else 2,
                    'velocity_mps': [0 if frame > 102 else 2, 0, 0],
                    'yaw_rad': 0} for frame in range(100, 109)]
        approach_state = 'green' if suffix == 'no_approach_red' else 'red_alone'
        destination_state = 'red_alone' if suffix == 'destination_red' else 'yellow'
        approach = [{'frame': frame, 'device_id': 'approach-A',
                     'source': {'diagnostic_device': 'A'}, 'facing_ego': True,
                     'state': approach_state} for frame in range(100, 109)]
        destination = [{'frame': frame, 'device_id': 'destination-B',
                        'source': {'diagnostic_device': 'B'}, 'facing_ego': False,
                        'state': destination_state} for frame in range(100, 109)]
        trace = {'format': 'diagnostic-property-route-v1', 'diagnostic_fixture': True,
                 'case_id': case_id, 'coordinate_frame': 'diagnostic-xy',
                 'actor_class': 'vehicle', 'actor_source': {'source': 'diagnostic actor'},
                 'ego': samples, 'approach_signal': approach[0],
                 'destination_signal': destination[2],
                 'approach_signal_history': approach, 'destination_signal_history': destination,
                 'destination_street_id': 'street-B', 'destination_entry_frame': 102,
                 'purpose': {'source': 'diagnostic authored context',
                             'value': 'other' if suffix == 'other_purpose' else 'avoid_red'},
                 'status': 'diagnostic_unreviewed'}
        frame_map = ''.join(json.dumps({'video_frame': index, 'carla_frame': row['frame'],
                                        'time_s': row['time_s']}, sort_keys=True) + '\n'
                            for index, row in enumerate(samples))
        core_files = core_example['files']
        source_trace = ''.join(json.dumps(row) + '\n' for row in canonical_trace_rows(samples))
        core_evidence = [json.loads(line) for line in core_files['capture/evidence.jsonl'].splitlines()]
        core_frames = [json.loads(line) for line in core_files['capture/native/frames.jsonl'].splitlines()]
        graphs = copy.deepcopy(core_example['graphs'])
        for index, body in enumerate(samples):
            event = core_evidence[index]
            frame = core_frames[index]
            graph = graphs[index]
            event['original_frame'] = body['frame']
            event['replay_frame'] = body['frame']
            event['recording_time_s'] = body['time_s']
            event['replay_simulation_time_s'] = 40 + body['time_s']
            event['ego']['position_m'] = [body['x'], body['y'], body.get('z', 0)]
            event['ego']['speed_mps'] = body['speed_mps']
            event['ego']['speed_provenance'] = 'synthetic_native_sample'
            event['original_observations']['frame'] = body['frame']
            event['original_observations']['time_s'] = body['time_s']
            event['original_observations']['participants'] = []
            frame['frame'] = body['frame']
            frame['simulation_time'] = 40 + body['time_s']
            frame['adapter_graph'] = f'graphs/base/{body["frame"]:08d}.adapter.json'
            graph['path'] = 'capture/native/' + frame['adapter_graph']
            graph['attributes']['frame'] = body['frame']
            graph['attributes']['observed_evidence'] = event['original_observations']
        capture_manifest = json.loads(core_files['capture/manifest.json'])
        capture_manifest['case_id'] = case_id
        capture_manifest['acquisition'] = 'synthetic_fixture'
        capture_manifest['source_run'] = 'C108447 diagnostic source fixture'
        capture_manifest['required_observations'] = []
        capture_manifest['sources']['road.xodr'] = sha(xodr.encode())
        capture_manifest['sources']['trace.jsonl'] = sha(source_trace.encode())
        spec = {'files': {'road.xodr': xodr, 'authority.json': authority_text,
                          'map-packet.json': encoded(packet), 'trace.json': encoded(trace),
                          'video_frames.jsonl': frame_map,
                          'trace.jsonl': source_trace,
                          'capture/evidence.jsonl': ''.join(json.dumps(row) + '\n' for row in core_evidence),
                          'capture/native/frames.jsonl': ''.join(json.dumps(row) + '\n' for row in core_frames),
                          'capture/manifest.json': encoded(capture_manifest),
                          'capture/native_map_facts.json': core_files['capture/native_map_facts.json'],
                          'capture/recorder_info.txt': core_files['capture/recorder_info.txt']},
                'graphs': graphs,
                'videos': [{'path': f'{name}.mkv', 'frames': 9, 'width': width,
                            'height': height, 'fps': 20, 'color': 'black'}
                           for name, width, height in [('overview', 1920, 1080),
                                                       ('approach', 1280, 720),
                                                       ('reference_corner', 1280, 720),
                                                       ('driver_reference', 1280, 720)]]}
        source = folder / 'specification.json'
        source.write_text(json.dumps(spec, separators=(',', ':')) + '\n')
        reference = str(source.relative_to(ROOT))
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-source.json', 'source': reference,
                               'sha256': sha(source.read_bytes())}],
                  'generator': {'source': reference, 'sha256': sha(source.read_bytes())}}
        (folder / 'fixture-recipe.json').write_text(encoded(recipe))
    return {'assignment_id': ASSIGNMENT, 'diagnostic_recipes': len(SUFFIXES),
            'physical_acceptance_claimed': False}


if __name__ == '__main__':
    print(encoded(build()).strip())
