"""Create declared synthetic freight sources for the current CPU proof chain."""
import json
from datetime import datetime, timedelta
from pathlib import Path

from build_diagnostic_fixtures import BASE, ROOT, VIEWS, body, lines, sha, write
from freight_plan import PURPOSES


def build(suffix):
    construction = json.loads((BASE / 'native-freight-draft' / suffix / 'construction.json').read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    start = datetime.fromisoformat(config['civil_start_local'])
    taxi_x = config['taxi_stop_x_m']
    root = BASE / 'native' / 'freight-diagnostic' / suffix
    sources = root / 'sources'
    native, mapping, trace, evidence, frames, graphs = [], [], [], [], [], []
    for index in range(600):
        frame, time_s = index + 2000, (index + 1) / 20
        cameras = {view: frame for view in VIEWS}
        progress = min(max(index - 150, 0), 150) / 150
        x = (8.0 - 2.5 * progress if suffix == 'freight_load' else
             5.5 + 2.5 * progress if suffix == 'freight_unload' else 8.0)
        moving = 150 <= index < 300 and suffix != 'freight_wait'
        native.append({'video_frame': index, 'native_frame': frame,
            'time_s': time_s, 'source_kind': 'synthetic_cpu_fixture',
            'civil_time_local': (start + timedelta(seconds=time_s)).isoformat(timespec='milliseconds'),
            'taxi_actor_id': 42, 'taxi_blueprint_id': 'vehicle.tesla.model3',
            'taxi_xyz_m': [taxi_x, 10, .5], 'taxi_body_vertices_xyz_m': body(taxi_x, 10),
            'taxi_velocity_xyz_mps': [0, 0, 0],
            'cargo_actor_id': 44, 'cargo_blueprint_id': 'static.prop.box01',
            'cargo_body_vertices_xyz_m': body(x, 10),
            'cargo_transfer_motion_observed': moving,
            'requested_purpose': PURPOSES[suffix], 'source_cameras': cameras})
        mapping.append({'video_frame': index, 'carla_frame': frame,
                        'native_frame': frame, 'time_s': time_s,
                        'camera_native_frames': cameras})
        trace.append({'frame': frame, 'time_s': time_s, 'taxi_actor_id': 42,
            'position_m': [taxi_x, 10, .5], 'position': {'x': taxi_x, 'y': 10, 'z': .5},
            'heading_deg': 90, 'speed_mps': 0, 'speed_mph': 0,
            'velocity_mps': [0, 0, 0], 'control': {'brake': 1, 'hand_brake': True},
            'source_kind': 'synthetic_cpu_fixture'})
        evidence.append({'actor_id': 42, 'original_frame': frame,
            'replay_frame': frame, 'recording_time_s': time_s,
            'replay_simulation_time_s': time_s,
            'ego': {'position_m': [taxi_x, 10, .5], 'body_vertices_m': body(taxi_x, 10),
                    'heading_deg': 90, 'speed_mps': 0,
                    'speed_provenance': 'synthetic_native_sample',
                    'synthetic_diagnostic': True},
            'other_actors': [{'actor_id': 44, 'position_m': [x, 10, .5],
                              'body_vertices_m': body(x, 10)}],
            'world': {'road_projection': {'road_id': 1, 'lane_id': -2,
                                          'section_id': 0, 's_m': 90}}})
        graph_path = f'capture/native/graphs/base/{index:08d}.adapter.json'
        frames.append({'frame': frame, 'simulation_time': time_s,
                       'adapter_graph': f'graphs/base/{index:08d}.adapter.json',
                       'base': f'graphs/base/{index:08d}.adapter.json',
                       'nodes': 2, 'edges': 0})
        graphs.append({'path': graph_path,
            'attributes': {'frame': frame, 'simulation_time_s': time_s,
                           'synthetic_diagnostic': True},
            'nodes': [{'id': 'ego', 'attributes': {
                'entity_id': 42, 'sem_class': 'ego', 'vertex': [taxi_x, 10, .5],
                'forward': [0, 1, 0], 'threedbbox': body(taxi_x, 10)}},
                {'id': 'cargo', 'attributes': {
                'entity_id': 44, 'sem_class': 'cargo', 'vertex': [x, 10, .5],
                'forward': [1, 0, 0], 'threedbbox': body(x, 10)}}], 'edges': []})
    for name, rows in (('freight-native.jsonl', native),
                       ('video_frames.jsonl', mapping), ('trace.jsonl', trace),
                       ('capture/evidence.jsonl', evidence)):
        write(sources / name, lines(rows))
    for name in ('road.xodr', 'yellow-freight-road.xodr'):
        write(sources / name, (BASE / 'native/yellow-freight-road.xodr').read_text())
    review = {'source_kind': 'synthetic_cpu_fixture', 'synthetic_cpu_fixture': True,
              'source_basis': 'Synthetic taxi/light-express CPU fixture only',
              'legal_verdict': None}
    write(sources / 'sign-authority-pending.json', {
        'source_kind': 'synthetic_cpu_fixture', 'actual_sign_authority_source': None,
        'legal_verdict': None})
    write(sources / 'commercial-status-review.json', {
        **review, 'taxi_actor_id': 42, 'observed_taxicab': True,
        'observed_commercial_use': None,
        'classification_status': 'original_identity_and_use_source_required'})
    write(sources / 'sign-review.json', {**review, 'observed_curb_color': 'yellow',
        'posted_hours_start': '09:00', 'posted_hours_end': '17:00',
        'observed_sign_content': 'synthetic proposed commercial freight hours',
        'sign_authority_status': 'original_authority_source_required'})
    write(sources / 'freight-purpose-review.json', {**review,
        'cargo_actor_id': 44, 'observed_purpose': PURPOSES[suffix],
        'actual_freight_status': 'original_cargo_and_transfer_source_required'})
    write(sources / 'capture/manifest.json', {
        'extraction_confirmed': True, 'frames': 600, 'synthetic_diagnostic': True,
        'sources': {'road.xodr': sha(sources / 'road.xodr'),
                    'freight-native.jsonl': sha(sources / 'freight-native.jsonl'),
                    'trace.jsonl': sha(sources / 'trace.jsonl')}})
    spec = {'files': {
        'capture/native/frames.jsonl': lines(frames),
        'capture/recorder_info.txt': 'Synthetic freight diagnostic; no Native recording.\nCreate 42: vehicle.tesla.model3 (0)\nCreate 44: static.prop.box01 (0)\n'},
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
                           'source': str(path.relative_to(ROOT)), 'sha256': sha(path)}
                          for path in sorted(sources.rglob('*')) if path.is_file()]}
    recipe_path = root / 'fixture-recipe.json'
    write(recipe_path, recipe)
    return {'case_id': config['case_id'], 'recipe': str(recipe_path.relative_to(ROOT)),
            'recipe_sha256': sha(recipe_path)}


if __name__ == '__main__':
    print(json.dumps([build(suffix) for suffix in PURPOSES], indent=2))
