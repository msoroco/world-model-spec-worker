"""Build small textual diagnostic sources for both selected crossing cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
AID = ROOT.name
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value, indent=2, sort_keys=True) + '\n')


def lines(values):
    return ''.join(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n' for value in values)


def body(x, y):
    return [[x + dx, y + dy, z] for dx in (-.2, .2) for dy in (-.2, .2) for z in (0, 1.8)]


def build(suffix, departure):
    root = HERE / 'diagnostic' / suffix
    sources = root / 'sources'
    mapped, rows, trace, evidence, native, graphs = [], [], [], [], [], []
    for index in range(600):
        time = round(index / 20, 6)
        x = -5 if index < departure else min(5, -3.6 + .06 * (index - departure))
        y = 10
        vehicle_y = min(30, -20 + .11 * index)
        frame = index
        mapped.append({'video_frame': index, 'native_frame': frame, 'carla_frame': frame,
                       'time_s': time, 'camera_native_frames': {name: frame for name in CAMERAS}})
        rows.append({'native_frame': frame, 'time_s': time, 'pedestrian_id': 5,
                     'pedestrian_footprint_xy_m': [[x-.2,y-.2],[x+.2,y-.2],[x+.2,y+.2],[x-.2,y+.2]],
                     'vehicles': [{'id': 9, 'x_m': -1.75, 'y_m': vehicle_y, 'speed_mps': 2.2}],
                     'source': 'synthetic_scene_request'})
        trace.append({'frame': frame, 'time_s': time,
                      'position': {'x': x, 'y': y, 'z': .5},
                      'position_m': [x, y, .5], 'heading_deg': 0,
                      'speed_mps': 1.2 if index >= departure else 0,
                      'speed_mph': (1.2 if index >= departure else 0) / .44704,
                      'velocity_mps': [1.2 if index >= departure else 0, 0, 0],
                      'control': {}})
        evidence.append({'actor_id': 5, 'original_frame': frame, 'replay_frame': frame,
                         'recording_time_s': time, 'replay_simulation_time_s': time,
                         'ego': {'position_m': [x, y, .5], 'body_vertices_m': body(x,y),
                                 'heading_deg': 0, 'speed_mps': 1.2 if index >= departure else 0,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'synthetic_diagnostic': True},
                         'other_actors': [{'actor_id': 9, 'position_m': [-1.75, vehicle_y, .5],
                                           'body_vertices_m': body(-1.75,vehicle_y)}],
                         'world': {'road_projection': {'road_id': 1, 'lane_id': 1,
                                                       'section_id': 0, 's_m': vehicle_y},
                                   'weather': {'cloudiness': 0, 'fog_density': 0,
                                               'precipitation': 0, 'wetness': 0}}})
        graph_path = f'capture/native/graphs/base/{index:08d}.adapter.json'
        native.append({'frame': frame, 'simulation_time': time,
                       'adapter_graph': f'graphs/base/{index:08d}.adapter.json',
                       'base': f'graphs/base/{index:08d}.adapter.json', 'nodes': 2, 'edges': 0})
        graphs.append({'path': graph_path,
                       'attributes': {'frame': frame, 'simulation_time_s': time,
                                      'source': 'C190398 overhead-crossing CPU diagnostic',
                                      'synthetic_diagnostic': True},
                       'nodes': [{'id': 'ego', 'attributes': {'entity_id': 5, 'sem_class': 'ego',
                                                            'vertex': [x,y,.5], 'forward': [1,0,0],
                                                            'threedbbox': body(x,y)}},
                                 {'id': 'vehicle', 'attributes': {'entity_id': 9,
                                                                 'sem_class': 'vehicle',
                                                                 'vertex': [-1.75,vehicle_y,.5],
                                                                 'forward': [0,1,0],
                                                                 'threedbbox': body(-1.75,vehicle_y)}}],
                       'edges': []})
    write(sources / 'post-tick.jsonl', lines(rows))
    write(sources / 'video_frames.jsonl', lines(mapped))
    write(sources / 'trace.jsonl', lines(trace))
    write(sources / 'capture/evidence.jsonl', lines(evidence))
    write(sources / 'road.xodr', (HERE / 'draft_road.xodr').read_text())
    write(sources / 'crossing-context.json', {
        'trace_sha256': sha(sources / 'post-tick.jsonl'),
        'frozen_cell': {'layout': 'pedestrian_overpass', 'maneuver': 'straight', 'control': 'other_vehicle'},
        'source_kind': 'synthetic_scene_request',
        'grade_separation': {'road_id': 2, 'provided': True, 'crossing_y_m': 10.0,
                             'elevation_m': 5.5, 'span_x_m': [-10, 10]},
        'marked_crosswalk_intervals_y_m': [],
        'intersection_intervals_y_m': [], 'designated_place_prohibition': None,
        'pedestrian_id': 5, 'vehicle_ids': [9],
        'limitations': ['Synthetic diagnostic only; no original motion or legal applicability']})
    write(sources / 'capture/manifest.json', {'extraction_confirmed': True,
          'frames': 600, 'synthetic_diagnostic': True,
          'sources': {'road.xodr': sha(sources / 'road.xodr'),
                      'post-tick.jsonl': sha(sources / 'post-tick.jsonl'),
                      'trace.jsonl': sha(sources / 'trace.jsonl')}})
    spec = {'files': {'capture/native/frames.jsonl': lines(native),
                      'capture/recorder_info.txt': 'Synthetic diagnostic; no Native recording.\nCreate 5: walker.pedestrian.0001 (0)\nCreate 9: vehicle.tesla.model3 (0)\n'},
            'graphs': graphs,
            'videos': [{'path': name + '.mkv', 'frames': 600,
                        'width': 1920 if name == 'overview' else 1280,
                        'height': 1080 if name == 'overview' else 720,
                        'fps': 20, 'color': 'black'} for name in CAMERAS]}
    spec_path = root / 'fixture-spec.json'
    write(spec_path, spec)
    repo = Path.cwd()
    recipe = {'format': 'worker-fixture-recipe',
              'generator': {'source': str(spec_path.relative_to(repo)), 'sha256': sha(spec_path)},
              'sources': [{'path': str(path.relative_to(sources)),
                           'source': str(path.relative_to(repo)), 'sha256': sha(path)}
                          for path in sorted(sources.rglob('*')) if path.is_file() and
                          path.name != 'road.xodr']}
    write(root / 'fixture-recipe.json', recipe)
    return {'case_id': AID + '__' + suffix, 'recipe_sha256': sha(root/'fixture-recipe.json')}


if __name__ == '__main__':
    print(json.dumps([build('yield', 320), build('enter_ahead', 140)], indent=2))
