"""Build explicit text-only trail fixture recipes for current public CPU checks."""
import hashlib
import json
from pathlib import Path

from native.geometry import open_drive

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SUFFIXES = ('outside', 'all_present', 'no_designation', 'no_dedication',
            'no_posting', 'emergency', 'maintenance')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value, separators=(',', ':'), allow_nan=False)
                            + '\n' for value in values))


def build(suffix):
    if suffix not in SUFFIXES:
        raise ValueError('Unknown exact trail case')
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
    write(source / 'trail-inventory.json', {
        'source_kind': 'synthetic_cpu', 'cell_id': 'C143691',
        'trail_right_of_way_m': {'min_x': -50.0, 'max_x': 70.0,
                                  'min_y': -2.0, 'max_y': 2.0},
        'barrier_clear_gap_m': 3.5, 'vehicle_width_m': 2.0,
        'sign_marker_native_readback': request['appropriate_posting'],
        'sign_wording_and_authority_verified': False,
        'subject_blueprint_id': 'vehicle.synthetic.' + suffix,
        'source_context_request': request,
        'official_plan_document_original': False,
        'city_dedication_document_original': False})
    write(source / 'trail-authority-context.json', {
        'source_kind': 'synthetic_cpu', 'request': request,
        'official_record_reviewed': False, 'official_plan_source': None,
        'city_record_reviewed': False, 'city_dedication_source': None,
        'sign_wording_and_authority_reviewed': False,
        'emergency_identity_reviewed': False,
        'this_right_of_way_use_reviewed': False, 'maintenance_source': None,
        'device_design_reviewed': False, 'impaired_person_use_reviewed': False,
        'original_documents_attached': False, 'legal_verdict_claimed': False})
    (source / 'road.xodr').write_text(open_drive() + '\n')
    recorder = source / 'capture' / 'recorder_info.txt'
    recorder.parent.mkdir(parents=True, exist_ok=True)
    recorder.write_text('Create 107: vehicle.synthetic.' + suffix + '\n')
    poses, mapping, image_rows, trace, evidence, native_frames = [], [], [], [], [], []
    inside = config['route_case'] == 'within'
    y = 0.0 if inside else 6.0
    for index in range(600):
        native = 100 + index
        time = index / 20
        x = -50.0 + 4.0 * time
        body = [[x - 2, y - 1], [x + 2, y - 1],
                [x + 2, y + 1], [x - 2, y + 1]]
        poses.append({'video_frame': index, 'native_frame': native,
                      'time_s': time, 'vehicle_id': 107,
                      'vehicle_blueprint_id': 'vehicle.synthetic.' + suffix,
                      'vehicle_xyz_m': [x, y, 1], 'vehicle_yaw_deg': 0,
                      'bbox_half_length_m': 2, 'bbox_half_width_m': 1,
                      'observed_speed_mps': 4,
                      'camera_native_frames': {name: native for name in CAMERAS},
                      'barrier_physical_clearance_verified': False})
        mapping.append({'native_frame': native, 'carla_frame': native,
                        'video_frame': index, 'time_s': time,
                        'camera_native_frames': {name: native for name in CAMERAS}})
        trace.append({'frame': native, 'time_s': time,
                      'position': {'x': x, 'y': y, 'z': 1},
                      'position_m': [x, y, 1], 'heading_deg': 0,
                      'speed_mps': 4, 'speed_mph': 8.947745168,
                      'velocity_mps': [4, 0, 0],
                      'control': {'throttle': 0, 'brake': 0, 'hand_brake': False},
                      'synthetic_diagnostic': True,
                      'speed_provenance': 'synthetic_native_sample'})
        evidence.append({'original_frame': native, 'replay_frame': native,
                         'actor_id': 107, 'recording_time_s': time,
                         'replay_simulation_time_s': time,
                         'ego': {'position_m': [x, y, 1], 'heading_deg': 0,
                                 'speed_mps': 4, 'speed_provenance': 'synthetic_native_sample',
                                 'body_vertices_m': [[u, v, z] for u, v in body
                                                     for z in (0, 1.5)]},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                              'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 1, 'section_id': 0,
                                                       'lane_id': -2 if inside else -1,
                                                       's_m': x + 80}}})
        native_frames.append({'frame': native, 'time_s': time,
                              'simulation_time': time, 'synthetic_diagnostic': True,
                              'adapter_graph': f'graphs/base/{native:08d}.adapter.json'})
        for name in CAMERAS:
            image_rows.append({'frame': index, 'camera': name,
                               'native_frame': native,
                               'rgb_sha256': hashlib.sha256(
                                   f'{case_id}:{index}:{name}'.encode()).hexdigest()})
    for name, values in {'vehicle-poses.jsonl': poses, 'video_frames.jsonl': mapping,
                         'camera-frames.jsonl': image_rows, 'trace.jsonl': trace,
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
                    'capture/recorder_info.txt', 'trace.jsonl', 'video_frames.jsonl',
                    'road.xodr', 'trail-inventory.json', 'trail-authority-context.json',
                    'vehicle-poses.jsonl', 'camera-frames.jsonl')
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
