"""Source-hashed synthetic diagnostic recipe for one current v2 primary."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ID = HERE.name
CASE = ID + '__probe_1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def lines(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def main():
    source = HERE / 'current-v2-probe-1-fixture'
    source.mkdir(exist_ok=True)
    native, mapping, trace, evidence, frames, graphs = [], [], [], [], [], []
    for index in range(600):
        frame = 100 + index
        time = index / 20
        phase = ('cross_green', 'cross_yellow', 'cross_red')[(index % 120) // 40]
        front = -4.0 if index < 250 else 1.0
        body = [[-1, front-2, 0], [1, front-2, 0], [-1, front, 0], [1, front, 0]]
        speed = 0 if 15 <= index < 250 else 3
        native.append({'native_frame': frame, 'time_s': time,
                       'signal_actor_id': 17, 'cross_signal_actor_id': 18,
                       'ego_face_observed': 'circular_red_green_left_arrow',
                       'cross_phase_observed': phase, 'controller_cycle_count': index // 120,
                       'actor_class_observed': 'motorcycle', 'detector_request_present': True,
                       'detector_request_serviced': False, 'other_device_prohibition_observed': False,
                       'body_vertices_m': body, 'speed_mps': speed,
                       'speed_provenance': 'synthetic_native_sample',
                       'entered_intersection': index >= 250,
                       'pedestrians_in_crosswalk': False, 'lawful_traffic_conflict': False})
        mapping.append({'video_frame': index, 'native_frame': frame, 'carla_frame': frame, 'time_s': time})
        trace.append({'frame': frame, 'time_s': time,
                      'position': {'x': 0.0, 'y': front-1.0, 'z': 0.5},
                      'heading_deg': 90.0, 'speed_mps': speed,
                      'position_m': [0.0, front-1.0, 0.5],
                      'speed_mph': speed / .44704,
                      'control': {'throttle': 0, 'brake': 0, 'hand_brake': False}})
        evidence.append({'original_frame': frame, 'recording_time_s': time,
                         'replay_frame': frame, 'replay_simulation_time_s': time,
                         'actor_id': 107,
                         'ego': {'body_vertices_m': body, 'position_m': [0, front-1, 0.5],
                                 'heading_deg': 90.0, 'speed_mps': speed,
                                 'speed_provenance': 'synthetic_native_sample'},
                         'world': {'weather': {}, 'road_projection': {'road_id': 1,
                                  'section_id': 0, 'lane_id': -1, 's_m': 50 + index * 0.01}}})
        graph_path = f'capture/native/graphs/base/{frame:08d}.adapter.json'
        frames.append({'frame': frame, 'simulation_time': time, 'time_s': time,
                       'adapter_graph': f'graphs/base/{frame:08d}.adapter.json',
                       'synthetic_diagnostic': True})
        graphs.append({'path': graph_path,
                       'attributes': {'frame': frame, 'simulation_time_s': time},
                       'nodes': [{'id': 'ego', 'attributes': {
                           'vertex': [0.0, front-1.0, 0.5], 'sem_class': 'ego',
                           'forward': [0.0, 1.0, 0.0], 'entity_id': 107,
                           'carla_speed': speed, 'special_class': 'ego'}}],
                       'edges': []})
    lines(source / 'native_samples.jsonl', native)
    lines(source / 'video_frames.jsonl', mapping)
    lines(source / 'trace.jsonl', trace)
    lines(source / 'capture/evidence.jsonl', evidence)
    lines(source / 'capture/native/frames.jsonl', frames)
    (source / 'capture/recorder_info.txt').write_text('Create 107: vehicle.kawasaki.ninja\nSynthetic diagnostic source frames: 600\n')
    original_road = ROOT / 'work/training__C110919__NRS-484B-307-8d__motorcycle_or_moped_operator/current-v2-condition_a-fixture/road.xodr'
    (source / 'road.xodr').write_bytes(original_road.read_bytes())
    write(source / 'road_geometry.json', {
        'signal_actor_id': 17, 'cross_signal_actor_id': 18,
        'governing_face': 'circular_red_green_left_arrow',
        'approach_enters_intersection': True,
        'stop_reference_kind': 'nearest_crosswalk', 'approach_axis': 1,
        'approach_sign': 1, 'stop_reference_coordinate_m': 0,
        'other_device_prohibition_survey': False})
    write(source / 'capture/manifest.json', {
        'extraction_confirmed': True, 'frames': 600, 'synthetic_diagnostic': True,
        'sources': {'road.xodr': sha(source / 'road.xodr'),
                    'trace.jsonl': sha(source / 'trace.jsonl')}})
    spec = HERE / 'current-v2-probe-1-fixture-spec.json'
    write(spec, {'files': {}, 'graphs': graphs,
                 'videos': [{'path': name + '.mkv', 'frames': 600, 'width': width,
                             'height': height, 'fps': 20, 'color': 'black'}
                            for name, width, height in
                            [('overview', 1920, 1080), ('approach', 1280, 720),
                             ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]]})
    recipe = HERE / 'current-v2-probe-1-fixture-recipe.json'
    write(recipe, {'format': 'worker-fixture-recipe',
                   'sources': [{'path': p.relative_to(source).as_posix(),
                                'source': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)}
                               for p in sorted(source.rglob('*')) if p.is_file()],
                   'generator': {'source': spec.relative_to(ROOT).as_posix(),
                                 'sha256': sha(spec)}})
    contract = HERE / 'current-v2-probe-1-measurement-contract.json'
    write(contract, {'format': 'worker-measurement-contract', 'case_id': CASE,
                     'requirements': [{'disposition_index': 0, 'requirement': 'NRS-484B-307-9b',
                                       'source': 'NRS 484B.307(9)(b)',
                                       'output_key': 'cycle_requirement',
                                       'method': 'measure_cycle_requirement',
                                       'value_type': 'object', 'kind': 'measured',
                                       'inputs': ['native_samples.jsonl', 'road_geometry.json']}],
                     'negative': {'remove': ['road_geometry.json'],
                                  'error_contains': 'Missing required source: road_geometry.json'}})
    manifest = json.loads((HERE / 'draft-manifest.json').read_text())
    entry = manifest['cases'][0]
    entry['fixture_recipe'] = recipe.relative_to(ROOT).as_posix()
    entry['measurement_contract'] = contract.name
    entry['measurement_procedure'] = {'entrypoint': 'finalize.py',
                                      'output_schema': 'c111071-saved-finalizer-report-v1'}
    manifest['cases'] = [entry]
    destination = HERE / 'current-v2-probe-1-primary-manifest.json'
    write(destination, manifest)
    proposals = HERE / 'proposals/cases.json'
    plan = json.loads((HERE / 'case-plan.json').read_text())
    write(proposals, {'cases': [next(c for c in plan['cases'] if c['case_id'] == CASE)]})
    print(json.dumps({'manifest': sha(destination), 'recipe': sha(recipe),
                      'spec': sha(spec), 'sources': len(json.loads(recipe.read_text())['sources'])}))


if __name__ == '__main__':
    main()
