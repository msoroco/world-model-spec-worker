"""Source-shaped synthetic bus dwell diagnostics; no original authority claim."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from geometry import open_drive

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def lines(values):
    return ''.join(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n'
                   for value in values)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    road = open_drive() + '\n'
    for suffix, first, end in (('probe_01', 120, 280), ('probe_02', 120, 480)):
        case = HERE.name + '__' + suffix
        frames, history, trace, evidence, replay, graphs = [], [], [], [], [], []
        for i in range(600):
            native = 1000 + i
            t = i / 20
            parked = first <= i < end
            x = -12 + i * .1 if i < first else 0.0 if parked else 25 + (i - end) * .1
            speed = 0.0 if parked else 2.0
            velocity = [speed, 0.0, 0.0]
            xyz = [x, -5.25, 1.0]
            frames.append({'video_frame': i, 'native_frame': native, 'carla_frame': native,
                           'time_s': t, 'camera_native_frames': dict.fromkeys(VIEWS, native)})
            history.append({'video_frame': i, 'native_frame': native, 'time_s': t,
                            'subject_id': 1, 'blueprint_id': 'vehicle.mitsubishi.fusorosa',
                            'position_xyz_m': xyz, 'velocity_xyz_mps': velocity,
                            'controller_state': 'parked' if parked else 'approach' if i < first else 'depart',
                            'control': {'throttle': 0 if parked else .25,
                                        'brake': 1 if parked else 0,
                                        'hand_brake': parked}})
            trace.append({'frame': native, 'time_s': t,
                          'position': {'x': x, 'y': -5.25, 'z': 1.0},
                          'position_m': xyz, 'heading_deg': 0,
                          'speed_mps': speed, 'speed_mph': speed / .44704,
                          'velocity_mps': velocity, 'control': {}})
            bbox = [[x + dx, -5.25 + dy, z] for dx in (-4, 4)
                    for dy in (-1, 1) for z in (.5, 3.0)]
            evidence.append({'original_frame': native, 'replay_frame': native,
                             'actor_id': 1, 'recording_time_s': t,
                             'replay_simulation_time_s': t,
                             'ego': {'position_m': xyz, 'heading_deg': 0,
                                     'speed_mps': speed,
                                     'speed_provenance': 'synthetic_native_sample',
                                     'body_vertices_m': bbox},
                             'synthetic_diagnostic': True,
                             'world': {'road_projection': {'road_id': 1,
                                                           'lane_id': -2,
                                                           'section_id': 0,
                                                           's_m': x + 100}}})
            graph = f'graphs/base/{native:08d}.adapter.json'
            replay.append({'frame': native, 'time_s': t, 'simulation_time': t,
                           'synthetic_diagnostic': True, 'adapter_graph': graph})
            graphs.append({'path': 'capture/native/' + graph,
                           'attributes': {'frame': native, 'simulation_time_s': t,
                                          'synthetic_diagnostic': True,
                                          'source': 'C393261 bus dwell software diagnostic'},
                           'nodes': [{'id': 'ego', 'attributes': {
                               'sem_class': 'ego', 'entity_id': 1, 'vertex': xyz,
                               'forward': [1, 0, 0], 'threedbbox': bbox}}],
                           'edges': []})
        context = {'zone_x_m': [-2.0, 20.0], 'parking_lane_id': -2,
                   'endpoint_id': 'native_road_1_parking_-2_terminus',
                   'native_survey': {'terminus_signal': {'name': 'BUS ROUTE TERMINUS',
                                                         'unit': 'none'},
                                     'parking_lane_samples': [{'requested_x_m': x,
                                         'native_xyz_m': [x, -5.25, 0],
                                         'road_id': 1, 'lane_id': -2}
                                         for x in (-12, 0, 10, 20)]},
                   'covered_non_tour_bus_claim': 'vehicle.mitsubishi.fusorosa',
                   'operator_id': 'synthetic-diagnostic-controller',
                   'designation_authority_source': None,
                   'designated_period_s': None, 'designation_verified': False,
                   'actual_loading_activity_verified': False,
                   'physical_sign_pixels_verified': False}
        trace_text = lines(trace)
        files = {'road.xodr': road, 'terminus-context.json': json.dumps(context) + '\n',
                 'terminus-history.jsonl': lines(history),
                 'video_frames.jsonl': lines(frames), 'trace.jsonl': trace_text,
                 'capture/evidence.jsonl': lines(evidence),
                 'capture/native/frames.jsonl': lines(replay),
                 'capture/recorder_info.txt':
                    'Synthetic C393261 software diagnostic; no CARLA recorder\nCreate 1: vehicle.mitsubishi.fusorosa (0)\n',
                 'capture/manifest.json': json.dumps({
                     'extraction_confirmed': True, 'frames': 600,
                     'required_observations': [],
                     'sources': {'trace.jsonl': sha(trace_text), 'road.xodr': sha(road)},
                     'synthetic_diagnostic': True}) + '\n'}
        review_sources = ('road.xodr', 'terminus-context.json',
                          'terminus-history.jsonl', 'video_frames.jsonl',
                          'trace.jsonl', 'capture/manifest.json')
        review = {'assignment_id': HERE.name, 'case_id': case,
                  'review_kind': 'synthetic_diagnostic',
                  'source_sha256': {name: sha(files[name]) for name in review_sources},
                  'official_designation_verified': False,
                  'physical_acceptance_claimed': False}
        for name in VIEWS:
            review['source_sha256'][name + '.mkv'] = None
        files['terminus-review.json'] = json.dumps(review, indent=2) + '\n'
        spec = {'files': files, 'graphs': graphs,
                'videos': [{'path': name + '.mkv', 'frames': 600,
                            'width': 1920 if name == 'overview' else 1280,
                            'height': 1080 if name == 'overview' else 720,
                            'fps': 20, 'color': 'black'} for name in VIEWS]}
        directory = HERE / 'cases' / suffix
        path = directory / 'diagnostic.json'
        write(path, spec)
        relative = str(path.relative_to(REPO))
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json',
                               'source': relative,
                               'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}],
                  'generator': {'source': relative,
                                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}
        write(directory / 'recipe.json', recipe)
        print(suffix, path.stat().st_size)


if __name__ == '__main__':
    main()
