"""Build short textual CPU diagnostics for the exact arrow/crosswalk cases."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def body(x, y):
    return [[x, y, 0], [x + 1, y, 0], [x + 1, y + 1, 0], [x, y + 1, 0]]


def write_case(suffix):
    fixture = json.loads((REPO / 'runtime/fixtures/example.json').read_text())
    files = fixture['files']
    trace = [json.loads(line) for line in files['trace.jsonl'].splitlines()
             if line.strip()]
    mapping = [json.loads(line) for line in files['video_frames.jsonl'].splitlines()
               if line.strip()]
    if len(trace) != len(mapping) or len(trace) != 9:
        raise ValueError('pinned CPU diagnostic frame shape changed')
    occupied = suffix == 'crosswalk_occupied_yield'
    traffic_case = suffix == 'lawful_traffic_yield'
    context = {'map_source': 'diagnostic/Native-shaped map',
        'adjacent_crosswalk_source': 'diagnostic/Native-shaped marked vertices',
        'ego_route_source': 'diagnostic/Native-shaped connected waypoints',
        'facing_head_source': 'diagnostic/Native-shaped official arrow asset',
        'lawful_presence_method': 'diagnostic Walk entry and geometry' if occupied else 'no pedestrian',
        'facing_head_id': 7, 'adjacent_crosswalk_bounds_m': [-2, 4, 2, 8],
        'route_waypoints': [{'x_m': x, 'y_m': y, 'road_id': 1, 'lane_id': 1}
            for x, y in [(-20, -1.75), (-4, -1.75), (0, 0), (0, 20)]],
        'crosswalk_vertices_m': [[-2, 4, 0], [2, 4, 0],
                                  [2, 8, 0], [-2, 8, 0]],
        'camera_profile': 'overview1080-capability', 'duration_s': 30,
        'pedestrian_entry_source': 'pedestrian-entry.jsonl' if occupied else None,
        'other_vehicle_entry_source': 'traffic-entry.jsonl' if traffic_case else None,
        'other_vehicle_signal_head_id': 9 if traffic_case else None,
        'other_vehicle_route_waypoints': ([{'x_m': 0, 'y_m': y,
            'road_id': 2, 'lane_id': 1} for y in (-12, 0, 10)] if traffic_case else None),
        'other_vehicle_lawfulness_method': 'diagnostic green entry and connected route' if traffic_case else 'no other traffic',
        'diagnostic_only': True}
    files['intersection-context.json'] = json.dumps(context, sort_keys=True) + '\n'
    rows = []
    xs = [-10, -9, -8, -7, -6, -5, -4, -1, 0]
    headings = [0, 0, 0, 0, 0, 20, 40, 65, 90]
    for index, (motion, frame) in enumerate(zip(trace, mapping)):
        if (motion['frame'], motion['time_s']) != (frame['carla_frame'], frame['time_s']):
            raise ValueError('pinned diagnostic trace/video join changed')
        person = []
        if occupied:
            person = [{'id': 2, 'role': 'pedestrian',
                'source_ref': 'diagnostic/Native-shaped walker',
                'lawful_presence_source': 'pedestrian-entry.jsonl and original Walk head',
                'lawfully_present': True,
                'body_vertices_m': body(0 if index < 3 else 5, 5)}]
        ego_y = 4 if index == 8 else (-1.75 if index < 7 else 0)
        traffic = ([{'id': 3, 'role': 'motor_vehicle',
            'source_ref': 'diagnostic/Native-shaped other vehicle',
            'lawful_presence_source': 'traffic-entry.jsonl and original green head',
            'lawfully_using_intersection': True,
            'body_vertices_m': body(0, index)}] if traffic_case and index < 3 else [])
        rows.append({'frame': motion['frame'], 'time_s': motion['time_s'],
            'facing_signal': {'source_verified': True,
                'source_ref': 'diagnostic/Native-shaped facing head 7',
                'head_id': 7, 'observed_frame': motion['frame'],
                'illuminated_indications': [{'color': 'green', 'shape': 'arrow',
                                            'direction': 'left'}]},
            'ego': {'source_ref': 'diagnostic/Native-shaped ego',
                'heading_source': 'diagnostic/Native-shaped transform',
                'heading_deg': headings[index], 'body_vertices_m': body(xs[index], ego_y),
                'speed_mps': 0 if (occupied or traffic_case) and index < 3 else 2,
                'brake': 1 if (occupied or traffic_case) and index < 3 else 0},
            'pedestrians': person, 'other_traffic': traffic})
    files['turn-history.jsonl'] = ''.join(json.dumps(row, sort_keys=True) + '\n'
                                         for row in rows)
    names = ['turn-history.jsonl', 'intersection-context.json', 'video_frames.jsonl']
    if occupied:
        entry = [{'frame': trace[0]['frame'] - 3 + index,
                  'time_s': trace[0]['time_s'] - .15 + index / 20,
                  'pedestrian_signal_head_id': 8, 'walk_state': 'Walk',
                  'person_body_vertices_m': body(x, 5)}
                 for index, x in enumerate((-3, -2, 0))]
        files['pedestrian-entry.jsonl'] = ''.join(json.dumps(row) + '\n'
                                                  for row in entry)
        names.append('pedestrian-entry.jsonl')
    if traffic_case:
        entry = [{'frame': trace[0]['frame'] - 3 + index,
                  'time_s': trace[0]['time_s'] - .15 + index / 20,
                  'other_vehicle_signal_head_id': 9, 'green_state': 'Green',
                  'vehicle_body_vertices_m': body(0, y),
                  'route_source': 'Native CARLA connected waypoints'}
                 for index, y in enumerate((-2, -1, 0))]
        files['traffic-entry.jsonl'] = ''.join(json.dumps(row) + '\n'
                                               for row in entry)
        names.append('traffic-entry.jsonl')
    files['acquisition.json'] = json.dumps({name: {
        'kind': 'original_native', 'sha256': sha(files[name])} for name in names},
        sort_keys=True) + '\n'
    files['fixture-provenance.json'] = json.dumps({
        'scope': 'CPU software diagnostic with synthetic Native-shaped source text and media',
        'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
        'case_specific_sources': names}) + '\n'
    path = ROOT / ('diagnostic-' + suffix + '.json')
    path.write_text(json.dumps(fixture, ensure_ascii=False,
                               separators=(',', ':')) + '\n')
    source = str(path.relative_to(REPO))
    assignment = REPO / 'inputs' / ROOT.name / 'assignment.json'
    recipe = {'format': 'worker-fixture-recipe',
        'sources': [{'path': 'diagnostic-input.json',
            'source': str(assignment.relative_to(REPO)),
            'sha256': hashlib.sha256(assignment.read_bytes()).hexdigest()}],
        'generator': {'source': source,
                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}
    recipe_path = ROOT / ('diagnostic-' + suffix + '-recipe.json')
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')


if __name__ == '__main__':
    for case in ('crosswalk_clear_turn', 'crosswalk_occupied_yield',
                 'lawful_traffic_yield'):
        write_case(case)
