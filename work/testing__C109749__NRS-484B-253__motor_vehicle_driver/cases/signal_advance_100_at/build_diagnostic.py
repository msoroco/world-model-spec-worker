"""Author a compact 20 Hz source diagnostic for the exact 30.48 m case.

This is synthetic software evidence, never physical Native evidence. The
diagnostic keeps source frame, trace, actor-motion and graph packets joined.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

folder = Path(__file__).resolve().parent
assignment = folder.parents[1]
repo = assignment.parent.parent
base = json.loads((assignment / 'cases/inside_yield/diagnostic.json').read_text())
case = assignment.name + '__signal_advance_100_at'
FIRST_FRAME = 38033
FRAMES = 210
START_X = -40.46
SHIFT_X, SHIFT_Y = 100.0, 1.75
template_history = json.loads(base['files']['interaction_history.jsonl'].splitlines()[0])
template_trace = json.loads(base['files']['trace.jsonl'].splitlines()[0])
template_event = json.loads(base['files']['capture/evidence.jsonl'].splitlines()[0])
template_native = json.loads(base['files']['capture/native/frames.jsonl'].splitlines()[0])


def compact(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def actor(role, position, velocity):
    source = template_history[role]
    x0, y0 = source['position_xy_m']
    x, y = position
    body = [[round(px - x0 + x, 6), round(py - y0 + y, 6)]
            for px, py in source['body_vertices_xy_m']]
    return {'actor_id': source['actor_id'], 'position_xy_m': [x, y],
            'velocity_xy_mps': list(velocity), 'body_vertices_xy_m': body}


def motion(index):
    if index <= 32:
        x = START_X + 0.25 * index
        speed = 5.0
    elif index <= 144:
        x = -32.46 + 0.25 * (index - 32)
        speed = 5.0
    elif index <= 190:
        x = -4.46
        speed = 0.0
    elif index <= 200:
        x = -4.46 + 0.248 * (index - 190) + (1e-7 if index == 200 else 0.0)
        speed = 4.96
    else:
        x = -1.98 + 0.3 * (index - 200)
        speed = 6.0
    y = 0.0 if index <= 200 else -0.25 * (index - 200)
    heading = 0.0 if index <= 200 else -min(90.0, 20.0 * (index - 200))
    on_x = 4.0 if index <= 145 else 4.0 - 0.25 * (index - 145)
    on_speed = 0.0 if index <= 145 else 5.0
    reciprocal_x = 30.0 - 0.1 * min(index, 140)
    reciprocal_speed = 2.0 if index < 140 else 0.0
    return {'frame': FIRST_FRAME + index, 'time_s': round((index + 1) / 20, 6),
            'ego': actor('ego', (round(x + SHIFT_X, 7), round(y + SHIFT_Y, 6)),
                         (0.0, 0.0) if speed == 0 else (speed, 0.0)),
            'oncoming': actor('oncoming', (round(on_x + SHIFT_X, 6), SHIFT_Y),
                              (-on_speed, 0.0)),
            'reciprocal': actor('reciprocal',
                                (round(reciprocal_x + SHIFT_X, 6), SHIFT_Y),
                                (-reciprocal_speed, 0.0)),
            'ego_heading_deg': heading,
            'ego_left_indicator': 32 <= index <= 208}


def source_packet(index, row):
    event = copy.deepcopy(template_event)
    frame, time = row['frame'], row['time_s']
    event['original_frame'] = event['replay_frame'] = frame
    event['recording_time_s'] = time
    event['replay_simulation_time_s'] = round(13.517531131161377 + time, 6)
    position = row['ego']['position_xy_m']
    original = event['ego']['position_m']
    dx, dy = position[0] - original[0], position[1] - original[1]
    event['ego']['position_m'] = [position[0], position[1], original[2]]
    event['ego']['body_vertices_m'] = [[round(v[0] + dx, 6), round(v[1] + dy, 6), v[2]]
                                      for v in event['ego']['body_vertices_m']]
    speed = math.hypot(*row['ego']['velocity_xy_mps'])
    event['ego']['speed_mps'] = speed
    event['ego']['heading_deg'] = row['ego_heading_deg']
    event['world']['road_projection']['s_m'] = position[0]
    observation = event['original_observations']
    observation['frame'] = frame
    observation['time_s'] = time
    observation['rgb_sensors'] = [{
        'actor_id': sensor['actor_id'], 'blueprint': sensor['blueprint'],
        'position_m': sensor['position_m'], 'rotation_deg': sensor['rotation_deg'],
        'attributes': {key: sensor['attributes'][key]
                       for key in ('image_size_x', 'image_size_y', 'fov')
                       if key in sensor['attributes']}}
        for sensor in observation['rgb_sensors']]
    for participant in observation['participants']:
        if participant['actor_id'] != row['ego']['actor_id']:
            continue
        original_participant = participant['position_m']
        px, py = position[0] - original_participant[0], position[1] - original_participant[1]
        participant['position_m'] = [position[0], position[1], original_participant[2]]
        participant['body_vertices_m'] = [[round(v[0] + px, 6), round(v[1] + py, 6), v[2]]
                                          for v in participant['body_vertices_m']]
        participant['heading_deg'] = row['ego_heading_deg']
        participant['speed_mps'] = speed
        participant['velocity_mps'] = [*row['ego']['velocity_xy_mps'], 0.0]
        participant['light_attributes'] = {'light_LeftBlinker': row['ego_left_indicator'],
                                           'light_RightBlinker': False}
        participant.pop('blueprint_attributes', None)
        participant.pop('wheel_angle_reference', None)
    return event


def build():
    files = dict(base['files'])
    geometry = json.loads(files['intersection_geometry.json'])
    geometry['intersection_polygon_xy_m'] = [[x + SHIFT_X, y + SHIFT_Y]
                                             for x, y in geometry['intersection_polygon_xy_m']]
    geometry['conflict_point_xy_m'] = [geometry['conflict_point_xy_m'][0] + SHIFT_X,
                                       geometry['conflict_point_xy_m'][1] + SHIFT_Y]
    files['intersection_geometry.json'] = compact(geometry) + '\n'
    history, trace, events, frames, mapping, graphs = [], [], [], [], [], []
    for index in range(FRAMES):
        row = motion(index)
        frame, time = row['frame'], row['time_s']
        event = source_packet(index, row)
        history.append(compact(row))
        events.append(compact(event))
        point = copy.deepcopy(template_trace)
        point['frame'] = frame
        point['time_s'] = time
        xy = row['ego']['position_xy_m']
        point['position'] = {'x': xy[0], 'y': xy[1], 'z': point['position_m'][2]}
        point['position_m'] = [*xy, point['position_m'][2]]
        point['heading_deg'] = row['ego_heading_deg']
        point['speed_mps'] = event['ego']['speed_mps']
        point['speed_mph'] = point['speed_mps'] / 0.44704
        point['velocity_mps'] = [*row['ego']['velocity_xy_mps'], 0.0]
        trace.append(compact(point))
        mapping.append(compact({'video_frame': index, 'carla_frame': frame,
                                'native_frame': frame, 'time_s': time}))
        native = copy.deepcopy(template_native)
        native['frame'] = frame
        native['simulation_time'] = event['replay_simulation_time_s']
        native['abstract'] = f'graphs/abstract/{frame:08d}.pkl'
        native['base'] = f'graphs/base/{frame:08d}.pkl'
        native['nodes'] = 1
        native['edges'] = 0
        frames.append(compact(native))
        attrs = {'frame': frame, 'simulation_time_s': native['simulation_time'],
                 'units': {'distance': 'm', 'time': 's'},
                 'observed_evidence': event['original_observations']}
        for name in ('abstract', 'base'):
            nodes = []
            if name == 'base':
                nodes = [{'id': 'ego', 'attributes': {
                    'vertex': [*xy, point['position_m'][2]],
                    'sem_class': 'ego', 'entity_id': row['ego']['actor_id'],
                    'forward': [math.cos(math.radians(row['ego_heading_deg'])),
                                math.sin(math.radians(row['ego_heading_deg'])), 0.0],
                    'light_LeftBlinker': row['ego_left_indicator'],
                    'light_RightBlinker': False,
                    'carla_speed': point['speed_mps']}}]
            graphs.append({'path': f'capture/native/graphs/{name}/{frame:08d}.pkl',
                           'attributes': attrs, 'nodes': nodes, 'edges': []})
    files.update({'interaction_history.jsonl': '\n'.join(history) + '\n',
                  'trace.jsonl': '\n'.join(trace) + '\n',
                  'video_frames.jsonl': '\n'.join(mapping) + '\n',
                  'capture/evidence.jsonl': '\n'.join(events) + '\n',
                  'capture/native/frames.jsonl': '\n'.join(frames) + '\n'})
    manifest = json.loads(files['capture/manifest.json'])
    manifest['case_id'] = case
    manifest['frames'] = FRAMES
    manifest['sources']['trace.jsonl'] = hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()
    manifest['sources']['road.xodr'] = hashlib.sha256(files['road.xodr'].encode()).hexdigest()
    files['capture/manifest.json'] = compact(manifest) + '\n'
    provenance = json.loads(files['fixture-provenance.json'])
    provenance['scope'] = '210-frame 30.48 m signal-advance software diagnostic; no physical acceptance'
    files['fixture-provenance.json'] = compact(provenance) + '\n'
    videos = [dict(video, frames=FRAMES) for video in base['videos']]
    spec = {'files': files, 'graphs': graphs, 'videos': videos}
    output = folder / 'diagnostic.json'
    output.write_text(compact(spec) + '\n')
    if output.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Diagnostic source exceeds the 2 MiB return limit')
    source = 'work/' + assignment.name + '/cases/signal_advance_100_at/diagnostic.json'
    checksum = digest(output)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': source,
                           'sha256': checksum}],
              'generator': {'source': source, 'sha256': checksum}}
    (folder / 'diagnostic-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
    print(json.dumps({'frames': FRAMES, 'size_bytes': output.stat().st_size,
                      'diagnostic_sha256': checksum}))


if __name__ == '__main__':
    build()
