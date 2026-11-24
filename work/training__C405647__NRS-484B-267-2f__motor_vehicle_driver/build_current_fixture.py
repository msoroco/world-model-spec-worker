"""Build source-inventoried synthetic fixtures for current-runtime checks."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from runner import road_xml


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))


def build(suffix):
    case = HERE.name + '__' + suffix
    source = HERE / 'current-fixture' / suffix
    source.mkdir(parents=True, exist_ok=True)
    frames, poses, trace, evidence, native_frames, graphs = [], [], [], [], [], []
    ego_x, em_x = -75.0, -15.0
    for i in range(600):
        time, native = i / 20, 1000 + i
        ego_speed = 1 if suffix == 'controlled_1' and i >= 100 else 3
        em_speed = 2 if i >= 100 else 0
        ego_x += ego_speed / 20
        em_x -= em_speed / 20
        ego = {'actor_id': 107, 'x_m': round(ego_x, 5), 'y_m': -1.75,
               'heading_rad': 0, 'velocity_x_mps': ego_speed, 'velocity_y_mps': 0,
               'speed_mps': ego_speed, 'half_length_m': 2, 'half_width_m': 1}
        em = {'actor_id': 108, 'x_m': round(em_x, 5), 'y_m': 1.75,
              'heading_rad': 3.141592653589793, 'velocity_x_mps': -em_speed,
              'velocity_y_mps': 0, 'speed_mps': em_speed,
              'half_length_m': 2, 'half_width_m': 1,
              'special1_light_on': (i // 10) % 2 == 0}
        frames.append({'video_frame': i, 'native_frame': native,
                       'carla_frame': native, 'time_s': time})
        poses.append({'video_frame': i, 'native_frame': native,
                      'source_kind': 'synthetic_native_sample', 'ego': ego,
                      'emergency': em})
        trace.append({'frame': native, 'time_s': time,
                      'position': {'x': ego['x_m'], 'y': ego['y_m'], 'z': .5},
                      'position_m': [ego['x_m'], ego['y_m'], .5],
                      'heading_deg': 0, 'speed_mps': ego_speed,
                      'speed_mph': ego_speed / .44704,
                      'velocity_mps': [ego_speed, 0, 0],
                      'control': {'throttle': .2, 'brake': 0, 'hand_brake': False}})
        body = [[ego['x_m'] + dx, ego['y_m'] + dy, z]
                for dx in (-2, 2) for dy in (-1, 1) for z in (0, 1.5)]
        em_body = [[em['x_m'] + dx, em['y_m'] + dy, z]
                   for dx in (-2, 2) for dy in (-1, 1) for z in (0, 1.5)]
        evidence.append({'original_frame': native, 'replay_frame': native,
                         'actor_id': 107, 'recording_time_s': time,
                         'replay_simulation_time_s': time,
                         'ego': {'position_m': [ego['x_m'], ego['y_m'], .5],
                                 'heading_deg': 0, 'speed_mps': ego_speed,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'body_vertices_m': body},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 405647,
                                                       'section_id': 0, 'lane_id': -1,
                                                       's_m': ego['x_m'] + 120}}})
        name = f'{native:08d}'
        graphs.append({'path': f'capture/native/graphs/base/{name}.adapter.json',
                       'attributes': {'frame': native, 'simulation_time_s': time,
                                      'synthetic_diagnostic': True},
                       'nodes': [
                           {'id': 'ego', 'attributes': {'sem_class': 'ego', 'entity_id': 107,
                                                      'vertex': [ego['x_m'], ego['y_m'], .5],
                                                      'forward': [1, 0, 0], 'threedbbox': body}},
                           {'id': 'emergency', 'attributes': {'sem_class': 'vehicle',
                                                            'entity_id': 108,
                                                            'vertex': [em['x_m'], em['y_m'], .5],
                                                            'forward': [-1, 0, 0],
                                                            'threedbbox': em_body}}],
                       'edges': []})
        native_frames.append({'frame': native, 'simulation_time': time,
                              'time_s': time,
                              'base': f'graphs/base/{name}.adapter.json',
                              'abstract': f'graphs/abstract/{name}.pkl',
                              'adapter_graph': f'graphs/base/{name}.adapter.json',
                              'synthetic_diagnostic': True})
    for name, rows in [('video_frames.jsonl', frames), ('vehicle_poses.jsonl', poses),
                       ('trace.jsonl', trace), ('capture/evidence.jsonl', evidence),
                       ('capture/native/frames.jsonl', native_frames)]:
        lines(source / name, rows)
    (source / 'road.xodr').write_text(road_xml() + '\n')
    context = {'assignment_id': HERE.name, 'case_id': case,
               'review_kind': 'synthetic_diagnostic', 'reviewer': 'synthetic fixture',
               'ego_actor_id': 107, 'emergency_actor_id': 108,
               'emergency_vehicle_authorized': True,
               'qualifying_flash_equipment_reviewed': True,
               'officer_directed_otherwise': False}
    for key in ('ego_driver_source', 'emergency_authorization_source',
                'qualifying_flash_equipment_source', 'flashing_light_visual_source',
                'lane_boundary_source', 'visibility_review_source',
                'officer_direction_review_source'):
        context[key] = 'synthetic-fixture:' + key
    context['native_source_hashes'] = {
        name: digest(source / name) for name in
        ('video_frames.jsonl', 'vehicle_poses.jsonl', 'trace.jsonl')}
    (source / 'emergency_context.json').write_text(json.dumps(context, indent=2) + '\n')
    (source / 'capture/recorder_info.txt').write_text('Create 107: vehicle.lincoln.mkz_2020\n')
    (source / 'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed': True, 'frames': 600,
        'acquisition': 'synthetic_diagnostic', 'observation_contract_version': 1,
        'required_observations': ['kin.position'],
        'sources': {'road.xodr': digest(source / 'road.xodr'),
                    'trace.jsonl': digest(source / 'trace.jsonl')},
        'synthetic_diagnostic': True}, separators=(',', ':')) + '\n')
    (source / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_local_diagnostic', 'diagnostic_fixture': True,
        'native_executed': False}, separators=(',', ':')) + '\n')
    files = [{'path': p.relative_to(source).as_posix(),
              'source': p.relative_to(ROOT).as_posix(), 'sha256': digest(p)}
             for p in sorted(source.rglob('*')) if p.is_file()]
    spec = {'files': {}, 'graphs': graphs,
            'videos': [{'path': name + '.mkv', 'frames': 600, 'width': width,
                        'height': height, 'fps': 20, 'color': color}
                       for name, width, height, color in (
                           ('overview', 1920, 1080, 'blue'),
                           ('approach', 1280, 720, 'red'),
                           ('reference_corner', 1280, 720, 'green'),
                           ('driver_reference', 1280, 720, 'white'))]}
    spec_path = HERE / f'current-{suffix}-diagnostic.json'
    spec_path.write_text(json.dumps(spec, separators=(',', ':')) + '\n')
    recipe = {'format': 'worker-fixture-recipe', 'sources': files,
              'generator': {'source': spec_path.relative_to(ROOT).as_posix(),
                            'sha256': digest(spec_path)}}
    recipe_path = HERE / f'current-{suffix}-recipe.json'
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    return {'case': suffix, 'recipe_sha256': digest(recipe_path),
            'source_files': len(files), 'graphs': len(graphs)}


if __name__ == '__main__':
    for case_suffix in ('controlled_1', 'controlled_2'):
        print(json.dumps(build(case_suffix)))
