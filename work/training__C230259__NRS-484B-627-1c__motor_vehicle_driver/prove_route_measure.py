"""Small source-shaped route reducer test; never a Native observation."""
import hashlib
import json
from pathlib import Path

from geometry import open_drive
from route_measure import measure

HERE = Path(__file__).resolve().parent


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def source(alternate_possible, take_alternate):
    road = open_drive(alternate_possible).encode()
    context = encode({'source_kind': 'native_saved_sample',
        'road_xodr_sha256': hashlib.sha256(road).hexdigest(),
        'route_graph': {'start_road_id': 1, 'main_road_id': 2,
            'alternate_road_id': 3 if alternate_possible else None,
            'destination_road_id': 4}})
    rows, frame_map = [], []
    for index in range(900):
        native = index + 100
        road_id = 1 if index < 100 else (3 if take_alternate else 2)
        if index >= 700:
            road_id = 4
        x = -20 + index * .2
        cameras = {name: native for name in ('overview', 'approach', 'reference_corner', 'driver_reference')}
        rows.append({'video_frame': index, 'native_frame': native, 'time_s': index / 20,
            'camera_native_frames': cameras,
            'ego': {'actor_id': 'ego', 'xy_m': [x, 0], 'speed_mps': 4,
                    'road_id': road_id, 'lane_id': -1},
            'following': [{'actor_id': 'follower-1', 'xy_m': [x - 14, 0],
                'speed_mps': 4, 'road_id': 1 if index < 100 else 2, 'lane_id': -1},
                {'actor_id': 'follower-2', 'xy_m': [x - 30, 0],
                'speed_mps': 4, 'road_id': 1 if index < 100 else 2, 'lane_id': -1}]})
        frame_map.append({'video_frame': index, 'native_frame': native,
                          'time_s': index / 20})
    return [b''.join(encode(row) for row in rows), context, road,
            b''.join(encode(row) for row in frame_map)]


def prove():
    positives = []
    for alternate, taken in ((True, True), (True, False), (False, False)):
        facts = measure(*source(alternate, taken))
        assert facts['authored_alternate_connected'] == alternate
        assert facts['observed_alternate_road'] == taken
        positives.append({'alternate_possible': alternate, 'take_alternate': taken,
                          'frames': facts['frames']})
    base = source(True, False)
    negatives = []
    mutations = {
        'missing_road': [base[0], base[1], b'<OpenDRIVE/>', base[3]],
        'missing_frame': [base[0], base[1], base[2], b'\n'.join(base[3].splitlines()[:-1]) + b'\n'],
        'missing_following': None,
        'wrong_camera_frame': None,
    }
    rows = [json.loads(line) for line in base[0].splitlines()]
    changed = json.loads(json.dumps(rows))
    changed[40]['following'] = changed[40]['following'][:1]
    mutations['missing_following'] = [b''.join(encode(row) for row in changed), *base[1:]]
    changed = json.loads(json.dumps(rows))
    changed[40]['camera_native_frames']['reference_corner'] += 1
    mutations['wrong_camera_frame'] = [b''.join(encode(row) for row in changed), *base[1:]]
    for name, inputs in mutations.items():
        try:
            measure(*inputs)
        except ValueError as error:
            negatives.append({'mutation': name, 'rejection': str(error)})
        else:
            raise AssertionError('source mutation accepted: ' + name)
    receipt = {'format': 'c230259-route-saved-cpu-proof-v1',
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'positives': positives, 'negatives': negatives,
        'source_kind': 'synthetic_source_shaped_fixture',
        'native_observed': False, 'physical_or_legal_acceptance': False}
    (HERE / 'route-native-cpu-proof.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return {'positives': len(positives), 'negatives': len(negatives)}


if __name__ == '__main__':
    print(json.dumps(prove()))
