"""Build source-shaped synthetic taxi fixtures for public CPU checks."""
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parents[1]
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value, indent=2) + '\n')


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)


def body(x, y):
    return [[x + dx, y + dy, z] for dx in (-.6, .6)
            for dy in (-1.5, 1.5) for z in (0, 1.5)]


def build(suffix):
    construction = json.loads((BASE / 'native-draft' / suffix / 'construction.json').read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    start = datetime.fromisoformat(config['civil_start_local'])
    x = config['taxi_stop_x_m']
    root = BASE / 'native' / 'diagnostic' / suffix
    sources = root / 'sources'
    native, mapping, trace, evidence, activity, frames, graphs = [], [], [], [], [], [], []
    for index in range(600):
        frame, time_s = index + 1000, (index + 1) / 20
        cameras = {view: frame for view in VIEWS}
        motion = 160 <= index < 280 and config['requested_purpose'] != 'waiting_for_passengers'
        native.append({'video_frame': index, 'native_frame': frame,
            'time_s': time_s, 'source_kind': 'synthetic_cpu_fixture',
            'civil_time_local': (start + timedelta(seconds=time_s)).isoformat(timespec='milliseconds'),
            'taxi_actor_id': 42, 'taxi_blueprint_id': 'vehicle.tesla.model3',
            'taxi_xyz_m': [x, 10, .5], 'taxi_body_vertices_xyz_m': body(x, 10),
            'taxi_velocity_xyz_mps': [0, 0, 0],
            'passenger_proxy_id': 43, 'passenger_proxy_xyz_m': [x + 2, 10, .5],
            'requested_purpose': config['requested_purpose'],
            'requested_passenger_motion_active': motion,
            'source_cameras': cameras})
        mapping.append({'video_frame': index, 'carla_frame': frame,
                        'native_frame': frame, 'time_s': time_s,
                        'camera_native_frames': cameras})
        trace.append({'frame': frame, 'time_s': time_s, 'taxi_actor_id': 42,
            'position_m': [x, 10, .5], 'position': {'x': x, 'y': 10, 'z': .5},
            'heading_deg': 90, 'speed_mps': 0, 'speed_mph': 0,
            'velocity_mps': [0, 0, 0],
            'control': {'brake': 1, 'hand_brake': True},
            'source_kind': 'synthetic_cpu_fixture'})
        evidence.append({'actor_id': 42, 'original_frame': frame,
            'replay_frame': frame, 'recording_time_s': time_s,
            'replay_simulation_time_s': time_s,
            'ego': {'position_m': [x, 10, .5], 'body_vertices_m': body(x, 10),
                    'heading_deg': 90, 'speed_mps': 0,
                    'speed_provenance': 'synthetic_native_sample',
                    'synthetic_diagnostic': True},
            'other_actors': [{'actor_id': 43, 'position_m': [x + 2, 10, .5],
                              'body_vertices_m': body(x + 2, 10)}],
            'world': {'road_projection': {'road_id': 1, 'lane_id': -2,
                                          'section_id': 0, 's_m': 90}}})
        purpose = config['requested_purpose']
        occupancy = (1 if purpose == 'waiting_for_passengers' else
                     (1 if index < 280 else 2) if purpose == 'loading_passengers' else
                     (2 if index < 280 else 1))
        activity.append({'video_frame': index, 'native_frame': frame,
            'time_s': time_s, 'source_kind': 'synthetic_cpu_fixture',
            'observed_door_open': motion, 'observed_occupant_count': occupancy,
            'observed_purpose': purpose})
        graph_path = f'capture/native/graphs/base/{index:08d}.adapter.json'
        frames.append({'frame': frame, 'simulation_time': time_s,
                       'adapter_graph': f'graphs/base/{index:08d}.adapter.json',
                       'base': f'graphs/base/{index:08d}.adapter.json',
                       'nodes': 2, 'edges': 0})
        graphs.append({'path': graph_path,
            'attributes': {'frame': frame, 'simulation_time_s': time_s,
                           'synthetic_diagnostic': True},
            'nodes': [{'id': 'ego', 'attributes': {
                'entity_id': 42, 'sem_class': 'ego', 'vertex': [x, 10, .5],
                'forward': [0, 1, 0], 'threedbbox': body(x, 10)}},
                {'id': 'passenger', 'attributes': {
                'entity_id': 43, 'sem_class': 'pedestrian',
                'vertex': [x + 2, 10, .5], 'forward': [1, 0, 0],
                'threedbbox': body(x + 2, 10)}}], 'edges': []})
    for name, rows in (('yellow-zone-native.jsonl', native),
                       ('video_frames.jsonl', mapping), ('trace.jsonl', trace),
                       ('capture/evidence.jsonl', evidence),
                       ('observed-passenger-activity.jsonl', activity)):
        write(sources / name, lines(rows))
    write(sources / 'road.xodr', (BASE / 'native' / 'yellow-road.xodr').read_text())
    write(sources / 'sign-authority-pending.json', {
        'source_kind': 'synthetic_cpu_fixture', 'actual_sign_authority_source': None,
        'legal_verdict': None})
    review = {'source_kind': 'synthetic_cpu_fixture', 'synthetic_cpu_fixture': True,
              'source_basis': 'Source-shaped diagnostic only', 'legal_verdict': None}
    write(sources / 'taxicab-review.json', {**review, 'observed_taxicab': True})
    write(sources / 'sign-review.json', {**review, 'observed_curb_color': 'yellow',
        'posted_hours_start': '09:00', 'posted_hours_end': '17:00',
        'observed_sign_content': 'synthetic proposed taxi passenger hours'})
    write(sources / 'passenger-purpose-review.json', {
        **review, 'observed_purpose': config['requested_purpose']})
    write(sources / 'ordinary-rules-review.json', {**review, 'review_status': 'unresolved'})
    write(sources / 'capture/manifest.json', {
        'extraction_confirmed': True, 'frames': 600,
        'synthetic_diagnostic': True,
        'sources': {'road.xodr': sha(sources / 'road.xodr'),
                    'yellow-zone-native.jsonl': sha(sources / 'yellow-zone-native.jsonl'),
                    'trace.jsonl': sha(sources / 'trace.jsonl')}})
    spec = {'files': {
        'capture/native/frames.jsonl': lines(frames),
        'capture/recorder_info.txt': 'Synthetic taxi diagnostic; no Native recording.\nCreate 42: vehicle.tesla.model3 (0)\nCreate 43: walker.pedestrian.0001 (0)\n'},
        'graphs': graphs,
        'videos': [{'path': view + '.mkv', 'frames': 600,
                    'width': 1920 if view == 'overview' else 1280,
                    'height': 1080 if view == 'overview' else 720,
                    'fps': 20, 'color': 'black'} for view in VIEWS]}
    spec_path = root / 'fixture-spec.json'
    write(spec_path, spec)
    recipe = {'format': 'worker-fixture-recipe',
              'generator': {'source': str(spec_path.relative_to(ROOT)),
                            'sha256': sha(spec_path)},
              'sources': [{'path': str(path.relative_to(sources)),
                           'source': str(path.relative_to(ROOT)),
                           'sha256': sha(path)}
                          for path in sorted(sources.rglob('*')) if path.is_file()]}
    recipe_path = root / 'fixture-recipe.json'
    write(recipe_path, recipe)
    return {'case_id': config['case_id'], 'recipe': str(recipe_path.relative_to(ROOT)),
            'recipe_sha256': sha(recipe_path)}


if __name__ == '__main__':
    print(json.dumps([build(s) for s in ('probe_a', 'probe_b', 'probe_c', 'probe_d')],
                     indent=2))
