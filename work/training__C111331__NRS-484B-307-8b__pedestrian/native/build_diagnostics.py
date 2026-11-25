"""Write textual, source-bound synthetic diagnostics for the exact five cases."""

import hashlib
import json
from pathlib import Path

from native_red import CAMERAS, CONDITIONS, FRAMES, plan
from prove_source_join import fixture

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
REPO = ASSIGNMENT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)


def write(path, value):
    path.write_text(json.dumps(value, separators=(',', ':'), ensure_ascii=False) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Diagnostic exceeds worker file limit: ' + str(path))


def build(condition):
    config = plan(condition)
    samples, mapping, cameras = fixture(config)
    pixels = {name: hashlib.sha256(bytes(width * height * 3)).hexdigest()
              for name, width, height, _ in CAMERAS}
    for row in samples:
        row['source_rgb_sha256'] = pixels
    for row in mapping:
        row['source_rgb_sha256'] = pixels
    for row in cameras:
        row['source_rgb_sha256'] = pixels[row['camera']]
    trace = []
    evidence = []
    frames = []
    graphs = []
    body = []
    for row in samples:
        frame, time_s = row['native_frame'], row['time_s']
        x = sum(point[0] for point in row['footprint_xy_m']) / 4
        y = sum(point[1] for point in row['footprint_xy_m']) / 4
        source = {k: v for k, v in row.items() if k != 'source_rgb_sha256'}
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': {'x': x, 'y': y, 'z': 0.5},
                      'position_m': [x, y, 0.5], 'heading_deg': -90.0,
                      'speed_mps': 0.0, 'speed_mph': 0.0,
                      'velocity_mps': [0, 0, 0],
                      'control': {'throttle': 0, 'steer': 0, 'brake': 0,
                                  'hand_brake': False},
                      'red_entry_source': source})
        vertices = [[x - 0.25, y - 0.25, 0], [x + 0.25, y - 0.25, 0],
                    [x + 0.25, y + 0.25, 0], [x - 0.25, y + 0.25, 0]]
        evidence.append({'original_frame': frame, 'replay_frame': frame,
                         'recording_time_s': time_s, 'replay_simulation_time_s': time_s,
                         'actor_id': row['walker_id'],
                         'ego': {'position_m': [x, y, 0.5], 'heading_deg': -90.0,
                                 'speed_mps': 0.0, 'body_vertices_m': vertices,
                                 'speed_provenance': 'synthetic_native_sample'},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 1, 'section_id': 0,
                                                       'lane_id': -1, 's_m': y}}})
        body.append({'frame': frame, 'actor_id': row['walker_id'],
                     'body_vertices_m': vertices})
        graph = f'capture/native/graphs/base/{frame:08d}.adapter.json'
        frames.append({'abstract': f'graphs/base/{frame:08d}.adapter.json',
                       'adapter_graph': f'graphs/base/{frame:08d}.adapter.json',
                       'base': f'graphs/base/{frame:08d}.adapter.json',
                       'edges': 0, 'frame': frame, 'nodes': 0,
                       'simulation_time': time_s, 'time_s': time_s,
                       'synthetic_diagnostic': True})
        graphs.append({'path': graph, 'attributes': {'frame': frame},
                       'nodes': [], 'edges': []})
    files = {'video_frames.jsonl': lines(mapping),
             'camera-sources.jsonl': lines(cameras),
             'trace.jsonl': lines(trace),
             'capture/evidence.jsonl': lines(evidence),
             'capture/native/frames.jsonl': lines(frames),
             'capture/manifest.json': json.dumps({
                 'frames': FRAMES, 'extraction_confirmed': True,
                 'synthetic_diagnostic': True, 'case_id': config['case_id'],
                 'sources': {'road.xodr': sha(HERE / 'road.xodr'),
                             'trace.jsonl': hashlib.sha256(lines(trace).encode()).hexdigest()},
                 'required_observations': config['required_atoms']}),
             'capture/recorder_info.txt': 'Synthetic CPU diagnostic; no CARLA recording.\n'
                 + f"Create {samples[0]['walker_id']}: walker.pedestrian.0001 (0)\n"}
    spec = {'files': files, 'graphs': graphs,
            'videos': [{'path': name + '.mkv', 'frames': FRAMES,
                        'width': width, 'height': height,
                        'fps': 20, 'color': 'black'}
                       for name, width, height, _ in CAMERAS]}
    path = ASSIGNMENT / ('diagnostic-' + condition + '.json')
    source_path = ASSIGNMENT / ('diagnostic-source-' + condition + '.jsonl')
    source_path.write_text(lines(samples))
    body_path = ASSIGNMENT / ('diagnostic-body-' + condition + '.jsonl')
    body_path.write_text(lines(body))
    write(path, spec)
    assignment = REPO / 'inputs' / ASSIGNMENT.name / 'assignment.json'
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input-assignment.json',
                           'source': str(assignment.relative_to(REPO)),
                           'sha256': sha(assignment)},
                          {'path': 'body_history.jsonl',
                           'source': str(body_path.relative_to(REPO)),
                           'sha256': sha(body_path)},
                          {'path': 'red-entry-original.jsonl',
                           'source': str(source_path.relative_to(REPO)),
                           'sha256': sha(source_path)}],
              'generator': {'source': str(path.relative_to(REPO)),
                            'sha256': sha(path)}}
    recipe_path = ASSIGNMENT / ('diagnostic-' + condition + '-recipe.json')
    write(recipe_path, recipe)
    return {'condition': condition, 'spec_bytes': path.stat().st_size,
            'spec_sha256': sha(path), 'recipe_sha256': sha(recipe_path)}


if __name__ == '__main__':
    print(json.dumps([build(condition) for condition in CONDITIONS]))
