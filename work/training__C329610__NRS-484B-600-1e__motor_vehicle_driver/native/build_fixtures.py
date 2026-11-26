"""Author small, explicit speed-specific CPU diagnostic source recipes."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSIGNMENT = 'training__C329610__NRS-484B-600-1e__motor_vehicle_driver'
TARGETS = {'probe_a': 75.0, 'probe_at': 80.0, 'probe_b': 85.0}
RATE = 20
FRAMES = 600


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value, indent=2, sort_keys=True)+'\n')


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), sort_keys=True)+'\n' for row in rows)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vertices(x, y):
    return [[x+dx, y+dy, z] for dx in (-2, 2) for dy in (-.9, .9) for z in (0, 1.5)]


def make_case(probe, mph):
    root = HERE/'diagnostic'/probe
    sources = root/'sources'
    draft = json.loads((ROOT/'draft-native'/probe/'construction.json').read_text())
    contents = {row['path']: row['content'] for row in draft['files']}
    requested = [json.loads(row) for row in contents['requested-track.jsonl'].splitlines()]
    frames, motion, trace, evidence, native_frames, graphs = [], [], [], [], [], []
    for index in range(FRAMES):
        t = round(index/RATE, 6)
        request = requested[index]
        x, y, _ = request['ego_center_xyz_m']
        vx, vy, vz = request['ego_velocity_xyz_mps']
        speed = (vx*vx+vy*vy+vz*vz)**.5
        heading = __import__('math').degrees(__import__('math').atan2(vy, vx))
        other_x, other_y = 100.0, -5.55
        frames.append({'video_frame': index, 'native_frame': index, 'carla_frame': index,
                       'time_s': t, 'camera_native_frames': {name: index for name in
                                                              ('overview', 'approach', 'reference_corner', 'driver_reference')}})
        motion.append({'video_frame': index, 'native_frame': index, 'time_s': t,
                       'source_kind': 'synthetic_native_sample', 'ego_actor_id': 10,
                       'other_actor_id': 11, 'ego_blueprint': 'vehicle.tesla.model3',
                       'other_blueprint': 'vehicle.tesla.model3', 'driving_state': True,
                       'position_xyz_m': [x, y, .5], 'other_position_xyz_m': [other_x, other_y, .5],
                       'road_id': request['road_id'], 'lane_id': -1, 'controller_request_mps': speed,
                       'velocity_x_mps': vx, 'velocity_y_mps': vy, 'velocity_z_mps': vz})
        trace.append({'frame': index, 'time_s': t, 'position_m': [x, y, .5],
                      'position': {'x': x, 'y': y, 'z': .5}, 'velocity_mps': [vx, vy, vz],
                      'speed_mps': speed, 'speed_mph': speed/.44704, 'heading_deg': heading,
                      'control': {'throttle': 0, 'brake': 0, 'hand_brake': False}})
        evidence.append({'actor_id': 10, 'original_frame': index, 'replay_frame': index,
                         'recording_time_s': t, 'replay_simulation_time_s': t,
                         'ego': {'position_m': [x, y, .5], 'body_vertices_m': vertices(x,y),
                                 'heading_deg': heading, 'speed_mps': speed,
                                 'speed_provenance': 'synthetic_native_sample', 'synthetic_diagnostic': True},
                         'other_actors': [{'actor_id': 11, 'position_m': [other_x,other_y,.5],
                                           'body_vertices_m': vertices(other_x,other_y)}],
                         'world': {'road_projection': {'road_id': request['road_id'], 'lane_id': -1,
                                                       'section_id': 0, 's_m': x},
                                   'weather': {'cloudiness': 0, 'fog_density': 0,
                                               'precipitation': 0, 'wetness': 0}}})
        graph_name = f'capture/native/graphs/base/{index:08d}.adapter.json'
        native_frames.append({'frame': index, 'simulation_time': t,
                              'adapter_graph': f'graphs/base/{index:08d}.adapter.json',
                              'base': f'graphs/base/{index:08d}.adapter.json', 'nodes': 2, 'edges': 0})
        graphs.append({'path': graph_name,
                       'attributes': {'frame': index, 'simulation_time_s': t,
                                      'source': 'C329610 left-turn absolute-speed CPU diagnostic',
                                      'synthetic_diagnostic': True},
                       'nodes': [{'id': 'ego', 'attributes': {'entity_id': 10, 'sem_class': 'ego',
                                                            'vertex': [x,y,.5], 'forward': [vx/speed,vy/speed,0],
                                                            'threedbbox': vertices(x,y)}},
                                 {'id': 'other', 'attributes': {'entity_id': 11, 'sem_class': 'vehicle',
                                                              'vertex': [other_x,other_y,.5], 'forward': [vx/speed,vy/speed,0],
                                                              'threedbbox': vertices(other_x,other_y)}}],
                       'edges': []})
    for path, value in {
        'native_motion.jsonl': lines(motion), 'video_frames.jsonl': lines(frames),
        'trace.jsonl': lines(trace), 'capture/evidence.jsonl': lines(evidence),
        'road.xodr': (HERE/'road.xodr').read_text(),
        'road_context.json': json.dumps({'assignment_id': ASSIGNMENT, 'case_id': ASSIGNMENT+'__'+probe,
                                        'review_kind': 'synthetic_diagnostic', 'ego_actor_id': 10,
                                        'other_actor_id': 11, 'reviewer': 'synthetic CPU fixture',
                                        'route_source': 'source-hashed authored C329610 left-turn OpenDRIVE road',
                                        'vehicle_identity_source': 'synthetic source actor 10',
                                        'other_vehicle_source': 'synthetic separate actor 11',
                                        'driving_state_source': 'synthetic per-frame driving flag'}, sort_keys=True)+'\n'
    }.items():
        write(sources/path, value)
    write(sources/'capture/manifest.json', {'extraction_confirmed': True, 'frames': FRAMES,
                                            'synthetic_diagnostic': True,
                                            'sources': {'road.xodr': sha(sources/'road.xodr'),
                                                        'trace.jsonl': sha(sources/'trace.jsonl')}})
    spec = {'files': {'capture/native/frames.jsonl': lines(native_frames),
                      'capture/recorder_info.txt': 'Synthetic CPU diagnostic; no Native recording or physical acceptance.\nCreate 10: vehicle.tesla.model3 (0)\nCreate 11: vehicle.tesla.model3 (0)\n'},
            'graphs': graphs,
            'videos': [{'path': name+'.mkv', 'frames': FRAMES,
                        'width': 1920 if name == 'overview' else 1280,
                        'height': 1080 if name == 'overview' else 720,
                        'fps': 20, 'color': 'black'} for name in
                       ('overview', 'approach', 'reference_corner', 'driver_reference')]}
    spec_path = root/'fixture-spec.json'
    write(spec_path, spec)
    repo = Path.cwd()
    recipe = {'format': 'worker-fixture-recipe',
              'generator': {'source': str(spec_path.relative_to(repo)), 'sha256': sha(spec_path)},
              'sources': [{'path': str(path.relative_to(sources)),
                           'source': str(path.relative_to(repo)), 'sha256': sha(path)}
                          for path in sorted(sources.rglob('*')) if path.is_file() and path.name != 'road.xodr']}
    write(root/'fixture-recipe.json', recipe)
    return {'case_id': ASSIGNMENT+'__'+probe, 'spec_sha256': sha(spec_path),
            'recipe_sha256': sha(root/'fixture-recipe.json'), 'source_files': len(recipe['sources'])}


if __name__ == '__main__':
    print(json.dumps([make_case(probe, mph) for probe, mph in TARGETS.items()], indent=2))
