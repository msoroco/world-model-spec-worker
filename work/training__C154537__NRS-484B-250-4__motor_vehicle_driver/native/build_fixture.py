"""Build two source-specific 600-frame synthetic software diagnostics."""
import hashlib
import json
from pathlib import Path

from route import requested_rows

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = Path.cwd().resolve()
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + '\n')


def text(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True, allow_nan=False) + '\n'
                            for row in rows))


def body(x, y, eastbound=True):
    dx, dy = (2, .9) if eastbound else (.9, 2)
    return [[x + sx * dx, y + sy * dy, z]
            for sx in (-1, 1) for sy in (-1, 1) for z in (0, 1.5)]


def graph(frame, x, y):
    return {'path': f'capture/native/graphs/base/{frame:08d}.adapter.json',
            'attributes': {'frame': frame, 'simulation_time_s': frame / 20,
                           'source': 'C154537 no-line/no-crosswalk request diagnostic',
                           'synthetic_diagnostic': True},
            'nodes': [
                {'id': 'ego', 'attributes': {'entity_id': 10, 'sem_class': 'ego',
                    'vertex': [x, -1.75, .5], 'forward': [1, 0, 0],
                    'threedbbox': body(x, -1.75)}},
                {'id': 'other', 'attributes': {'entity_id': 11, 'sem_class': 'vehicle',
                    'vertex': [1.75, y, .5], 'forward': [0, 1, 0],
                    'threedbbox': body(1.75, y, False)}}], 'edges': []}


def build(case):
    rows = list(requested_rows(case))
    source = HERE / 'diagnostic' / case
    source.mkdir(parents=True, exist_ok=True)
    survey = {'source_kind': 'synthetic_original_shape',
              'diagnostic_fixture': True,
              'stop_line_present': False, 'near_side_crosswalk_present': False,
              'sidewalk_derived_crosswalk_reviewed': True,
              'signal_installed': True, 'signal_uncovered': True,
              'official_device_provenance_reviewed': True,
              'through_highway_provenance_reviewed': True,
              'signal_id': '701', 'ego_front_offset_m': 2.0,
              'intersection_entry_front_x_m': -6.0,
              'driver_view_samples': [
                  {'native_frame': frame, 'center_x_m': x,
                   'other_actor_id': 11, 'approaching_traffic_visible': x >= -11,
                   'rays': [{'clear': x >= -11,
                             'blockers': [] if x >= -11 else [{'label': 'synthetic_occluder'}]}
                            for _ in range(9)]}
                  for frame, x in ((100, -15), (110, -13), (120, -11), (130, -9))],
              'physical_acceptance_claimed': False}
    put(source / 'scene-survey.json', survey)
    motions, mappings, traces, evidence, native_frames, graphs = [], [], [], [], [], []
    for frame, row in enumerate(rows):
        x, y = row['ego_center_xy_m'][0], row['other_center_xy_m'][1]
        previous = rows[max(0, frame - 1)]['ego_center_xy_m'][0]
        speed = 4 if frame == 0 else round(20 * (x - previous), 6)
        motions.append({'native_frame': frame, 'video_frame': frame,
                        'time_s': frame / 20, 'ego_center_x_m': x,
                        'ego_front_x_m': x + 2, 'ego_speed_mps': speed,
                        'signal_id': '701', 'signal_state': 'inoperative_dark',
                        'other': {'actor_id': 11, 'center_xyz_m': [1.75, y, .5]},
                        'diagnostic_fixture': True})
        mappings.append({'native_frame': frame, 'carla_frame': frame,
                         'video_frame': frame, 'time_s': frame / 20,
                         'camera_native_frames': {name: frame for name in CAMERAS}})
        traces.append({'frame': frame, 'time_s': frame / 20,
                       'position_m': [x, -1.75, .5],
                       'velocity_mps': [speed, 0, 0], 'speed_mps': speed,
                       'heading_deg': 0,
                       'source_kind': 'synthetic_original_shape'})
        road_id = 250 if x < -6 else 251 if x <= 6 else 252
        station = x + 60 if road_id == 250 else x + 6 if road_id == 251 else x - 6
        evidence.append({'actor_id': 10, 'original_frame': frame,
                         'recording_time_s': frame / 20, 'replay_frame': frame,
                         'replay_simulation_time_s': frame / 20,
                         'ego': {'position_m': [x, -1.75, .5], 'heading_deg': 0,
                                 'speed_mps': speed, 'speed_provenance': 'synthetic_native_sample',
                                 'body_vertices_m': body(x, -1.75),
                                 'synthetic_diagnostic': True},
                         'other_actors': [{'actor_id': 11, 'position_m': [1.75, y, .5],
                                           'body_vertices_m': body(1.75, y, False)}],
                         'world': {'road_projection': {'road_id': road_id, 'lane_id': -1,
                                                       'section_id': 0, 's_m': station},
                                   'weather': {'cloudiness': 0, 'fog_density': 0,
                                               'precipitation': 0, 'wetness': 0}}})
        relative = f'graphs/base/{frame:08d}.adapter.json'
        native_frames.append({'frame': frame, 'simulation_time': frame / 20,
                              'adapter_graph': relative, 'base': relative,
                              'nodes': 2, 'edges': 0})
        graphs.append(graph(frame, x, y))
    text(source / 'native-motion.jsonl', motions)
    text(source / 'video_frames.jsonl', mappings)
    text(source / 'trace.jsonl', traces)
    text(source / 'capture/evidence.jsonl', evidence)
    put(source / 'capture/manifest.json', {'extraction_confirmed': True, 'frames': 600,
        'sources': {'crossroads.xodr': sha(HERE / 'crossroads.xodr'),
                    'trace.jsonl': sha(source / 'trace.jsonl')},
        'synthetic_diagnostic': True})
    spec = {'files': {'capture/native/frames.jsonl': ''.join(
                        json.dumps(row, sort_keys=True) + '\n' for row in native_frames),
                      'capture/recorder_info.txt':
                      'synthetic C154537 CPU diagnostic; no CARLA recorder\n'
                      'Create 10: vehicle.tesla.model3 (0)\n'
                      'Create 11: vehicle.audi.tt (0)\n'},
            'graphs': graphs,
            'videos': [{'path': name + '.mkv', 'frames': 600, 'fps': 20,
                        'width': 1920 if name == 'overview' else 1280,
                        'height': 1080 if name == 'overview' else 720,
                        'color': 'black'} for name in CAMERAS]}
    spec_path = HERE / f'diagnostic-{case}-fixture-spec.json'
    put(spec_path, spec)
    refs = ['scene-survey.json', 'native-motion.jsonl', 'video_frames.jsonl',
            'trace.jsonl', 'capture/evidence.jsonl', 'capture/manifest.json']
    recipe = {'format': 'worker-fixture-recipe',
              'generator': {'source': str(spec_path.relative_to(REPO)), 'sha256': sha(spec_path)},
              'sources': [{'path': name, 'source': str((source / name).relative_to(REPO)),
                           'sha256': sha(source / name)} for name in refs]}
    recipe_path = HERE / f'diagnostic-{case}-fixture-recipe.json'
    put(recipe_path, recipe)
    return {'case': case, 'spec_sha256': sha(spec_path),
            'recipe_sha256': sha(recipe_path),
            'source_count': len(refs), 'graph_count': len(graphs)}


if __name__ == '__main__':
    print(json.dumps([build(case) for case in ('controlled_1', 'controlled_2')]))
