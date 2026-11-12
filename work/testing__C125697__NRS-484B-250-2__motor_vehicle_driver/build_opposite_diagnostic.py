"""Build original-source synthetic turn motion for the opposite comparison."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'cases/off_opposite_left_turn'
CASE = HERE.name + '__off_opposite_left_turn'


def lines(rows):
    return ''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows)


def body(x, y, yaw):
    angle = math.radians(yaw)
    forward = math.cos(angle), math.sin(angle)
    lateral = -forward[1], forward[0]
    return [[x + a * forward[0] + b * lateral[0],
             y + a * forward[1] + b * lateral[1]]
            for a, b in ((-1.8, -0.85), (-1.8, 0.85),
                         (1.8, 0.85), (1.8, -0.85))]


def build():
    spec = json.loads((HERE / 'diagnostic.json').read_text())
    files = spec['files']
    config = json.loads((OUT / 'config.json').read_text())
    context = json.loads(files['junction_context.json'])
    context.update(ego_highway_id='east-west', other_highway_id='east-west',
                   ego_road_id=1, other_road_id=1,
                   ego_approach_forward_xy=[1, 0],
                   other_approach_forward_xy=[-1, 0],
                   opposite_approach_with_left_turn=True,
                   other_left_turn_route_xy_m=config['site']['routes']['other'])
    files['junction_context.json'] = json.dumps(context, allow_nan=False) + '\n'
    frame_rows, crossing, controls, trace = [], [], [], []
    for index, frame in enumerate(range(100, 221)):
        time_s = 1 + index / 20
        moving = max(0, frame - 120)
        ego_x = min(19, moving * 0.25)
        if frame <= 180:
            other_x, other_y = max(15, 30 - moving * 0.25), 1.75
            other_yaw = 180
        else:
            other_x, other_y = 15, 1.75 - (frame - 180) * 0.25
            other_yaw = 225 if frame == 181 else 270
        ego_speed = 0 if frame < 120 or ego_x >= 19 else 5
        other_speed = 0 if frame < 120 else 5
        steer = -0.3 if 179 <= frame <= 184 else 0
        frame_rows.append({'video_frame': index, 'carla_frame': frame, 'time_s': time_s})
        ego_body = body(ego_x, -1.75, 0)
        other_body = body(other_x, other_y, other_yaw)
        crossing.append({
            'frame': frame, 'time_s': time_s,
            'governing_signal_state': 'Off',
            'entrance_signal_states': [{'actor_id': 17, 'state': 'Off'},
                                       {'actor_id': 18, 'state': 'Off'}],
            'ego': {'actor_id': 101, 'position_xy_m': [ego_x, -1.75],
                    'heading_deg': 0, 'body_vertices_xy_m': ego_body,
                    'intersection_id': 44, 'road_id': 1,
                    'speed_mps': ego_speed, 'velocity_mps': [ego_speed, 0, 0]},
            'other': {'actor_id': 102, 'position_xy_m': [other_x, other_y],
                      'heading_deg': other_yaw, 'body_vertices_xy_m': other_body,
                      'intersection_id': 44, 'road_id': 1,
                      'speed_mps': other_speed,
                      'velocity_mps': [-other_speed, 0, 0] if frame <= 180
                                      else [0, -other_speed, 0]},
            'ego_vertices_m': ego_body,
        })
        controls.append({'frame': frame, 'time_s': time_s,
                         'ego_held': frame < 120, 'other_held': frame < 120,
                         'ego_steer': 0, 'other_steer': steer,
                         'route_target_index': {'ego': 1, 'other': 2 if frame <= 180 else 3}})
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': {'x': ego_x, 'y': -1.75, 'z': 0},
                      'heading_deg': 0, 'speed_mps': ego_speed,
                      'velocity_mps': [ego_speed, 0, 0],
                      'control': {'throttle': 0 if frame < 120 else .3,
                                  'steer': 0, 'brake': 1 if frame < 120 else 0,
                                  'hand_brake': False, 'reverse': False}})
    files['video_frames.jsonl'] = lines(frame_rows)
    files['crossing_history.jsonl'] = lines(crossing)
    files['controller_history.jsonl'] = lines(controls)
    files['trace.jsonl'] = lines(trace)
    spec['graphs'] = []
    for video in spec['videos']:
        video['frames'] = len(frame_rows)
    OUT.mkdir(parents=True, exist_ok=True)
    diagnostic = OUT / 'diagnostic.json'
    diagnostic.write_text(json.dumps(spec, indent=2, allow_nan=False) + '\n')
    source = str(diagnostic.relative_to(HERE.parents[1]))
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': source, 'sha256': ''}],
              'generator': {'source': source, 'sha256': ''}}
    (OUT / 'diagnostic-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
    module_spec = importlib.util.spec_from_file_location('augment_opposite',
                                                          HERE / 'augment_diagnostic_capture.py')
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    module.HERE = OUT
    module.CASE = CASE
    module.HEADINGS = ((101, 'ego', 0), (102, 'other', 180))
    augmented = module.build()
    manifest = json.loads((OUT / 'candidate-manifest.json').read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'] == CASE)
    entry['fixture_recipe'] = source.replace('diagnostic.json', 'diagnostic-recipe.json')
    entry['acquisition'] = manifest['cases'][0]['acquisition']
    (OUT / 'candidate-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return {'case_id': CASE, **augmented}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
