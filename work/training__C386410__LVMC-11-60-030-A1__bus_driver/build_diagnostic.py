"""Text-only source-shaped diagnostics for exact two-location constructions."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from geometry import open_drive

BASE = REPO / 'work/training__C393261__LVMC-11-60-030-A5__bus_driver/cases/probe_01/diagnostic.json'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def dumps(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False)


def lines(values):
    return '\n'.join(map(dumps, values)) + '\n'


def hash_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def update_position(obj, x, speed):
    if isinstance(obj, dict):
        if isinstance(obj.get('position_m'), list) and len(obj['position_m']) >= 2:
            obj['position_m'][0] = x
        if isinstance(obj.get('position'), dict) and 'x' in obj['position']:
            obj['position']['x'] = x
        if isinstance(obj.get('vertex'), list) and len(obj['vertex']) >= 2:
            obj['vertex'][0] = x
        if isinstance(obj.get('threedbbox'), list):
            for index, point in enumerate(obj['threedbbox']):
                point[0] = x + (-4 if index < 4 else 4)
        if isinstance(obj.get('body_vertices_m'), list):
            for index, point in enumerate(obj['body_vertices_m']):
                point[0] = x + (-4 if index < 4 else 4)
        if isinstance(obj.get('road_projection'), dict):
            obj['road_projection']['s_m'] = 100 + x
        if 'speed_mps' in obj:
            obj['speed_mps'] = speed
        if 'speed_mph' in obj:
            obj['speed_mph'] = speed / .44704
        if 'velocity_mps' in obj:
            obj['velocity_mps'] = [speed, 0, 0]
        for value in obj.values():
            if isinstance(value, (dict, list)):
                update_position(value, x, speed)
    elif isinstance(obj, list):
        for value in obj:
            if isinstance(value, (dict, list)):
                update_position(value, x, speed)


def build():
    base = json.loads(BASE.read_text())
    for suffix, zone_kind, target in (
            ('designated_terminus', 'route_destination', 5.0),
            ('undesignated_street', 'other_street', 40.0)):
        spec = json.loads(json.dumps(base))
        files = spec['files']
        road = open_drive() + '\n'
        files['road.xodr'] = road
        zone_id = ('route-destination-R1' if zone_kind == 'route_destination'
                   else 'other-street-R1')
        zone = {'kind': zone_kind, 'id': zone_id, 'route_id': 'R1'}
        if zone_kind != 'other_street':
            zone['designation_source'] = {'path': 'road.xodr', 'sha256': hash_text(road)}
        context = {'vehicle_class': 'route_bus_non_tour', 'vehicle_class_verified': False,
                   'route_id': 'R1', 'route_assignment_verified': False,
                   'street_id': 'native-road-1', 'street_status_verified': False,
                   'controller_policy': 'approach_then_stationary_brake_v1',
                   'weather_policy': 'ClearNoon',
                   'capture_profile': {'rate_hz': 20, 'frames': 600,
                     'cameras': {'overview': [1920, 1080], 'approach': [1280, 720],
                                 'reference_corner': [1280, 720], 'driver_reference': [1280, 720]}},
                   'zone': zone, 'official_designation_verified': False,
                   'route_designation_source': {'candidate_reference': zone.get('designation_source'),
                                                'official_authority_verified': False},
                   'driver_presence_verified': False,
                   'native_lane_readback': [{'requested_x_m': target, 'road_id': 1,
                                            'lane_id': -2, 'native_xy_m': [target, -5.25]}]}
        files['bus-context.json'] = dumps(context) + '\n'
        files.pop('terminus-context.json', None)
        files.pop('terminus-review.json', None)
        old = [json.loads(s) for s in files.pop('terminus-history.jsonl').splitlines()]
        history = []
        for i, row in enumerate(old):
            x = target - 20 + min(i, 100) * .2
            speed = 4.0 if i < 100 else 0.0
            history.append({'video_frame': i, 'native_frame': row['native_frame'],
                'time_s': row['time_s'], 'bus_speed_mps': speed,
                'parking_brake_applied': i >= 100, 'driver_present': True,
                'driver_presence_source': 'synthetic_diagnostic_controller',
                'occupied_zone_id': zone_id if x >= target - 5 else 'outside',
                'position_xyz_m': [x, -5.25, 1.0], 'actor_id': 1,
                'blueprint_id': 'vehicle.mitsubishi.fusorosa'})
        files['bus-history.jsonl'] = lines(history)
        for name in ('trace.jsonl', 'capture/evidence.jsonl'):
            data = [json.loads(s) for s in files[name].splitlines()]
            for i, row in enumerate(data):
                x = target - 20 + min(i, 100) * .2
                speed = 4.0 if i < 100 else 0.0
                update_position(row, x, speed)
            files[name] = lines(data)
        for i, graph in enumerate(spec['graphs']):
            x = target - 20 + min(i, 100) * .2
            update_position(graph, x, 4.0 if i < 100 else 0.0)
            graph['attributes']['source'] = 'C386410 bus standing software diagnostic'
        manifest = json.loads(files['capture/manifest.json'])
        manifest['sources'] = {'trace.jsonl': hash_text(files['trace.jsonl']),
                               'road.xodr': hash_text(road)}
        files['capture/manifest.json'] = dumps(manifest) + '\n'
        path = ROOT / 'cases' / suffix / 'diagnostic.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(spec, separators=(',', ':'), ensure_ascii=False) + '\n')
        source = str(path.relative_to(REPO))
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json', 'source': source,
                               'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}],
                  'generator': {'source': source, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}
        (path.parent / 'recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')


if __name__ == '__main__':
    build()
