"""Generate textual, source-hashed route diagnostics; no CARLA observation."""
import hashlib
import json
from pathlib import Path

from geometry import open_drive
from prove_route_measure import source

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
VARIANTS = (
    ('witness_1', True, True), ('witness_2', True, False),
    ('exception_1_1', True, False), ('exception_1_2', False, False))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(folder, name, content):
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip('\n') + '\n')


def rows(values):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n'
                   for row in values)


def build(suffix, possible, taken):
    folder = HERE / 'selected-source' / suffix
    folder.mkdir(parents=True, exist_ok=True)
    trace_bytes, _, road_bytes, frame_bytes = source(possible, taken)
    road = road_bytes.decode()
    road_hash = hashlib.sha256((road.rstrip('\n') + '\n').encode()).hexdigest()
    context = {'assignment_id': ASSIGNMENT, 'case_id': ASSIGNMENT + '__' + suffix,
        'source_kind': 'synthetic_fixture', 'road_xodr_sha256': road_hash,
        'route_graph': {'start_road_id': 1, 'main_road_id': 2,
            'alternate_road_id': 3 if possible else None, 'destination_road_id': 4},
        'controlled_access_designation_source': None,
        'controlled_access_designation_independently_verified': False,
        'alternate_route_usability_physically_verified': False,
        'planned_take_alternate': taken, 'planned_alternate_possible': possible,
        'legal_impediment_determined': False, 'legal_verdict': None}
    route_rows = [json.loads(line) for line in trace_bytes.splitlines()]
    route_core, evidence, native_frames, graphs = [], [], [], []
    for row in route_rows:
        index, frame, time = row['video_frame'], row['native_frame'], row['time_s']
        x, y = row['ego']['xy_m']
        route_core.append({'frame': frame, 'time_s': time,
            'position': {'x': x, 'y': y, 'z': 1.0}, 'position_m': [x, y, 1.0],
            'heading_deg': 0.0, 'speed_mps': 4, 'speed_mph': 4 / .44704,
            'control': {'throttle': 0, 'brake': 0, 'hand_brake': False},
            'synthetic_diagnostic': True, 'velocity_mps': [4, 0, 0],
            'speed_provenance': 'synthetic_native_sample'})
        body = [[x + dx, y + dy, z] for dx, dy in ((-2, -1), (2, -1),
                (2, 1), (-2, 1)) for z in (0, 1.5)]
        evidence.append({'original_frame': frame, 'replay_frame': frame,
            'actor_id': 107, 'recording_time_s': time,
            'replay_simulation_time_s': time,
            'ego': {'position_m': [x, y, 1.0], 'heading_deg': 0,
                    'speed_mps': 4, 'speed_provenance': 'synthetic_native_sample',
                    'body_vertices_m': body},
            'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                 'wetness': 0, 'fog_density': 0},
                      'road_projection': {'road_id': row['ego']['road_id'],
                        'section_id': 0, 'lane_id': -1, 's_m': max(0, x + 100)}}})
        graph_name = f'{frame:08d}.adapter.json'
        native_frames.append({'frame': frame, 'time_s': time,
            'simulation_time': time, 'synthetic_diagnostic': True,
            'adapter_graph': 'graphs/base/' + graph_name})
        graphs.append({'path': 'capture/native/graphs/base/' + graph_name,
                       'attributes': {'frame': frame}, 'nodes': [], 'edges': []})
    write(folder, 'route-trace.jsonl', rows(route_rows))
    frame_rows = [json.loads(line) for line in frame_bytes.splitlines()]
    for frame_row in frame_rows:
        frame_row['carla_frame'] = frame_row['native_frame']
        frame_row['camera_native_frames'] = {
            name: frame_row['native_frame'] for name in CAMERAS}
    write(folder, 'video_frames.jsonl', rows(frame_rows))
    write(folder, 'trace.jsonl', rows(route_core))
    write(folder, 'capture/evidence.jsonl', rows(evidence))
    write(folder, 'capture/native/frames.jsonl', rows(native_frames))
    write(folder, 'road.xodr', road)
    write(folder, 'route-context.json', json.dumps(context, indent=2))
    write(folder, 'capture/recorder_info.txt', 'Create 107: vehicle.tesla.model3')
    write(folder, 'acquisition-provenance.json', json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'native_executed': False}, indent=2))
    write(folder, 'capture/manifest.json', json.dumps({
        'extraction_confirmed': True, 'frames': 900,
        'required_observations': [], 'synthetic_diagnostic': True,
        'sources': {'road.xodr': sha(folder / 'road.xodr'),
                    'trace.jsonl': sha(folder / 'trace.jsonl')}}, indent=2))
    videos = [{'path': name + '.mkv', 'frames': 900,
        'width': 1920 if name == 'overview' else 1280,
        'height': 1080 if name == 'overview' else 720,
        'fps': 20, 'color': color} for name, color in zip(CAMERAS,
                                                        ('blue', 'green', 'white', 'red'))]
    generator = {'files': {}, 'graphs': graphs, 'videos': videos}
    generator_path = HERE / ('selected-generator-' + suffix + '.json')
    generator_path.write_text(json.dumps(generator, separators=(',', ':')) + '\n')
    inventory = [{'path': str(path.relative_to(folder)),
                  'source': str(path.relative_to(ROOT)), 'sha256': sha(path)}
                 for path in sorted(folder.rglob('*')) if path.is_file()]
    recipe = {'format': 'worker-fixture-recipe', 'sources': inventory,
        'generator': {'source': str(generator_path.relative_to(ROOT)),
                      'sha256': sha(generator_path)}}
    recipe_path = HERE / ('selected-recipe-' + suffix + '.json')
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    return {'case': suffix, 'sources': len(inventory),
            'recipe_sha256': sha(recipe_path)}


if __name__ == '__main__':
    print(json.dumps([build(*variant) for variant in VARIANTS]))
