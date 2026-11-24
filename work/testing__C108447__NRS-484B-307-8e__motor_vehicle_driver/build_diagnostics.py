"""Create six source-shaped diagnostic recipes with explicit synthetic provenance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

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
    for suffix in SUFFIXES:
        case_id = ASSIGNMENT + '__' + suffix
        folder = FOLDER / 'diagnostics' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        xodr = '<OpenDRIVE><header name="C108447 diagnostic only"/></OpenDRIVE>\n'
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
                    'yaw_rad': 0} for frame in range(100, 120)]
        approach_state = 'green' if suffix == 'no_approach_red' else 'red_alone'
        destination_state = 'red_alone' if suffix == 'destination_red' else 'yellow'
        approach = [{'frame': frame, 'device_id': 'approach-A',
                     'source': {'diagnostic_device': 'A'}, 'facing_ego': True,
                     'state': approach_state} for frame in range(100, 120)]
        destination = [{'frame': frame, 'device_id': 'destination-B',
                        'source': {'diagnostic_device': 'B'}, 'facing_ego': False,
                        'state': destination_state} for frame in range(100, 120)]
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
        spec = {'files': {'road.xodr': xodr, 'authority.json': authority_text,
                          'map-packet.json': encoded(packet), 'trace.json': encoded(trace)},
                'graphs': [],
                'videos': [{'path': f'{name}.mkv', 'frames': 20, 'width': width,
                            'height': height, 'fps': 20, 'color': 'black'}
                           for name, width, height in [('overview', 1920, 1080),
                                                       ('approach', 1280, 720),
                                                       ('property', 1280, 720),
                                                       ('destination', 1280, 720)]]}
        source = folder / 'specification.json'
        source.write_text(encoded(spec))
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
