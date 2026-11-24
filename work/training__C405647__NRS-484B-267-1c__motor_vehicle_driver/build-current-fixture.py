"""Build six source-inventoried diagnostic fixtures for current portable runtime."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
CASES = ('probe_a', 'probe_b', 'exception_1_1', 'exception_1_2', 'official_1', 'official_2')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value, separators=(',', ':')) + '\n' for value in values))


def build(suffix):
    source = HERE / 'current-fixture' / suffix
    source.mkdir(parents=True, exist_ok=True)
    construction = json.loads((HERE / 'draft-native' / suffix / 'primary/construction.json').read_text())
    requests = [json.loads(row) for row in next(file['content'] for file in construction['files']
                                                 if file['path'] == 'requested-track.jsonl').splitlines()]
    actor_rows, trace, mapping, evidence, frames, graphs = [], [], [], [], [], []
    for index, request in enumerate(requests):
        native_frame, time = index + 1000, index / 20
        sx, sy = request['ego_center_xy_m']
        ax, ay = request['emergency_center_xy_m']
        ego_body = request['ego_body_xy_m']
        emergency_body = request['emergency_body_xy_m']
        actor_rows.append({'frame': index, 'video_frame': index, 'native_frame': native_frame,
                           'time_s': time, 'source_kind': 'synthetic_cpu',
                           'subject': {'center_xy_m': [sx, sy], 'body_xy_m': ego_body,
                                       'speed_mps': request['ego_speed_mps']},
                           'approach': {'center_xy_m': [ax, ay], 'body_xy_m': emergency_body,
                                        'speed_mps': 2.0},
                           'lamp_request': request['requested_flashing_lights'],
                           'approach_kind_request': request['requested_approach_kind'],
                           'officer_direction_request': request['requested_officer_direction']})
        trace.append({'frame': native_frame, 'time_s': time,
                      'position': {'x': sx, 'y': sy, 'z': .5},
                      'position_m': [sx, sy, .5], 'heading_deg': 90,
                      'speed_mps': request['ego_speed_mps'],
                      'speed_mph': request['ego_speed_mps'] / .44704,
                      'velocity_mps': [0, request['ego_speed_mps'], 0],
                      'control': {'throttle': 0, 'brake': 1 if request['ego_speed_mps'] == 0 else 0,
                                  'hand_brake': False}})
        mapping.append({'video_frame': index, 'native_frame': native_frame,
                        'carla_frame': native_frame, 'time_s': time})
        body3 = [[x, y, z] for x, y in ego_body for z in (0, 1.5)]
        approach3 = [[x, y, z] for x, y in emergency_body for z in (0, 1.5)]
        evidence.append({'original_frame': native_frame, 'replay_frame': native_frame,
                         'actor_id': 107, 'recording_time_s': time,
                         'replay_simulation_time_s': time,
                         'ego': {'position_m': [sx, sy, .5], 'heading_deg': 90,
                                 'speed_mps': request['ego_speed_mps'],
                                 'speed_provenance': 'synthetic_native_sample',
                                 'body_vertices_m': body3},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 1, 'section_id': 0,
                                                       'lane_id': -2, 's_m': sy + 90}}})
        name = f'{native_frame:08d}'
        graphs.append({'path': f'capture/native/graphs/base/{name}.adapter.json',
                       'attributes': {'frame': native_frame, 'simulation_time_s': time,
                                      'synthetic_diagnostic': True},
                       'nodes': [
                           {'id': 'ego', 'attributes': {'sem_class': 'ego', 'entity_id': 107,
                                                      'vertex': [sx, sy, .5],
                                                      'forward': [0, 1, 0], 'threedbbox': body3}},
                           {'id': 'approach', 'attributes': {'sem_class': 'vehicle', 'entity_id': 108,
                                                           'vertex': [ax, ay, .5],
                                                           'forward': [0, 1, 0],
                                                           'threedbbox': approach3}}],
                       'edges': []})
        frames.append({'frame': native_frame, 'simulation_time': time, 'time_s': time,
                       'base': f'graphs/base/{name}.adapter.json',
                       'abstract': f'graphs/abstract/{name}.pkl',
                       'adapter_graph': f'graphs/base/{name}.adapter.json',
                       'synthetic_diagnostic': True})
    lines(source / 'actor-frames.jsonl', actor_rows)
    lines(source / 'trace.jsonl', trace)
    lines(source / 'video_frames.jsonl', mapping)
    lines(source / 'capture/evidence.jsonl', evidence)
    lines(source / 'capture/native/frames.jsonl', frames)
    road = HERE / 'native/emergency-road.xodr'
    (source / 'road.xodr').write_bytes(road.read_bytes())
    (source / 'capture/recorder_info.txt').write_text('Create 107: vehicle.lincoln.mkz_2020\n')
    (source / 'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed': True, 'frames': 600, 'acquisition': 'synthetic_diagnostic',
        'observation_contract_version': 1,
        'required_observations': ['rel.same_direction', 'rel.surface_gap',
                                  'kin.position'],
        'sources': {'road.xodr': sha(source / 'road.xodr'),
                    'trace.jsonl': sha(source / 'trace.jsonl')},
        'synthetic_diagnostic': True}, separators=(',', ':')) + '\n')
    (source / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_local_diagnostic', 'diagnostic_fixture': True,
        'native_executed': False}, separators=(',', ':')) + '\n')
    scope = {'case_suffix': suffix, 'source_kind': 'synthetic_cpu',
             'approach_kind_request': requests[0]['requested_approach_kind'],
             'officer_direction_request': requests[0]['requested_officer_direction'],
             'original_authority_verified': False,
             'qualifying_lamps_verified': False,
             'original_officer_direction_verified': False,
             'native_source_hashes': {'actor-frames.jsonl': sha(source / 'actor-frames.jsonl'),
                                      'trace.jsonl': sha(source / 'trace.jsonl'),
                                      'video_frames.jsonl': sha(source / 'video_frames.jsonl')}}
    (source / 'context-scope.json').write_text(json.dumps(scope, indent=2) + '\n')
    files = [{'path': path.relative_to(source).as_posix(),
              'source': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)}
             for path in sorted(source.rglob('*')) if path.is_file() and path.name != 'road.xodr']
    files.append({'path': 'road.xodr', 'source': road.relative_to(ROOT).as_posix(),
                  'sha256': sha(road)})
    diagnostic = {'files': {}, 'graphs': graphs,
                  'videos': [{'path': name + '.mkv', 'frames': 600, 'width': width,
                              'height': height, 'fps': 20, 'color': color}
                             for name, width, height, color in (
                                 ('overview', 1920, 1080, 'blue'),
                                 ('approach', 1280, 720, 'red'),
                                 ('reference_corner', 1280, 720, 'green'),
                                 ('driver_reference', 1280, 720, 'white'))]}
    spec = HERE / f'current-{suffix}-diagnostic.json'
    spec.write_text(json.dumps(diagnostic, separators=(',', ':')) + '\n')
    recipe = {'format': 'worker-fixture-recipe', 'sources': files,
              'generator': {'source': spec.relative_to(ROOT).as_posix(),
                            'sha256': sha(spec)}}
    target = HERE / f'current-{suffix}-recipe.json'
    target.write_text(json.dumps(recipe, indent=2) + '\n')
    return {'case': suffix, 'sources': len(files), 'graphs': len(graphs),
            'recipe_sha256': sha(target)}


if __name__ == '__main__':
    for suffix in CASES:
        print(json.dumps(build(suffix)))
