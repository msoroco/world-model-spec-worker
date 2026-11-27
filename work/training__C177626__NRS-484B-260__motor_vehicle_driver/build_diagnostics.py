"""Source-shaped synthetic CPU fixtures for two exact private-way entry cases."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows)


def put(path, item):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(item, indent=2, allow_nan=False).rstrip() + '\n')


def rect(x, y, hx, hy):
    return [[x - hx, y - hy], [x - hx, y + hy],
            [x + hx, y - hy], [x + hx, y + hy]]


def main():
    road = (ROOT / 'native/geometry.py').read_text()
    import sys
    sys.path.insert(0, str(ROOT / 'native'))
    from geometry import open_drive
    road = open_drive() + '\n'
    for suffix, source in (('probe_a', 'yield_both'), ('probe_b', 'enter_before_second')):
        case = ROOT.name + '__' + suffix
        raw = [json.loads(line) for line in (ROOT / 'fixtures/private_entry' / source / 'actors.jsonl').read_text().splitlines()]
        poses, frames, traces, evidence, replay, graphs = [], [], [], [], [], []
        for i, original in enumerate(raw):
            native, time = original['frame'], original['time_s']
            ego_xy = [2, original['actors']['ego']['y_m'] - 2]
            actors = {}
            for name, ident in (('ego', 1), ('approach_1', 2), ('approach_2', 3)):
                x, y = (ego_xy if name == 'ego' else
                        [original['actors'][name]['x_m'] + 2, -2])
                body = rect(x, y, .8 if name == 'ego' else 2.1,
                            2.1 if name == 'ego' else .8)
                speed = 2 if name == 'ego' else 5
                actors[name] = {'actor_id': ident, 'blueprint_id': 'vehicle.tesla.model3',
                                'center_xy_m': [x, y], 'body_xy_m': body,
                                'velocity_xy_mps': [0, speed] if name == 'ego' else [speed, 0],
                                'speed_mps': speed}
            all_actors = {str(actor['actor_id']): actor for actor in actors.values()}
            poses.append({'native_frame': native, 'video_frame': i, 'time_s': time,
                          'actors': actors, 'all_vehicle_bodies': all_actors})
            frames.append({'video_frame': i, 'native_frame': native,
                           'carla_frame': native, 'time_s': time,
                           'camera_native_frames': dict.fromkeys(VIEWS, native)})
            xyz = [ego_xy[0], ego_xy[1], 1.0]
            traces.append({'frame': native, 'time_s': time,
                           'position': {'x': xyz[0], 'y': xyz[1], 'z': xyz[2]},
                           'position_m': xyz, 'heading_deg': 90, 'speed_mps': 2,
                           'speed_mph': 2 / .44704, 'velocity_mps': [0, 2, 0],
                           'control': {}})
            bbox = [[ego_xy[0] + dx, ego_xy[1] + dy, z]
                    for dx in (-.8, .8) for dy in (-2.1, 2.1) for z in (.5, 1.5)]
            evidence.append({'original_frame': native, 'replay_frame': native,
                             'actor_id': 1, 'recording_time_s': time,
                             'replay_simulation_time_s': time,
                             'ego': {'position_m': xyz, 'heading_deg': 90,
                                     'speed_mps': 2,
                                     'speed_provenance': 'synthetic_native_sample',
                                     'body_vertices_m': bbox},
                             'synthetic_diagnostic': True,
                             'world': {'road_projection': {'road_id': 2,
                                                           'lane_id': -1,
                                                           'section_id': 0,
                                                           's_m': 13 + 2 * time}}})
            graph = f'graphs/base/{native:08d}.adapter.json'
            replay.append({'frame': native, 'time_s': time,
                           'simulation_time': time, 'synthetic_diagnostic': True,
                           'adapter_graph': graph})
            graphs.append({'path': 'capture/native/' + graph,
                           'attributes': {'frame': native, 'simulation_time_s': time,
                                          'synthetic_diagnostic': True,
                                          'source': 'C177626 private-way CPU diagnostic'},
                           'nodes': [{'id': 'ego', 'attributes': {
                               'sem_class': 'ego', 'entity_id': 1, 'vertex': xyz,
                               'forward': [0, 1, 0], 'threedbbox': bbox}}],
                           'edges': []})
        pose_text, trace_text = lines(poses), lines(traces)
        files = {'road.xodr': road,
                 'private-entry-actors.jsonl': pose_text,
                 'video_frames.jsonl': lines(frames),
                 'trace.jsonl': trace_text,
                 'capture/evidence.jsonl': lines(evidence),
                 'capture/native/frames.jsonl': lines(replay),
                 'capture/recorder_info.txt': 'Synthetic C177626 software diagnostic; no CARLA recorder\nCreate 1: vehicle.tesla.model3 (0)\nCreate 2: vehicle.tesla.model3 (0)\nCreate 3: vehicle.tesla.model3 (0)\n',
                 'capture/manifest.json': json.dumps({
                     'extraction_confirmed': True, 'frames': 600,
                     'required_observations': [],
                     'sources': {'trace.jsonl': sha(trace_text), 'road.xodr': sha(road)},
                     'synthetic_diagnostic': True}) + '\n',
                 'private-entry-context.json': json.dumps({
                     'source_kind': 'synthetic_cpu_private_way_entry',
                     'case_id': case,
                     'all_vehicle_inventory_method': 'all actor bodies from source-shaped rows',
                     'private_way_and_highway': {'source': 'synthetic authored geometry; not physical proof'},
                     'physical_and_legal_acceptance_claimed': False}) + '\n'}
        review_sources = ('road.xodr', 'private-entry-context.json',
                          'private-entry-actors.jsonl', 'video_frames.jsonl',
                          'trace.jsonl', 'capture/manifest.json')
        review = {'case_id': case,
                  'review_kind': 'synthetic_diagnostic',
                  'source_sha256': {name: sha(files[name]) for name in review_sources},
                  'physical_acceptance_claimed': False}
        for view in VIEWS:
            review['source_sha256'][view + '.mkv'] = None
        files['private-entry-review.json'] = json.dumps(review, indent=2) + '\n'
        spec = {'files': files, 'graphs': graphs,
                'videos': [{'path': view + '.mkv', 'frames': 600,
                            'width': 1920 if view == 'overview' else 1280,
                            'height': 1080 if view == 'overview' else 720,
                            'fps': 20, 'color': 'black'} for view in VIEWS]}
        path = ROOT / 'cases' / suffix / 'diagnostic.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(spec, separators=(',', ':'), allow_nan=False) + '\n')
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json',
                               'source': str(path.relative_to(REPO)),
                               'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}],
                  'generator': {'source': str(path.relative_to(REPO)),
                                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}
        put(ROOT / 'cases' / suffix / 'recipe.json', recipe)
        print(suffix, path.stat().st_size)


if __name__ == '__main__':
    main()
