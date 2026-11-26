"""Build source-shaped taxi CPU fixtures; no original activity is inferred."""
import hashlib
import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else
                    json.dumps(value, indent=2, allow_nan=False) + '\n')


def lines(values):
    return ''.join(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n'
                   for value in values)


def body(x, y):
    return [[x + dx, y + dy, z] for dx in (-1, 1) for dy in (-.5, .5)
            for z in (0, 1.5)]


def build(suffix, loading):
    root = HERE / 'diagnostic' / suffix
    sources = root / 'sources'
    native, mapping, trace, evidence, activity, frames, graphs = [], [], [], [], [], [], []
    for index in range(600):
        frame = index + 100
        time_s = (index + 1) / 20
        camera_frames = {view: frame for view in VIEWS}
        active = 160 <= index < 400
        count = 2 if loading == 'merchandise_loading' or index < 400 else 3
        native.append({'video_frame': index, 'native_frame': frame,
                       'time_s': time_s, 'taxi_actor_id': 42,
                       'participant_actor_id': 43,
                       'taxi_blueprint_id': 'vehicle.tesla.model3',
                       'taxi_xyz_m': [5.25, 10, .5],
                       'taxi_velocity_xyz_mps': [0, 0, 0],
                       'participant_xyz_m': [7, 10, .5],
                       'source_cameras': camera_frames,
                       'requested_activity': loading,
                       'requested_activity_active': active})
        mapping.append({'video_frame': index, 'carla_frame': frame,
                        'native_frame': frame, 'time_s': time_s,
                        'camera_native_frames': camera_frames})
        trace.append({'frame': frame, 'time_s': time_s,
                      'taxi_actor_id': 42, 'position_m': [5.25, 10, .5],
                      'position': {'x': 5.25, 'y': 10, 'z': .5},
                      'heading_deg': 0, 'speed_mps': 0, 'speed_mph': 0,
                      'velocity_mps': [0, 0, 0],
                      'control': {'brake': 1, 'hand_brake': True},
                      'source_kind': 'synthetic_cpu_fixture'})
        evidence.append({'actor_id': 42, 'original_frame': frame,
                         'replay_frame': frame, 'recording_time_s': time_s,
                         'replay_simulation_time_s': time_s,
                         'ego': {'position_m': [5.25, 10, .5],
                                 'body_vertices_m': body(5.25, 10),
                                 'heading_deg': 0, 'speed_mps': 0,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'synthetic_diagnostic': True},
                         'other_actors': [{'actor_id': 43,
                                           'position_m': [7, 10, .5],
                                           'body_vertices_m': body(7, 10)}],
                         'world': {'road_projection': {'road_id': 1,
                                                       'lane_id': -2,
                                                       'section_id': 0,
                                                       's_m': 5.25},
                                   'weather': {'cloudiness': 0,
                                               'fog_density': 0,
                                               'precipitation': 0,
                                               'wetness': 0}}})
        activity.append({'video_frame': index, 'native_frame': frame,
                         'time_s': time_s, 'observed_taxi_identity': True,
                         'observed_stand_location': 'outside_designated_stand',
                         'observed_speed_mps': 0,
                         'observed_door_open': active,
                         'observed_occupant_count': count,
                         'observed_activity': loading if active else 'no_activity'})
        graph = f'capture/native/graphs/base/{index:08d}.adapter.json'
        frames.append({'frame': frame, 'simulation_time': time_s,
                       'adapter_graph': f'graphs/base/{index:08d}.adapter.json',
                       'base': f'graphs/base/{index:08d}.adapter.json',
                       'nodes': 2, 'edges': 0})
        graphs.append({'path': graph,
                       'attributes': {'frame': frame, 'simulation_time_s': time_s,
                                      'source': 'C394327 taxi CPU diagnostic',
                                      'synthetic_diagnostic': True},
                       'nodes': [
                           {'id': 'ego', 'attributes': {
                               'entity_id': 42, 'sem_class': 'ego',
                               'vertex': [5.25, 10, .5], 'forward': [1, 0, 0],
                               'threedbbox': body(5.25, 10)}},
                           {'id': 'participant', 'attributes': {
                               'entity_id': 43, 'sem_class': 'pedestrian',
                               'vertex': [7, 10, .5], 'forward': [1, 0, 0],
                               'threedbbox': body(7, 10)}}], 'edges': []})
    for name, values in (('native-rows.jsonl', native),
                         ('video_frames.jsonl', mapping), ('trace.jsonl', trace),
                         ('capture/evidence.jsonl', evidence),
                         ('observed-activity.jsonl', activity)):
        write(sources / name, lines(values))
    write(sources / 'road.xodr', (HERE / 'taxi-road.xodr').read_text())
    for name in ('taxi-license-review.json', 'participant-activity-review.json',
                 'stand-designation-review.json', 'other-regulations-review.json'):
        review = {
            'source_kind': 'synthetic_cpu_fixture', 'synthetic_cpu_fixture': True,
            'review_status': 'diagnostic_only',
            'source_basis': 'Source-shaped synthetic taxi diagnostic, no original authority',
            'legal_verdict': None}
        if name == 'stand-designation-review.json':
            review['observed_sign_content'] = 'synthetic diagnostic stand sign'
        write(sources / name, review)
    write(sources / 'capture/manifest.json', {
        'extraction_confirmed': True, 'frames': 600,
        'synthetic_diagnostic': True,
        'sources': {'road.xodr': sha(sources / 'road.xodr'),
                    'native-rows.jsonl': sha(sources / 'native-rows.jsonl'),
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
    repo = Path.cwd()
    recipe = {'format': 'worker-fixture-recipe',
              'generator': {'source': str(spec_path.relative_to(repo)),
                            'sha256': sha(spec_path)},
              'sources': [{'path': str(path.relative_to(sources)),
                           'source': str(path.relative_to(repo)),
                           'sha256': sha(path)}
                          for path in sorted(sources.rglob('*')) if path.is_file()]}
    recipe_path = root / 'fixture-recipe.json'
    write(recipe_path, recipe)
    return {'case_id': BASE.name + '__' + suffix,
            'recipe_sha256': sha(recipe_path),
            'largest_file_bytes': max(p.stat().st_size for p in root.rglob('*')
                                      if p.is_file())}


if __name__ == '__main__':
    print(json.dumps([build('probe_a', 'passenger_loading'),
                      build('probe_b', 'merchandise_loading')], indent=2))
