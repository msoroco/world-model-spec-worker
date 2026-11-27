"""Build source-shaped synthetic CPU diagnostics for the exact curb cell."""
import hashlib
import json
from pathlib import Path

from road_geometry import road_xml
from source_review import SOURCES

HERE = Path(__file__).resolve().parent
AID = HERE.name
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SPEEDS = (75.0, 79.5, 85.0)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def wire(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n'


def lines(values):
    return ''.join(wire(value) for value in values)


def make(index):
    suffix = f'probe_0{index}'
    case = AID + '__' + suffix
    directory = HERE / 'cases' / suffix
    road = road_xml() + '\n'
    (directory / 'road.xodr').write_text(road)
    context = {name: 'Synthetic C229398 CPU diagnostic ' + name +
               '; no original road, phase, actor, or pixel assertion.\n'
               for name in SOURCES}
    refs = {name: {'path': 'source_context/' + name + '.txt',
                   'sha256': sha(context[name].encode())} for name in SOURCES}
    review = {'assignment_id': AID, 'case_id': case,
              'review_kind': 'synthetic_diagnostic', 'sources': refs,
              'road_xodr_sha256': sha(road.encode()),
              'physical_acceptance_claimed': False, 'legal_verdict': None}
    fmap, native, core, evidence, graph_index, graphs, visibility = [], [], [], [], [], [], []
    speed = SPEEDS[index - 1]
    for i in range(600):
        frame = 1000 + i
        time_s = i / 20
        phase = 'approach_driving' if i < 400 else 'curb_parking' if i < 520 else 'parked'
        mph = speed if i < 400 else 5.0 if i < 520 else 0.0
        mps = mph / 2.2369362920544
        lane = -1 if i < 520 else -2
        x = -300 + min(i, 400) * speed / 2.2369362920544 / 20
        y = -1.75 if i < 400 else -1.75 - 3.25 * min(i - 400, 120) / 120
        sample = {'actor_id': 1, 'blueprint': 'vehicle.tesla.model3',
                  'road_id': 229398, 'lane_id': lane,
                  'position_xyz_m': [x, y, 1.0],
                  'velocity_xyz_mps': [mps, 0.0, 0.0],
                  'observed_speed_mph': mph}
        fmap.append({'video_frame': i, 'native_frame': frame, 'carla_frame': frame,
                     'time_s': time_s,
                     'camera_native_frames': dict.fromkeys(CAMERAS, frame)})
        native.append({'frame': i, 'native_frame': frame, 't_s': time_s,
                       'source_kind': 'synthetic_native_sample', 'phase': phase,
                       'requested_speed_mph': speed, 'sample': sample,
                       'parking_target_xyz_m': [600.0, -5.0, 0.0]})
        core.append({'frame': frame, 'time_s': time_s,
                     'position': {'x': x, 'y': y, 'z': 1.0},
                     'position_m': [x, y, 1.0], 'heading_deg': 0,
                     'speed_mps': mps, 'speed_mph': mph,
                     'velocity_mps': [mps, 0.0, 0.0],
                     'control': {'throttle': 0.5 if i < 400 else 0,
                                 'brake': 0 if i < 400 else 0.8}})
        vertices = [[x + dx, y + dy, z] for dx in (-2, 2)
                    for dy in (-0.8, 0.8) for z in (0.5, 2.0)]
        evidence.append({'original_frame': frame, 'replay_frame': frame,
                         'actor_id': 1, 'recording_time_s': time_s,
                         'replay_simulation_time_s': time_s,
                         'ego': {'position_m': [x, y, 1.0], 'heading_deg': 0,
                                 'speed_mps': mps, 'body_vertices_m': vertices,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'synthetic_diagnostic': True},
                         'participants': {},
                         'world': {'road_projection': {'road_id': 229398,
                                                       'lane_id': lane,
                                                       'section_id': 0,
                                                       's_m': x + 900}}})
        graph_path = f'graphs/base/{frame:08d}.adapter.json'
        graph_index.append({'frame': frame, 'simulation_time': time_s,
                            'base': graph_path, 'adapter_graph': graph_path,
                            'nodes': 1, 'edges': 0})
        graphs.append({'path': 'capture/native/' + graph_path,
                       'attributes': {'frame': frame, 'simulation_time_s': time_s,
                                      'source': 'synthetic C229398 speed fixture',
                                      'synthetic_diagnostic': True},
                       'nodes': [{'id': 'ego', 'attributes': {'entity_id': 1,
                           'sem_class': 'ego', 'vertex': [x, y, 1.0],
                           'forward': [1, 0, 0], 'threedbbox': vertices}}],
                       'edges': []})
        visibility.append({'frame': i, 'visible_views': list(CAMERAS)})
    core_text = lines(core)
    files = {'approach-review.json': wire(review),
             'visibility-review.json': wire({'case_id': case,
                'review_kind': 'synthetic_diagnostic', 'frames': visibility}),
             'native-speed.jsonl': lines(native), 'video_frames.jsonl': lines(fmap),
             'trace.jsonl': core_text, 'capture/evidence.jsonl': lines(evidence),
             'capture/native/frames.jsonl': lines(graph_index),
             'capture/manifest.json': wire({'synthetic_diagnostic': True,
                 'extraction_confirmed': True, 'frames': 600,
                 'sources': {'trace.jsonl': sha(core_text.encode()),
                             'road.xodr': sha(road.encode())}}),
             'capture/recorder_info.txt':
                 'Synthetic C229398 CPU diagnostic; no CARLA recorder\nCreate 1: vehicle.tesla.model3 (0)\n'}
    files.update({'source_context/' + name + '.txt': value
                  for name, value in context.items()})
    spec = {'files': files, 'graphs': graphs,
            'videos': [{'path': name + '.mkv', 'frames': 600,
                        'width': 1920 if name == 'overview' else 1280,
                        'height': 1080 if name == 'overview' else 720,
                        'fps': 20, 'color': color}
                       for name, color in zip(CAMERAS,
                                              ('blue', 'green', 'white', 'red'))]}
    spec_path = directory / 'fixture-spec.json'
    spec_path.write_text(wire(spec))
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'road.xodr',
                           'source': 'work/' + AID + '/cases/' + suffix + '/road.xodr',
                           'sha256': sha(road.encode())}],
              'generator': {'source': 'work/' + AID + '/cases/' + suffix + '/fixture-spec.json',
                            'sha256': sha(spec_path.read_bytes())}}
    (directory / 'fixture-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
    return {'case_id': case, 'fixture_spec_bytes': spec_path.stat().st_size}


if __name__ == '__main__':
    print(json.dumps([make(i) for i in range(1, 4)]))
