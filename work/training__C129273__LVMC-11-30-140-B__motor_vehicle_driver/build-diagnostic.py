"""Build explicit synthetic Native-shaped sources for blind-person public checks."""
import hashlib
import json
from pathlib import Path

from native.geometry import open_drive

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SUFFIXES = ('probe_1', 'probe_2', 'white_wholly', 'white_partial',
            'assisted', 'early_release')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n'
                            for value in values))


def speed_at(index, behavior):
    if behavior == 'no_stop':
        return 10.0
    if index < 120:
        return 10.0
    if behavior == 'early_release' and index >= 220:
        return 10.0
    if behavior == 'stop_clear' and index >= 360:
        return 10.0
    return 0.0


def build(suffix):
    case_id = HERE.name + '__' + suffix
    proposal = json.loads((HERE / 'draft-exact' / suffix / 'primary' /
                           'construction.json').read_text())
    config = json.loads(next(item['content'] for item in proposal['files']
                             if item['path'] == 'config.json'))
    request = config['source_context_request']
    source = HERE / 'diagnostic-source' / suffix
    source.mkdir(parents=True, exist_ok=True)
    write(source / 'acquisition-provenance.json', {
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'native_executed': False})
    write(source / 'blind-person-context.json', {
        'source_kind': 'synthetic_cpu', 'request': request,
        'blind_person_source_context': request,
        'blindness_independently_verified': False,
        'cane_or_assistance_independently_verified': False,
        'legal_verdict_claimed': False})
    write(source / 'road-survey.json', {
        'source_kind': 'synthetic_cpu', 'cell_id': 'C129273',
        'lane_survey': [{'x_m': x, 'road_id': 1, 'lane_id': -1}
                        for x in (-80, -40, 0, 40, 80)],
        'marker_appearance_verified': False})
    (source / 'road.xodr').write_text(open_drive().rstrip() + '\n')
    recorder = source / 'capture' / 'recorder_info.txt'
    recorder.parent.mkdir(parents=True, exist_ok=True)
    recorder.write_text('Create 107: vehicle.synthetic.subject\nCreate 202: walker.synthetic.person\n')
    poses, mapping, image_rows, trace, evidence, native_frames = [], [], [], [], [], []
    x = -80.0
    for index in range(600):
        native = 100 + index
        time = index / 20
        speed = speed_at(index, request['driver_behavior'])
        if index:
            x += speed / 20
        person_y = -4.6 + min(max(index - 100, 0), 260) * .025
        person = [0.0, person_y, 28.1]
        vehicle = [x, -1.75, 27.0]
        poses.append({'video_frame': index, 'native_frame': native,
                      'time_s': time, 'vehicle_id': 107, 'person_id': 202,
                      'assistant_id': 203 if suffix == 'assisted' else None,
                      'vehicle_xyz_m': vehicle, 'person_xyz_m': person,
                      'vehicle_yaw_deg': 0, 'bbox_half_length_m': 2.0,
                      'bbox_half_width_m': 1.0, 'speed_mps': speed,
                      'requested_throttle': .25 if speed else 0.0,
                      'requested_brake': 0.0 if speed else 1.0,
                      'marker_appearance_verified': False,
                      'value': {'vehicle_xyz_m': vehicle, 'person_xyz_m': person,
                                'speed_mps': speed}})
        mapping.append({'native_frame': native, 'carla_frame': native,
                        'video_frame': index, 'time_s': time,
                        'camera_native_frames': {name: native for name in CAMERAS}})
        trace.append({'frame': native, 'time_s': time,
                      'position': {'x': x, 'y': -1.75, 'z': 27.0},
                      'position_m': vehicle, 'heading_deg': 0,
                      'speed_mps': speed, 'speed_mph': speed * 2.2369362921,
                      'velocity_mps': [speed, 0, 0],
                      'control': {'throttle': .25 if speed else 0.0,
                                  'brake': 0.0 if speed else 1.0,
                                  'hand_brake': False},
                      'synthetic_diagnostic': True,
                      'speed_provenance': 'synthetic_native_sample'})
        evidence.append({'original_frame': native, 'replay_frame': native,
                         'actor_id': 107, 'recording_time_s': time,
                         'replay_simulation_time_s': time,
                         'ego': {'position_m': vehicle, 'heading_deg': 0,
                                 'speed_mps': speed,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'body_vertices_m': [[x + dx, -1.75 + dy, z]
                                                     for dx in (-2, 2)
                                                     for dy in (-1, 1)
                                                     for z in (26.5, 28.5)]},
                         'world': {'weather': {'cloudiness': 0,
                                              'precipitation': 0, 'wetness': 0,
                                              'fog_density': 0},
                                   'road_projection': {'road_id': 1,
                                                       'section_id': 0,
                                                       'lane_id': -1,
                                                       's_m': x + 120}}})
        native_frames.append({'frame': native, 'time_s': time,
                              'simulation_time': time,
                              'synthetic_diagnostic': True,
                              'adapter_graph': f'graphs/base/{native:08d}.adapter.json'})
        for name in CAMERAS:
            image_rows.append({'frame': index, 'camera': name,
                               'native_frame': native,
                               'rgb_sha256': hashlib.sha256(
                                   f'{case_id}:{index}:{name}'.encode()).hexdigest()})
    for name, values in {'vehicle-person-poses.jsonl': poses,
                         'video_frames.jsonl': mapping,
                         'camera-frames.jsonl': image_rows,
                         'trace.jsonl': trace,
                         'capture/evidence.jsonl': evidence,
                         'capture/native/frames.jsonl': native_frames}.items():
        write_rows(source / name, values)
    write(source / 'capture/manifest.json', {
        'extraction_confirmed': True, 'frames': 600,
        'required_observations': [], 'synthetic_diagnostic': True,
        'sources': {'road.xodr': sha(source / 'road.xodr'),
                    'trace.jsonl': sha(source / 'trace.jsonl')}})
    generator = {'files': {}, 'graphs': [
        {'path': f'capture/native/graphs/base/{100 + i:08d}.adapter.json',
         'attributes': {'frame': 100 + i}, 'nodes': [], 'edges': []}
        for i in range(600)],
        'videos': [{'path': name + '.mkv', 'frames': 600,
                    'width': width, 'height': height, 'fps': 20, 'color': 'blue'}
                   for name, width, height in (('overview', 1920, 1080),
                                               ('approach', 1280, 720),
                                               ('reference_corner', 1280, 720),
                                               ('driver_reference', 1280, 720))]}
    generator_path = HERE / ('diagnostic-generator-' + suffix + '.json')
    write(generator_path, generator)
    source_names = ('acquisition-provenance.json', 'capture/evidence.jsonl',
                    'capture/manifest.json', 'capture/native/frames.jsonl',
                    'capture/recorder_info.txt', 'trace.jsonl',
                    'video_frames.jsonl', 'road.xodr', 'road-survey.json',
                    'blind-person-context.json', 'vehicle-person-poses.jsonl',
                    'camera-frames.jsonl')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': name, 'source': str((source / name).relative_to(REPO)),
                           'sha256': sha(source / name)} for name in source_names],
              'generator': {'source': str(generator_path.relative_to(REPO)),
                            'sha256': sha(generator_path)}}
    recipe_path = HERE / ('diagnostic-recipe-' + suffix + '.json')
    write(recipe_path, recipe)
    return {'case_id': case_id, 'recipe': str(recipe_path.relative_to(REPO))}


if __name__ == '__main__':
    print(json.dumps([build(suffix) for suffix in SUFFIXES]))
