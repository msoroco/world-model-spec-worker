"""Create textual 600-frame software diagnostics for the selected reference.

All speed and pixels here are invented CPU samples, never original CARLA data.
Generated media and pickle graphs are materialized only under .runtime-work/.
"""
import argparse
import hashlib
import json
from pathlib import Path

from native_runner import ASSIGNMENT, FRAMES, RATE_HZ
from rail_road import open_drive


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE_ID = ASSIGNMENT + '__reference'
SOURCES = ROOT / 'fixtures' / 'sources'
SPEC = ROOT / 'fixtures' / 'reference-diagnostic-spec.json'
RECIPE = ROOT / 'fixtures' / 'reference-recipe.json'


def encode(value):
    return json.dumps(value, sort_keys=True, allow_nan=False) + '\n'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(relative, content):
    path = SOURCES / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def lines(rows):
    return ''.join(encode(row) for row in rows)


def body(station, direction=1):
    return [[station + x, -1.75 * direction + y, z]
            for x in (-6.0, 6.0) for y in (-1.2, 1.2) for z in (0.0, 2.5)]


def build(suffix='reference', direction=1):
    global CASE_ID, SOURCES, SPEC, RECIPE
    if suffix not in ('reference', 'contrast'):
        raise ValueError('Unknown exact comparison suffix')
    if direction not in (-1, 1):
        raise ValueError('Unknown approach direction')
    CASE_ID = ASSIGNMENT + '__' + suffix
    label = suffix if direction == 1 else suffix + '-fallback1'
    SOURCES = ROOT / 'fixtures' / ('sources' if suffix == 'reference' and direction == 1
                                  else label + '-sources')
    SPEC = ROOT / 'fixtures' / (label + '-diagnostic-spec.json')
    RECIPE = ROOT / 'fixtures' / (label + '-recipe.json')
    SOURCES.mkdir(parents=True, exist_ok=True)
    save('road.xodr', open_drive())
    signal = {'officer_id': '206', 'bus_id': '205', 'direction': direction,
              'issued_frame': 0, 'first_governing_frame': 1,
              'last_governing_frame': FRAMES, 'crossing_id':
              'c177225_authored_rail_crossing', 'authorized': True,
              'hand_signal': 'STOP'}
    save('officer_signal_definition.json', encode(signal))
    save('acquisition-provenance.json', encode({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'speed_source': 'synthetic_native_sample',
        'physical_acceptance_claimed': False}))
    save('capture/recorder_info.txt', 'Frame 1\nCreate 205: vehicle.mitsubishi.fusorosa\n')
    trace, evidence, bus_rows, officer_rows, mapping, frame_index, graphs = (
        [] for _ in range(7))
    for index in range(FRAMES):
        frame = index + 1
        time = frame / RATE_HZ
        station = direction * (-70.0 + (min(index * .25, 56.25) if suffix == 'reference'
                                            else index * .25))
        speed = 5.0 if suffix == 'contrast' or index < 225 else 0.0
        position = [station, -1.75 * direction, 0.0]
        velocity = [speed * direction, 0.0, 0.0]
        heading = 0.0 if direction == 1 else 180.0
        observed = {'frame': frame, 'time_s': time,
                    'participants': [],
                    'rgb_sensors': [{'actor_id': 300 + i,
                                     'blueprint': 'sensor.camera.rgb'}
                                    for i in range(4)],
                    'world_settings': {'no_rendering_mode': False},
                    'map_context': {'declared_public_way_road_ids': []}}
        trace.append({'frame': frame, 'time_s': time,
                      'position': {'x': station, 'y': -1.75 * direction, 'z': 0.0},
                      'position_m': position, 'heading_deg': heading,
                      'speed_mps': speed, 'speed_mph': speed / .44704,
                      'velocity_mps': velocity,
                      'control': {'throttle': 0.18 if speed else 0.0,
                                  'brake': 0.0 if speed else 1.0,
                                  'hand_brake': False}})
        evidence.append({'original_frame': frame, 'replay_frame': frame,
                         'actor_id': 205, 'recording_time_s': time,
                         'replay_simulation_time_s': time,
                         'ego': {'position_m': position, 'heading_deg': heading,
                                 'speed_mps': speed,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'body_vertices_m': body(station, direction)},
                         'world': {'weather': {'sun_altitude_angle': 45.0,
                                               'precipitation': 0.0,
                                               'wetness': 0.0}},
                         'original_observations': observed})
        bus_rows.append({'native_frame': frame, 'actor_id': '205',
                         'station_m': station, 'lane_y_native_m': -1.75 * direction,
                         'heading_native_deg': heading,
                         'velocity_native_xyz_mps': velocity,
                         'approach_direction': direction,
                         'source_kind': 'synthetic_native_sample'})
        officer_rows.append({'native_frame': frame, 'actor_id': '206',
                             'recipient_actor_id': '205',
                             'crossing_id': signal['crossing_id'],
                             'direction': direction, 'authorized': True,
                             'hand_signal': 'STOP', 'governing': True,
                             'pose_control_applied': True,
                             'pose_bone_readback': 'crl_arm__R'})
        mapping.append({'video_frame': index, 'carla_frame': frame,
                        'native_frame': frame, 'time_s': time})
        graph_relative = f'graphs/base/{frame:08d}.pkl'
        frame_index.append({'frame': frame, 'simulation_time': time,
                            'base': graph_relative, 'abstract': graph_relative,
                            'nodes': 0, 'edges': 0})
        graphs.append({'path': 'capture/native/' + graph_relative,
                       'attributes': {'frame': frame,
                                      'simulation_time_s': time,
                                      'observed_evidence': observed},
                       'nodes': [], 'edges': []})
    for name, records in (
            ('trace.jsonl', trace), ('capture/evidence.jsonl', evidence),
            ('bus_native_rows.jsonl', bus_rows),
            ('officer_signal_rows.jsonl', officer_rows),
            ('video_frames.jsonl', mapping),
            ('capture/native/frames.jsonl', frame_index)):
        save(name, lines(records))
    save('capture/manifest.json', encode({
        'status': 'draft', 'acquisition': 'synthetic_fixture',
        'case_id': CASE_ID, 'frames': FRAMES,
        'extraction_confirmed': True, 'observation_contract_version': 2,
        'required_observations': [], 'complete_driving_lanes': False,
        'sources': {'road.xodr': sha(SOURCES / 'road.xodr'),
                    'trace.jsonl': sha(SOURCES / 'trace.jsonl')}}))
    videos = [{'path': name + '.mkv', 'frames': FRAMES,
               'width': 1920 if name == 'overview' else 1280,
               'height': 1080 if name == 'overview' else 720,
               'fps': RATE_HZ, 'color': 'black'}
              for name in ('overview', 'approach', 'reference_corner',
                           'driver_reference')]
    SPEC.write_text(encode({'files': {}, 'graphs': graphs, 'videos': videos}))
    if SPEC.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Diagnostic specification exceeds worker text limit')
    sources = [{'path': str(path.relative_to(SOURCES)),
                'source': str(path.relative_to(REPO)), 'sha256': sha(path)}
               for path in sorted(SOURCES.rglob('*')) if path.is_file()]
    RECIPE.write_text(encode({
        'format': 'worker-fixture-recipe', 'sources': sources,
        'generator': {'source': str(SPEC.relative_to(REPO)),
                      'sha256': sha(SPEC)}}))
    return {'recipe': str(RECIPE.relative_to(REPO)),
            'source_count': len(sources), 'graph_count': len(graphs),
            'frames': FRAMES, 'synthetic_native_sample': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case-suffix', choices=('reference', 'contrast'),
                        default='reference')
    parser.add_argument('--direction', type=int, choices=(-1, 1), default=1)
    args = parser.parse_args()
    print(json.dumps(build(args.case_suffix, args.direction)))
