"""Make synthetic Native graph/evidence rows for emergency no-worker CPU proof."""
import hashlib
import json
from pathlib import Path
import pickle
import shutil
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.fixture_generator import _GraphInput

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def body_3d(points):
    return [[x, y, z] for x, y in points for z in (0, 1.5)]


def build(attempt):
    attempt = Path(attempt).resolve()
    if REPO / '.runtime-work' not in attempt.parents:
        raise ValueError('Synthetic diagnostic belongs under .runtime-work')
    config = json.loads((attempt / 'config.json').read_text())
    if config['case_id'] != ROOT.name + '__emergency_vehicle_unsigned_no_business' or \
            config.get('activity_request') is not None:
        raise ValueError('This diagnostic requires emergency no-worker activity')
    no_loading = True
    capture = attempt / 'capture'
    graph_dir = capture / 'native/graphs/base'
    if (capture / 'manifest.json').exists() or graph_dir.exists():
        raise ValueError('Retain prior Native diagnostic; use a fresh attempt')
    graph_dir.mkdir(parents=True)
    shutil.copy2(attempt / 'red-curb-road.xodr', attempt / 'road.xodr')
    (attempt / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'native_executed': False}) + '\n')
    actors = (json.loads(line) for line in (attempt / 'native-raw-actors.jsonl').open())
    walkers = ((None for _ in range(config['capture_frames'])) if no_loading
               else (json.loads(line) for line in
                     (attempt / 'native-service-worker-actors.jsonl').open()))
    count = 0
    with (capture / 'evidence.jsonl').open('w') as evidence, \
         (capture / 'native/frames.jsonl').open('w') as frames:
        for actor, walker in zip(actors, walkers, strict=True):
            frame, time_s = actor['frame'], actor['time_s']
            if walker is not None and (walker['frame'] != frame or
                                       walker['time_s'] != time_s):
                raise ValueError('Synthetic bus/walker frame join differs')
            x, y = actor['ego_center_native_xy_m']
            speed = actor['velocity_native_xyz_mps'][0]
            bus = {
                'actor_id': actor['actor_id'], 'blueprint': actor['blueprint'],
                'position_m': [x, y, 0], 'heading_deg': actor['yaw_deg'],
                'velocity_mps': actor['velocity_native_xyz_mps'],
                'speed_mps': abs(speed), 'acceleration_mps2': [0, 0, 0],
                'accel_longitudinal_mps2': 0,
                'body_vertices_m': body_3d(actor['ego_body_native_xy_m']),
                'blueprint_attributes': {'role_name': 'c150142_ego'},
                'light_attributes': {}, 'wheel_steer_angle_deg': 0,
            }
            participants = [bus]
            if walker is not None:
                wx, wy = walker['center_native_xy_m']
                pedestrian = {
                    'actor_id': walker['actor_id'], 'blueprint': walker['blueprint'],
                    'position_m': [wx, wy, 0], 'heading_deg': 0,
                    'velocity_mps': walker['velocity_native_xyz_mps'],
                    'speed_mps': abs(walker['velocity_native_xyz_mps'][1]),
                    'acceleration_mps2': [0, 0, 0],
                    'accel_longitudinal_mps2': 0,
                    'body_vertices_m': body_3d([[wx - .2, wy - .2],
                                                [wx + .2, wy - .2],
                                                [wx + .2, wy + .2],
                                                [wx - .2, wy + .2]]),
                    'blueprint_attributes': {}, 'light_attributes': {},
                }
                participants.append(pedestrian)
            observed = {
                'frame': frame, 'time_s': time_s,
                'participants': participants,
                'world_settings': {'no_rendering_mode': False},
                'rgb_sensors': {view: {'frame': frame} for view in VIEWS},
                'map_context': {'declared_public_way_road_ids': [150142],
                                'core_assumptions': [['asm.public_highway', True]]},
            }
            graph_rel = f'graphs/base/{frame:08d}.pkl'
            item = {'path': 'capture/native/' + graph_rel,
                    'attributes': {'frame': frame, 'observed_evidence': observed},
                    'nodes': [], 'edges': []}
            (graph_dir / f'{frame:08d}.pkl').write_bytes(
                pickle.dumps(_GraphInput(item), protocol=4))
            frames.write(json.dumps({'frame': frame, 'time_s': time_s,
                                     'simulation_time': time_s,
                                     'base': graph_rel}) + '\n')
            evidence.write(json.dumps({
                'original_frame': frame, 'replay_frame': frame,
                'actor_id': bus['actor_id'], 'recording_time_s': time_s,
                'replay_simulation_time_s': time_s,
                'ego': {'position_m': bus['position_m'],
                        'heading_deg': bus['heading_deg'],
                        'speed_mps': bus['speed_mps'],
                        'speed_provenance': 'synthetic_native_sample',
                        'body_vertices_m': bus['body_vertices_m']},
                'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                      'wetness': 0, 'fog_density': 0},
                          'road_projection': {'road_id': 150142,
                                              'section_id': 0, 'lane_id': -2,
                                              's_m': x}},
                'original_observations': observed,
            }) + '\n')
            count += 1
    if count != config['capture_frames']:
        raise ValueError('Native diagnostic frame count differs')
    (capture / 'recorder_info.txt').write_text(
        'Synthetic CPU diagnostic; CARLA recorder did not run.\n'
        'Create 1: ' + config['native_blueprint'] + '\n' +
        ('' if no_loading else 'Create 2: walker.pedestrian.0001\n'))
    (capture / 'manifest.json').write_text(json.dumps({
        'extraction_confirmed': True, 'frames': count,
        'acquisition': 'synthetic_cpu_fixture',
        'observation_contract_version': 2,
        'required_observations': [],
        'sources': {'road.xodr': digest(attempt / 'road.xodr'),
                    'trace.jsonl': digest(attempt / 'trace.jsonl')},
    }, indent=2) + '\n')
    return {'frames': count, 'source_kind': 'synthetic_native_sample',
            'native_executed': False, 'graphs': count,
            'capture_manifest_sha256': digest(capture / 'manifest.json')}


if __name__ == '__main__':
    print(json.dumps(build(sys.argv[1]), sort_keys=True))
