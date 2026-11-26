"""CPU source and missing-evidence proof for the saved walking finalizer."""

import json
import tempfile
from pathlib import Path

from runner import _packet
from saved_walking import finalize
from walking_side import FRAMES, HZ

BASE = Path(__file__).resolve().parents[1]


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def prepare(folder, condition):
    construction = json.loads((BASE / 'draft-native' / condition / 'construction.json').read_text())
    config = json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
    write(folder / 'config.json', config)
    write(folder / 'result.json', {'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture'})
    context = {'source_kind': 'synthetic_diagnostic', 'highway_authority_source': 'fixture:public-road',
               'highway_boundary_source': 'fixture:survey', 'sidewalk_inventory_source': 'fixture:absence',
               'subsection_6_obstruction_source': 'fixture:no-sidewalk-traveler-obstruction',
               'traffic_route_source': 'fixture:eastbound', 'sidewalk_present': False,
               'subsection_6_obstruction': False, 'highway_half_width_m': 6,
               'highway_centerline_anchor_xy_m': [0, 0], 'traffic_direction_xy': [1, 0]}
    write(folder / 'reviewed-road-source.json', context)
    side_y = 4 if condition == 'a' else -4
    with (folder / 'walking-source.jsonl').open('x') as source, (folder / 'video_frames.jsonl').open('x') as frames, (folder / 'trace.jsonl').open('x') as original:
        for i in range(FRAMES):
            position = [20 - i * .02, side_y, .5]
            source.write(json.dumps({'video_frame': i, 'native_frame': i + 100, 'time_s': i / HZ,
                                     'pedestrian_id': 'ped-1', 'vehicle_id': 'veh-1',
                                     'pedestrian_xy_m': position[:2],
                                     'vehicle_xy_m': [-30 + i * .04, -1.75],
                                     'pedestrian_heading_xy': [-1, 0]}) + '\n')
            frames.write(json.dumps({'video_frame': i, 'native_frame': i + 100, 'time_s': i / HZ}) + '\n')
            original.write(json.dumps({'frame': i + 100, 'time_s': i / HZ,
                                       'position_m': position, 'speed_mps': .4}) + '\n')


def prove():
    result = {'format': 'worker-saved-walking-cpu-proof', 'assignment_id': BASE.name,
              'positive': [], 'negative': [], 'physical_completion': False}
    for condition in ('a', 'b'):
        with tempfile.TemporaryDirectory(prefix='c230259-walk-', dir='.runtime-work') as scratch:
            folder = Path(scratch)
            prepare(folder, condition)
            report = finalize(folder)
            count = report['measurements']['walking_side_trace']['value']
            assert report['frame_count'] == FRAMES and count['facing_opposite_traffic'] == FRAMES
            assert count['traffic_left' if condition == 'a' else 'traffic_right'] == FRAMES
            result['positive'].append({'condition': condition, 'case_id': report['case_id'], 'counts': count})
            packet = json.loads((folder / 'reviewed-road-source.json').read_text())
            packet.update({'source_kind': 'original_native', 'map_name': 'fixture-map',
                           'condition': condition,
                           'pedestrian_route_side': 'traffic_left' if condition == 'a' else 'traffic_right',
                           'pedestrian_spawn_transform': {'location': {'x': 0, 'y': 0, 'z': 0}, 'rotation': {'yaw': 0}},
                           'vehicle_spawn_transform': {'location': {'x': -30, 'y': 0, 'z': 0}, 'rotation': {'yaw': 0}},
                           'pedestrian_blueprint': 'walker.pedestrian.fixture',
                           'vehicle_blueprint': 'vehicle.fixture',
                           'pedestrian_direction_xyz': [-1, 0, 0],
                           'pedestrian_speed_mps': 1.0, 'vehicle_throttle': 0.3})
            write(folder / 'source-packet.json', packet)
            assert _packet(folder / 'source-packet.json', config_for(folder))['condition'] == condition
            packet['pedestrian_direction_xyz'] = [1, 0, 0]
            write(folder / 'source-packet.json', packet)
            try:
                _packet(folder / 'source-packet.json', config_for(folder))
            except ValueError as error:
                assert 'must face approaching traffic' in str(error)
                result['negative'].append({'condition': condition, 'error': str(error)})
            else:
                raise AssertionError('Wrong heading packet was accepted')
            (folder / 'reviewed-road-source.json').unlink()
            try:
                finalize(folder)
            except ValueError as error:
                assert str(error) == 'Missing required source: reviewed-road-source.json'
                result['negative'].append({'condition': condition, 'error': str(error)})
            else:
                raise AssertionError('Missing context was accepted')
    return result


def config_for(folder):
    return json.loads((folder / 'config.json').read_text())


if __name__ == '__main__':
    proof = prove()
    write(BASE / 'native' / 'saved-walking-proof.json', proof)
    print(json.dumps({'positive': len(proof['positive']), 'negative': len(proof['negative'])}))
