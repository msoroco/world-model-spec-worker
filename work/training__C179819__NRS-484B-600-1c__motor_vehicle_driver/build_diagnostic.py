"""Author small, explicit speed-specific CPU diagnostic source recipes."""
import hashlib
import json
from pathlib import Path

from road import open_drive

HERE = Path(__file__).resolve().parent
ASSIGNMENT = 'training__C179819__NRS-484B-600-1c__motor_vehicle_driver'
TARGETS = {'below_posted': 25.0, 'at_posted': 30.0, 'above_posted': 35.0}
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
    speed = mph*.44704
    frames, motion, trace, evidence, native_frames, graphs = [], [], [], [], [], []
    for index in range(FRAMES):
        t = round(index/RATE, 6)
        x, y = round(5+speed*t, 6), -1.85
        other_x, other_y = 100.0, -5.55
        frames.append({'video_frame': index, 'native_frame': index, 'carla_frame': index,
                       'time_s': t, 'camera_native_frames': {name: index for name in
                                                              ('overview', 'approach', 'reference_corner', 'driver_reference')}})
        motion.append({'video_frame': index, 'native_frame': index, 'time_s': t,
                       'source_kind': 'synthetic_native_sample', 'ego_actor_id': 10,
                       'other_actor_id': 11, 'ego_blueprint': 'vehicle.tesla.model3',
                       'other_blueprint': 'vehicle.tesla.model3', 'driving_state': True,
                       'position_xyz_m': [x, y, .5], 'other_position_xyz_m': [other_x, other_y, .5],
                       'road_id': 1, 'lane_id': -1, 'direction': 'forward',
                       'sign_id': 'authored-signal-30', 'sign_passed': x >= 40,
                       'controller_request_mps': speed,
                       'velocity_x_mps': speed, 'velocity_y_mps': 0, 'velocity_z_mps': 0})
        trace.append({'frame': index, 'time_s': t, 'position_m': [x, y, .5],
                      'position': {'x': x, 'y': y, 'z': .5}, 'velocity_mps': [speed, 0, 0],
                      'speed_mps': speed, 'speed_mph': mph, 'heading_deg': 0,
                      'control': {'throttle': 0, 'brake': 0, 'hand_brake': False}})
        evidence.append({'actor_id': 10, 'original_frame': index, 'replay_frame': index,
                         'recording_time_s': t, 'replay_simulation_time_s': t,
                         'ego': {'position_m': [x, y, .5], 'body_vertices_m': vertices(x,y),
                                 'heading_deg': 0, 'speed_mps': speed,
                                 'speed_provenance': 'synthetic_native_sample', 'synthetic_diagnostic': True},
                         'other_actors': [{'actor_id': 11, 'position_m': [other_x,other_y,.5],
                                           'body_vertices_m': vertices(other_x,other_y)}],
                         'world': {'road_projection': {'road_id': 1, 'lane_id': -1,
                                                       'section_id': 0, 's_m': x},
                                   'weather': {'cloudiness': 0, 'fog_density': 0,
                                               'precipitation': 0, 'wetness': 0}}})
        graph_name = f'capture/native/graphs/base/{index:08d}.adapter.json'
        native_frames.append({'frame': index, 'simulation_time': t,
                              'adapter_graph': f'graphs/base/{index:08d}.adapter.json',
                              'base': f'graphs/base/{index:08d}.adapter.json', 'nodes': 2, 'edges': 0})
        graphs.append({'path': graph_name,
                       'attributes': {'frame': index, 'simulation_time_s': t,
                                      'source': 'C179819 posted-speed CPU diagnostic',
                                      'synthetic_diagnostic': True},
                       'nodes': [{'id': 'ego', 'attributes': {'entity_id': 10, 'sem_class': 'ego',
                                                            'vertex': [x,y,.5], 'forward': [1,0,0],
                                                            'threedbbox': vertices(x,y)}},
                                 {'id': 'other', 'attributes': {'entity_id': 11, 'sem_class': 'vehicle',
                                                              'vertex': [other_x,other_y,.5], 'forward': [1,0,0],
                                                              'threedbbox': vertices(other_x,other_y)}}],
                       'edges': []})
    for path, value in {
        'native_motion.jsonl': lines(motion), 'video_frames.jsonl': lines(frames),
        'trace.jsonl': lines(trace), 'capture/evidence.jsonl': lines(evidence),
        'road.xodr': open_drive()+'\n',
        'road_context.json': json.dumps({'assignment_id': ASSIGNMENT, 'case_id': ASSIGNMENT+'__'+probe,
                                        'review_kind': 'synthetic_diagnostic', 'ego_actor_id': 10,
                                        'other_actor_id': 11, 'reviewer': 'synthetic CPU fixture',
                                        'route_source': 'authored OpenDRIVE diagnostic road',
                                        'vehicle_identity_source': 'synthetic source actor 10',
                                        'other_vehicle_source': 'synthetic separate actor 11',
                                        'driving_state_source': 'synthetic per-frame driving flag',
                                        'sign_id': 'authored-signal-30', 'posted_mph': 30,
                                        'authority_source': 'synthetic public-authority review fixture',
                                        'highway_source': 'synthetic highway-portion review fixture',
                                        'governed_direction': 'forward', 'sign_position_x_m': 40,
                                        'zone_start_m': 40, 'zone_end_m': 1800,
                                        'road_id': 1, 'lane_id': -1,
                                        'road_xodr_sha256': hashlib.sha256((open_drive()+'\n').encode()).hexdigest()}, sort_keys=True)+'\n'
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
                          for path in sorted(sources.rglob('*')) if path.is_file()]}
    write(root/'fixture-recipe.json', recipe)
    return {'case_id': ASSIGNMENT+'__'+probe, 'spec_sha256': sha(spec_path),
            'recipe_sha256': sha(root/'fixture-recipe.json'), 'source_files': len(recipe['sources'])}


if __name__ == '__main__':
    print(json.dumps([make_case(probe, mph) for probe, mph in TARGETS.items()], indent=2))
