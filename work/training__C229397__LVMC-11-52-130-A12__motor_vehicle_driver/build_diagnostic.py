"""Build a bounded textual crosswalk compatibility fixture, never evidence."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

from crosswalk_measure import body_corners
from native.geometry import open_drive
from prove_saved import write_attempt

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CASES = {'controlled_1': -14.0, 'controlled_2': -5.0,
         'boundary_20ft': -8.096, 'stop_near': -5.0, 'stand_near': -5.0}


def compact(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False)


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def build(suffix, center_x):
    with tempfile.TemporaryDirectory(prefix='c229397-fixture-source-') as directory:
        source = Path(directory)
        poses, mapping, _ = write_attempt(source, center_x)
        files = {name: (source / name).read_text() for name in
                 ('vehicle-poses.jsonl', 'control-intent.jsonl', 'video_frames.jsonl',
                  'crosswalk-inventory.json', 'crosswalk-source-review.json',
                  'synthetic-original-review-source.txt', 'trace.jsonl')}
    controls = [json.loads(row) for row in files['control-intent.jsonl'].splitlines()]
    if suffix != 'controlled_2':
        for i, control in enumerate(controls):
            control['engineering_action'] = suffix
            control['applied_control']['hand_brake'] = suffix in (
                'controlled_1', 'boundary_20ft')
            if suffix == 'stop_near' and i >= 300:
                control['applied_control'] = {'throttle': .25, 'brake': 0.0,
                                              'hand_brake': False}
        files['control-intent.jsonl'] = ''.join(compact(row) + '\n' for row in controls)
    road = open_drive()
    files['road.xodr'] = road
    files['trace.jsonl'] = ''.join(compact({
        'frame': pose['native_frame'], 'time_s': pose['time_s'],
        'position': {'x': pose['vehicle_xy_m'][0], 'y': pose['vehicle_xy_m'][1], 'z': 8.0},
        'position_m': [*pose['vehicle_xy_m'], 8.0], 'heading_deg': 0.0,
        'speed_mps': pose['speed_mps'], 'speed_mph': pose['speed_mps'] / .44704,
        'velocity_mps': [pose['speed_mps'], 0.0, 0.0],
        'control': controls[i]['applied_control']}) + '\n'
        for i, pose in enumerate(poses))
    files['acquisition-provenance.json'] = compact({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'native_executed': False}) + '\n'
    capture_rows = []
    native_rows = []
    graphs = []
    for pose, frame in zip(poses, mapping):
        i, t = frame['video_frame'], frame['time_s']
        corners = body_corners(pose)
        vertices = [[x, y, z] for x, y in corners for z in (-.7, .7)]
        participant = {'actor_id': 10, 'blueprint': 'vehicle.tesla.model3',
                       'body_vertices_m': vertices, 'heading_deg': 0.0,
                       'velocity_mps': [pose['speed_mps'], 0, 0],
                       'speed_mps': pose['speed_mps'], 'accel_longitudinal_mps2': 0.0}
        observed = {'frame': pose['native_frame'], 'time_s': t, 'participants': [participant],
                    'world_settings': {'no_rendering_mode': False},
                    'rgb_sensors': {camera: {'frame': i} for camera in CAMERAS}}
        graph_rel = 'graphs/base/' + f'{i:08d}.adapter.json'
        graphs.append({'path': 'capture/native/' + graph_rel,
                       'attributes': {'frame': i, 'observed_evidence': observed},
                       'nodes': [], 'edges': []})
        native_rows.append({'frame': i, 'time_s': t, 'simulation_time': t,
                            'base': graph_rel, 'adapter_graph': graph_rel})
        capture_rows.append({'original_frame': pose['native_frame'], 'replay_frame': i,
                             'actor_id': 10,
                             'recording_time_s': t, 'replay_simulation_time_s': t,
                             'ego': {'position_m': [*pose['vehicle_xy_m'], 8.0],
                                     'heading_deg': 0.0, 'speed_mps': pose['speed_mps'],
                                     'speed_provenance': 'synthetic_native_sample',
                                     'body_vertices_m': vertices},
                             'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                                   'wetness': 0, 'fog_density': 0},
                                       'road_projection': {'road_id': 1, 'section_id': 0,
                                                           'lane_id': -2, 's_m': 50 + pose['vehicle_xy_m'][0]}},
                             'original_observations': observed})
    files['capture/evidence.jsonl'] = ''.join(compact(row) + '\n' for row in capture_rows)
    files['capture/native/frames.jsonl'] = ''.join(compact(row) + '\n' for row in native_rows)
    files['capture/recorder_info.txt'] = 'Create 10: vehicle.tesla.model3 (0) at (-5, -1.75, 8)\nSynthetic CPU diagnostic; no CARLA recorder\n'
    files['capture/manifest.json'] = compact({
        'extraction_confirmed': True, 'frames': 600,
        'acquisition': 'synthetic_cpu_fixture', 'observation_contract_version': 2,
        'required_observations': [],
        'sources': {'road.xodr': sha(road), 'trace.jsonl': sha(files['trace.jsonl'])}}) + '\n'
    videos = [{'path': camera + '.mkv', 'frames': 600,
               'width': 1920 if camera == 'overview' else 1280,
               'height': 1080 if camera == 'overview' else 720,
               'fps': 20, 'color': color}
              for camera, color in zip(CAMERAS, ('blue', 'green', 'white', 'red'))]
    diagnostic = {'files': files, 'graphs': graphs, 'videos': videos}
    output = HERE / ('diagnostic-' + suffix + '.json')
    output.write_text(compact(diagnostic) + '\n')
    if output.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('diagnostic text exceeds worker file limit')
    root = HERE.parents[1]
    rel = str(output.relative_to(root))
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': rel,
                           'sha256': sha(output.read_text())}],
              'generator': {'source': rel, 'sha256': sha(output.read_text())}}
    (HERE / ('diagnostic-' + suffix + '-recipe.json')).write_text(json.dumps(recipe, indent=2) + '\n')
    print(compact({'case': suffix, 'diagnostic_bytes': output.stat().st_size,
                   'diagnostic_sha256': sha(output.read_text())}))


if __name__ == '__main__':
    selected = sys.argv[1:] or ['controlled_2']
    for suffix in selected:
        if suffix not in CASES:
            raise ValueError('Unknown selected crosswalk case: ' + suffix)
        build(suffix, CASES[suffix])
