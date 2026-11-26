"""Build textual, source-shaped software fixtures for both bicycle cases."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from geometry import SIGN_NAME, open_drive

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def lines(values):
    return ''.join(encoded(value) + '\n' for value in values)


def digest_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


def geometry(x, y):
    return [[x+dx, y+dy, z] for dx in (-.35, .35) for dy in (-.2, .2)
            for z in (0, 1.2)]


def build(suffix, y):
    case_id = HERE.name + '__' + suffix
    frames, poses, trace, evidence, native_frames, graphs = [], [], [], [], [], []
    for index in range(600):
        frame = 100 + index
        time_s = index / 20
        x = -50 + 2.3*time_s
        body = geometry(x, y)
        frames.append({'video_frame': index, 'carla_frame': frame,
                       'native_frame': frame, 'time_s': time_s,
                       'camera_native_frames': {view: frame for view in VIEWS}})
        poses.append({'video_frame': index, 'native_frame': frame, 'time_s': time_s,
                      'native_elapsed_seconds': time_s, 'rider_xy_m': [x, y],
                      'rider_z_m': 1, 'velocity_xy_mps': [2.3, 0],
                      'rider_actor_id': 1, 'rider_blueprint_id': 'vehicle.bh.crossbike',
                      'source_kind': 'synthetic_native_sample'})
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': {'x': x, 'y': y, 'z': 1},
                      'position_m': [x, y, 1], 'heading_deg': 0,
                      'speed_mps': 2.3, 'speed_mph': 2.3/.44704,
                      'velocity_mps': [2.3, 0, 0], 'control': {}})
        evidence.append({'original_frame': frame, 'replay_frame': frame,
                         'actor_id': 1, 'recording_time_s': time_s,
                         'replay_simulation_time_s': time_s,
                         'ego': {'position_m': [x, y, 1], 'heading_deg': 0,
                                 'speed_mps': 2.3, 'speed_provenance': 'synthetic_native_sample',
                                 'body_vertices_m': body},
                         'synthetic_diagnostic': True,
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0}}})
        graph_path = f'capture/native/graphs/base/{frame:08d}.adapter.json'
        native_frames.append({'frame': frame, 'time_s': time_s,
                              'simulation_time': time_s, 'synthetic_diagnostic': True,
                              'adapter_graph': f'graphs/base/{frame:08d}.adapter.json'})
        graphs.append({'path': graph_path,
                       'attributes': {'frame': frame, 'simulation_time_s': time_s,
                                      'synthetic_diagnostic': True,
                                      'source': 'C230207 bicycle signed-roadway software fixture'},
                       'nodes': [{'id': 'ego', 'attributes': {'sem_class': 'ego',
                                   'entity_id': 1, 'vertex': [x, y, 1],
                                   'forward': [1, 0, 0], 'threedbbox': body}}],
                       'edges': []})
    context = {'case_id': case_id, 'target_surface': 'shoulder' if suffix == 'probe_01' else 'roadway',
               'rider_class': 'human_propelled_bicycle', 'blueprint_id': 'vehicle.bh.crossbike',
               'wheel_characteristics_reviewed': False,
               'sign_id': '100', 'sign_text': SIGN_NAME, 'sign_x_m': -45,
               'sign_orientation': 'positive_s',
               'native_sign_survey': {'id': '100', 'name': SIGN_NAME, 'orientation': '+'},
               'native_roadway_survey': [{'requested_x_m': x, 'road_id': 1, 'lane_id': -1}
                                         for x in (-40, 0, 40)],
               'native_shoulder_survey': [{'requested_x_m': x, 'road_id': 1, 'lane_id': -2}
                                          for x in (-40, 0, 40)],
               'roadway_xy_m': [[-60, -3.5], [60, -3.5], [60, 0], [-60, 0]],
               'city_traffic_engineer_designation_verified': False,
               'physical_sign_pixels_verified': False,
               'fixture_only': True}
    files = {'video_frames.jsonl': lines(frames),
             'bicycle-poses.jsonl': lines(poses),
             'restriction-context.json': encoded(context) + '\n',
             'trace.jsonl': lines(trace), 'road.xodr': open_drive() + '\n',
             'capture/evidence.jsonl': lines(evidence),
             'capture/native/frames.jsonl': lines(native_frames),
             'capture/recorder_info.txt': 'C230207 synthetic software diagnostic only\n'}
    capture_manifest = {'extraction_confirmed': True, 'frames': 600,
                        'required_observations': [],
                        'sources': {name: digest_text(files[name]) for name in ('trace.jsonl', 'road.xodr')},
                        'synthetic_diagnostic': True}
    files['capture/manifest.json'] = encoded(capture_manifest) + '\n'
    doc = {'files': files, 'graphs': graphs,
           'videos': [{'path': view + '.mkv', 'frames': 600,
                       'width': 1920 if view == 'overview' else 1280,
                       'height': 1080 if view == 'overview' else 720,
                       'fps': 20, 'color': 'black'} for view in VIEWS]}
    folder = HERE / 'cases' / suffix
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / 'diagnostic.json'
    source.write_text(encoded(doc) + '\n')
    relative = str(source.relative_to(ROOT))
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': relative,
                           'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}],
              'generator': {'source': relative, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}}
    (folder / 'recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
    return {'case_id': case_id, 'diagnostic_bytes': source.stat().st_size,
            'diagnostic_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps([build('probe_01', -4.75), build('probe_02', -1.75)], indent=2))
