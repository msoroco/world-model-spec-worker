"""Make source-inventoried synthetic Native shapes for sidewalk public checks."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def lines(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, separators=(',', ':'),
                                       allow_nan=False) + '\n' for row in rows))


def build(n):
    suffix = f'probe_{n}'
    case_id = HERE.name + '__' + suffix
    source = HERE / 'diagnostic-source' / suffix
    source.mkdir(parents=True, exist_ok=True)
    write(source / 'acquisition-provenance.json', {
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'native_executed': False})
    write(source / 'map-packet.json', {
        'map_acquisition': 'synthetic_native_shape',
        'sidewalk_polygon_m': [[0, -7], [100, -7], [100, -3.5], [0, -3.5]],
        'highway_boundary_source': None, 'property_boundary_source': None,
        'intended_pedestrian_use_source': None,
        'legal_sidewalk_status': None,
        'sidewalk_map_context': {'source': 'synthetic map shape',
                                 'legal_status_independently_verified': False}})
    write(source / 'authority-context.json', {
        'source_kind': 'synthetic_cpu', 'traffic_conflict_requested': False,
        'other_law_authority': None, 'officer_direction': None,
        'official_device_direction': None,
        'exception_independently_verified': False,
        'exception_authority_context': {
            'source': 'synthetic request shape', 'independently_verified': False}})
    (source / 'native-road.xodr').write_text(
        (HERE / 'native' / 'draft_road.xodr').read_text().rstrip() + '\n')
    (source / 'road.xodr').write_text((source / 'native-road.xodr').read_text())
    (source / 'capture' / 'recorder_info.txt').parent.mkdir(parents=True, exist_ok=True)
    (source / 'capture' / 'recorder_info.txt').write_text(
        'Create 107: vehicle.synthetic.sidewalk_subject\n')
    body_y = -5.0 if n == 2 else -1.75
    trace, frames, images, capture_trace, evidence, native_frames = [], [], [], [], [], []
    x = 20.0
    for i in range(600):
        native = 100 + i
        time = i / 20
        speed = 0.0 if 160 <= i < 500 else 4.0
        if i:
            x += speed / 20
        body = [[x - 1, body_y - .5], [x + 1, body_y - .5],
                [x + 1, body_y + .5], [x - 1, body_y + .5]]
        trace.append({'frame': i, 'native_frame': native, 'time_s': time,
                      'actor_id': 107, 'blueprint_id': 'vehicle.synthetic',
                      'actor_pose_source': 'synthetic_post_tick_shape',
                      'velocity_source': 'synthetic_post_tick_shape',
                      'speed_mps': speed, 'vehicle_footprint_m': body,
                      'sidewalk_overlap_area_m2': 2.0 if n == 2 else 0.0,
                      'value': {'vehicle_body_pose': body,
                                'vehicle_speed': speed,
                                'sidewalk_overlap': 2.0 if n == 2 else 0.0},
                      'requested_sidewalk_occupancy': n == 2})
        frames.append({'native_frame': native, 'carla_frame': native,
                       'video_frame': i, 'time_s': time,
                       'camera_native_frames': {name: native for name in CAMERAS}})
        capture_trace.append({'frame': native, 'time_s': time,
            'position': {'x': x, 'y': body_y, 'z': 0},
            'position_m': [x, body_y, 0], 'heading_deg': 0,
            'speed_mps': speed, 'speed_mph': speed * 2.2369362921,
            'velocity_mps': [speed, 0, 0],
            'control': {'throttle': .25 if speed else 0,
                        'brake': 0 if speed else 1,
                        'hand_brake': False},
            'synthetic_diagnostic': True,
            'speed_provenance': 'synthetic_native_sample'})
        evidence.append({'original_frame': native, 'replay_frame': native,
            'actor_id': 107, 'recording_time_s': time,
            'replay_simulation_time_s': time,
            'ego': {'position_m': [x, body_y, 0], 'heading_deg': 0,
                    'speed_mps': speed,
                    'speed_provenance': 'synthetic_native_sample',
                    'body_vertices_m': [[px, py, z] for px, py in body
                                        for z in (0, 1.5)]},
            'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                  'wetness': 0, 'fog_density': 0},
                      'road_projection': {'road_id': 1, 'section_id': 0,
                                          'lane_id': -2 if n == 2 else -1,
                                          's_m': x}}})
        native_frames.append({'frame': native, 'time_s': time,
            'simulation_time': time, 'synthetic_diagnostic': True,
            'adapter_graph': f'graphs/base/{native:08d}.adapter.json'})
        images.extend({'frame': i, 'camera': name, 'native_frame': native,
                       'rgb_sha256': hashlib.sha256(
                           f'{case_id}:{i}:{name}'.encode()).hexdigest()}
                      for name in CAMERAS)
    for name, values in {'vehicle-trace.jsonl': trace,
                         'video_frames.jsonl': frames,
                         'camera-frames.jsonl': images,
                         'trace.jsonl': capture_trace,
                         'capture/evidence.jsonl': evidence,
                         'capture/native/frames.jsonl': native_frames}.items():
        lines(source / name, values)
    write(source / 'capture/manifest.json', {
        'extraction_confirmed': True, 'frames': 600,
        'required_observations': [], 'synthetic_diagnostic': True,
        'sources': {'road.xodr': sha(source / 'road.xodr'),
                    'trace.jsonl': sha(source / 'trace.jsonl')}})
    generator = {'files': {}, 'graphs': [
        {'path': f'capture/native/graphs/base/{100+i:08d}.adapter.json',
         'attributes': {'frame': 100+i}, 'nodes': [], 'edges': []}
        for i in range(600)],
        'videos': [{'path': name + '.mkv', 'frames': 600,
                    'width': width, 'height': height, 'fps': 20,
                    'color': 'blue'} for name, width, height in (
                        ('overview', 1920, 1080), ('approach', 1280, 720),
                        ('reference_corner', 1280, 720),
                        ('driver_reference', 1280, 720))]}
    generated = HERE / f'diagnostic-generator-{suffix}.json'
    write(generated, generator)
    source_names = ('acquisition-provenance.json', 'capture/evidence.jsonl',
        'capture/manifest.json', 'capture/native/frames.jsonl',
        'capture/recorder_info.txt', 'trace.jsonl', 'video_frames.jsonl',
        'road.xodr', 'native-road.xodr', 'map-packet.json', 'authority-context.json',
        'vehicle-trace.jsonl', 'camera-frames.jsonl')
    recipe = {'format': 'worker-fixture-recipe',
        'sources': [{'path': name, 'source': str((source/name).relative_to(REPO)),
                     'sha256': sha(source/name)} for name in source_names],
        'generator': {'source': str(generated.relative_to(REPO)),
                      'sha256': sha(generated)}}
    recipe_path = HERE / f'diagnostic-recipe-{suffix}.json'
    write(recipe_path, recipe)
    return {'case_id': case_id, 'recipe': str(recipe_path.relative_to(REPO))}


if __name__ == '__main__':
    print(json.dumps([build(n) for n in (1, 2)]))
