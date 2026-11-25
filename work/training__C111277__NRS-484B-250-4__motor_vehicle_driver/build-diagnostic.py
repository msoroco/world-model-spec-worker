"""Create 600-frame textual Native-shaped software fixtures for exact cases."""
import hashlib
import json
from pathlib import Path

from native.generate_fixture import x_at

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = 'training__C111277__NRS-484B-250-4__motor_vehicle_driver'
CASES = [item['case_id'] for item in json.loads((ROOT / 'case-plan.json').read_text())['cases']]


def lines(values):
    return ''.join(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n'
                   for value in values)


def make(index):
    condition = ('halt', 'roll')[index]
    case_id = CASES[index]
    geometry = {'source_kind': 'synthetic_native_sample',
                'ego_incoming_lane': 'road_1_lane_-1',
                'stop_line_present': False, 'near_crosswalk_present': True,
                'crosswalk_near_edge_x_m': -12.0,
                'intersection_entry_x_m': -9.0}
    signal = {'source_kind': 'synthetic_native_sample', 'installed': True,
              'uncovered': True, 'inoperative_observed': True,
              'controlled_incoming_lane': 'road_1_lane_-1',
              'physical_pixels_verified': False}
    native = []
    mapping = []
    trace = []
    evidence = []
    motion = []
    for i in range(600):
        frame = i + 100
        x = round(x_at(condition, i) - 12, 6)
        prior = round(x_at(condition, max(0, i - 1)) - 12, 6)
        successor = round(x_at(condition, 1) - 12, 6)
        speed = round(max(0.0, ((successor - x) if i == 0 else (x - prior)) * 20), 6)
        body = [[x - 4.5, -.8, 0], [x - 4.5, -2.7, 0],
                [x, -.8, 0], [x, -2.7, 0]]
        native.append({'frame': i, 'native_frame': frame, 'time_s': i / 20,
                       'ego_front_x_m': x, 'ego_speed_mps': speed,
                       'other_speed_mps': 0.0 if 80 <= i <= 100 else 4.0,
                       'other_in_intersection': 120 <= i <= 240,
                       'source_kind': 'synthetic_native_sample'})
        mapping.append({'video_frame': i, 'carla_frame': frame,
                        'native_frame': frame, 'time_s': i / 20,
                        'camera_native_frames': {name: frame for name in
                                                 ('overview', 'approach', 'reference_corner',
                                                  'driver_reference')}})
        trace.append({'frame': frame, 'time_s': i / 20,
                      'position': {'x': x - 2.25, 'y': -1.75, 'z': 0},
                      'position_m': [x - 2.25, -1.75, 0],
                      'heading_deg': 0, 'speed_mps': speed,
                      'control': {}})
        evidence.append({'original_frame': frame, 'recording_time_s': i / 20,
                         'replay_frame': frame, 'replay_simulation_time_s': i / 20,
                         'actor_id': 1,
                         'ego': {'body_vertices_m': body,
                                 'position_m': [x - 2.25, -1.75, 0],
                                 'heading_deg': 0, 'speed_mps': speed},
                         'world': {},
                         'visibility': {'method': 'synthetic_body_ray_proxy',
                                        'approaches': [], 'unknown': True},
                         'original_observations': {'relations': [
                             {'a': 1, 'b': 2, 'visible': True,
                              'method': 'synthetic_any_body_ray', 'rays': []}]}})
        motion.append({'frame': frame, 'time_s': i / 20,
                       'states': {'ego': {'body_vertices_m': body}},
                       'signal_actor_id': 3, 'signal_state': 'Off',
                       'other_actor_id': 2,
                       'other_in_intersection': 120 <= i <= 240})
    files = {'geometry.json': json.dumps(geometry, indent=2) + '\n',
             'signal.json': json.dumps(signal, indent=2) + '\n',
             'native-rows.jsonl': lines(native),
             'video_frames.jsonl': lines(mapping),
             'trace.jsonl': lines(trace),
             'capture/evidence.jsonl': lines(evidence),
             'interaction_history.jsonl': lines(motion),
             'signal_context.json': json.dumps({
                 'intersection_polygon_xy_m': [[-9, -7], [7, -7], [7, 7], [-9, 7]],
                 'crosswalk_near_edge_x_m': -12,
                 'signal_actor_id': 3}, indent=2) + '\n',
             'capture/manifest.json': json.dumps({
                 'frames': 600, 'extraction_confirmed': True,
                 'case_id': case_id, 'acquisition': 'synthetic_fixture'}, indent=2) + '\n',
             'acquisition-provenance.json': json.dumps({
                 'provenance_kind': 'synthetic_fixture',
                 'diagnostic_fixture': True}, indent=2) + '\n'}
    files['capture/native/frames.jsonl'] = lines([
        {'abstract': f'graphs/base/{i + 100:08d}.adapter.json',
         'adapter_graph': f'graphs/base/{i + 100:08d}.adapter.json',
         'base': f'graphs/base/{i + 100:08d}.adapter.json',
         'edges': 0, 'frame': i + 100, 'nodes': 0,
         'simulation_time': i / 20, 'synthetic_diagnostic': True,
         'time_s': i / 20} for i in range(600)])
    hashes = {name: hashlib.sha256(files[name].encode()).hexdigest()
              for name in ('geometry.json', 'signal.json', 'native-rows.jsonl')}
    files['native-index.json'] = json.dumps({
        'format': 'nrs-484b-250-4-diagnostic-source-index-v1',
        'assignment_id': ASSIGNMENT, 'condition': condition, 'case_id': case_id,
        'frames': 600, 'rate_hz': 20, 'files': hashes}, indent=2) + '\n'
    graphs = [{'path': f'capture/native/graphs/base/{i + 100:08d}.adapter.json',
               'attributes': {'frame': i + 100, 'simulation_time_s': i / 20,
                              'synthetic_diagnostic': True},
               'nodes': [], 'edges': []} for i in range(600)]
    videos = [{'path': name + '.mkv', 'frames': 600, 'width': width,
               'height': height, 'fps': 20, 'color': 'black'}
              for name, width, height in (('overview', 1920, 1080),
                                          ('approach', 1280, 720),
                                          ('reference_corner', 1280, 720),
                                          ('driver_reference', 1280, 720))]
    output = ROOT / ('diagnostic-' + condition + '.json')
    output.write_text(json.dumps({'files': files, 'graphs': graphs, 'videos': videos},
                                 separators=(',', ':'), allow_nan=False) + '\n')
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json',
                           'source': str(output.relative_to(ROOT.parents[1])),
                           'sha256': checksum}],
              'generator': {'source': str(output.relative_to(ROOT.parents[1])),
                            'sha256': checksum}}
    (ROOT / ('diagnostic-' + condition + '-recipe.json')).write_text(
        json.dumps(recipe, indent=2) + '\n')
    return {'condition': condition, 'bytes': output.stat().st_size}


if __name__ == '__main__':
    print(json.dumps([make(0), make(1)]))
