"""Build source-shaped synthetic following and passing software fixtures."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / 'native'))
from geometry import open_drive

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def lines(values):
    return ''.join(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n'
                   for value in values)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False).rstrip() + '\n')


def rectangle(x, y, half_length, half_width):
    return [[x - half_length, y - half_width],
            [x - half_length, y + half_width],
            [x + half_length, y - half_width],
            [x + half_length, y + half_width]]


def main():
    road = open_drive() + '\n'
    for index, rider_speed in ((1, 3.0), (2, 5.0)):
        suffix = f'controlled_{index}'
        case = ROOT.name + '__' + suffix
        frames, poses, trace, evidence, replay, graphs = [], [], [], [], [], []
        for i in range(600):
            native, time = 1000 + i, i / 20
            rider_x = -80 + rider_speed * time
            other_x = -50 + 3 * time
            rider_y, other_y = -4.7, -1.5
            rider_body = rectangle(rider_x, rider_y, 1.2, .4)
            other_body = rectangle(other_x, other_y, 2.2, .9)
            xyz = [rider_x, rider_y, 1.0]
            frames.append({'video_frame': i, 'native_frame': native,
                           'carla_frame': native, 'time_s': time,
                           'camera_native_frames': dict.fromkeys(VIEWS, native)})
            poses.append({'video_frame': i, 'native_frame': native, 'time_s': time,
                          'rider_actor_id': 1, 'motor_actor_id': 2,
                          'rider_blueprint_id': 'vehicle.harley-davidson.low_rider',
                          'motor_blueprint_id': 'vehicle.tesla.model3',
                          'rider_xy_m': [rider_x, rider_y],
                          'motor_xy_m': [other_x, other_y],
                          'rider_body_xy_m': rider_body,
                          'motor_body_xy_m': other_body,
                          'rider_speed_mps': rider_speed,
                          'motor_speed_mps': 3.0})
            trace.append({'frame': native, 'time_s': time,
                          'position': {'x': rider_x, 'y': rider_y, 'z': 1.0},
                          'position_m': xyz, 'heading_deg': 0,
                          'speed_mps': rider_speed,
                          'speed_mph': rider_speed / .44704,
                          'velocity_mps': [rider_speed, 0, 0],
                          'control': {}})
            bbox = [[rider_x + dx, rider_y + dy, z]
                    for dx in (-1.2, 1.2) for dy in (-.4, .4)
                    for z in (.5, 1.5)]
            evidence.append({'original_frame': native, 'replay_frame': native,
                             'actor_id': 1, 'recording_time_s': time,
                             'replay_simulation_time_s': time,
                             'ego': {'position_m': xyz, 'heading_deg': 0,
                                     'speed_mps': rider_speed,
                                     'speed_provenance': 'synthetic_native_sample',
                                     'body_vertices_m': bbox},
                             'synthetic_diagnostic': True,
                             'world': {'road_projection': {'road_id': 1,
                                                           'lane_id': -1,
                                                           'section_id': 0,
                                                           's_m': rider_x + 100}}})
            graph = f'graphs/base/{native:08d}.adapter.json'
            replay.append({'frame': native, 'time_s': time,
                           'simulation_time': time,
                           'synthetic_diagnostic': True,
                           'adapter_graph': graph})
            graphs.append({'path': 'capture/native/' + graph,
                           'attributes': {'frame': native,
                                          'simulation_time_s': time,
                                          'synthetic_diagnostic': True,
                                          'source': 'C146108 same-lane software diagnostic'},
                           'nodes': [{'id': 'ego', 'attributes': {
                               'sem_class': 'ego', 'entity_id': 1,
                               'vertex': xyz, 'forward': [1, 0, 0],
                               'threedbbox': bbox}}], 'edges': []})
        pose_text = lines(poses)
        trace_text = lines(trace)
        context = {'rider_class': 'motorcycle', 'passed_class': 'motor_vehicle',
                   'motorcycle_class': {'observed_blueprint_id': 'vehicle.harley-davidson.low_rider',
                                        'classification_status': 'synthetic_diagnostic'},
                   'subsection_3_exception': {'pair_eligible': False,
                                              'reason': 'Other vehicle is a motor vehicle, not a second motorcycle or moped',
                                              'driver_consent': 'unverified'},
                   'observed_action': 'source_review_pending',
                   'classification_source': {'path': 'participant-poses.jsonl',
                                             'sha256': sha(pose_text)},
                   'rider_dimensions_m': [2.4, .8],
                   'motor_dimensions_m': [4.4, 1.8],
                   'native_classification_review_pending': True,
                   'driver_consent_review_pending': True,
                   'subsection_3_text_review_pending': False}
        files = {'road.xodr': road,
                 'pass-context.json': json.dumps(context) + '\n',
                 'participant-poses.jsonl': pose_text,
                 'video_frames.jsonl': lines(frames),
                 'trace.jsonl': trace_text,
                 'capture/evidence.jsonl': lines(evidence),
                 'capture/native/frames.jsonl': lines(replay),
                 'capture/recorder_info.txt':
                     'Synthetic C146108 software diagnostic; no CARLA recorder\nCreate 1: vehicle.harley-davidson.low_rider (0)\nCreate 2: vehicle.tesla.model3 (0)\n',
                 'capture/manifest.json': json.dumps({
                     'extraction_confirmed': True, 'frames': 600,
                     'required_observations': [],
                     'sources': {'trace.jsonl': sha(trace_text),
                                 'road.xodr': sha(road)},
                     'synthetic_diagnostic': True}) + '\n'}
        review_sources = ('road.xodr', 'pass-context.json',
                          'participant-poses.jsonl', 'video_frames.jsonl',
                          'trace.jsonl', 'capture/manifest.json')
        review = {'assignment_id': ROOT.name, 'case_id': case,
                  'review_kind': 'synthetic_diagnostic',
                  'source_sha256': {name: sha(files[name]) for name in review_sources},
                  'physical_acceptance_claimed': False,
                  'driver_consent_verified': False}
        for view in VIEWS:
            review['source_sha256'][view + '.mkv'] = None
        files['pass-review.json'] = json.dumps(review, indent=2) + '\n'
        spec = {'files': files, 'graphs': graphs,
                'videos': [{'path': view + '.mkv', 'frames': 600,
                            'width': 1920 if view == 'overview' else 1280,
                            'height': 1080 if view == 'overview' else 720,
                            'fps': 20, 'color': 'black'} for view in VIEWS]}
        directory = ROOT / 'cases' / suffix
        diagnostic = directory / 'diagnostic.json'
        write(diagnostic, spec)
        relative = str(diagnostic.relative_to(REPO))
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json',
                               'source': relative,
                               'sha256': hashlib.sha256(diagnostic.read_bytes()).hexdigest()}],
                  'generator': {'source': relative,
                                'sha256': hashlib.sha256(diagnostic.read_bytes()).hexdigest()}}
        write(directory / 'recipe.json', recipe)
        print(suffix, diagnostic.stat().st_size)


if __name__ == '__main__':
    main()
