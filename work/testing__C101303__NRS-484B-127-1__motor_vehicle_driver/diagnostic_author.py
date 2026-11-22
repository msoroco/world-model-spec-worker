"""Source-hashed sparse CPU diagnostics; never physical following evidence."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def body(x):
    return [[x-1,-1,0],[x-1,1,0],[x+1,-1,0],[x+1,1,0]]


def write_case(case):
    fixture = json.loads((REPO/'runtime/fixtures/example.json').read_text())
    files = fixture['files']
    mapping = [json.loads(line) for line in files['video_frames.jsonl'].splitlines() if line]
    suffix = case['case_id'].removeprefix(ROOT.name+'__')
    setup = case['world_setup']
    context = {'case_id': case['case_id'], 'rate_hz': 20, 'duration_s': 45,
               'map_source': 'diagnostic Native-shaped connected map',
               'route_source': 'Native CARLA connected waypoints',
               'common_following_route_xy_m': [[0,0],[100,0]],
               'condition_source': 'original weather and road context',
               'road_id': 12, 'following_lane_id': -1, 'target_lane_id': -2,
               'hill_crest': {'source_ref': 'Native CARLA map waypoint elevation',
                              'crest_station_m': 11},
               'camera_profile': 'overview1080-capability',
               'diagnostic_only': True}
    files['following-context.json'] = json.dumps(context, sort_keys=True)+'\n'
    logical = [14,17,19,20,21,21.05,21.10,21.15,21.20]
    history = []
    for i, (frame, diagnostic_time) in enumerate(zip(mapping, logical)):
        ego_x = 10+i
        leader_x = ego_x+setup['target_body_gap_m']+2
        change = diagnostic_time > 20
        condition = {'source_ref': 'original weather and road context',
                     'native_fog_density': 0,
                     'native_precipitation_strength': setup['precipitation_percent'],
                     'observed_tire_friction': 2.0}
        history.append({'frame': frame['carla_frame'], 'time_s': frame['time_s'],
            'diagnostic_time_s': diagnostic_time,
            'ego': {'actor_id': 1, 'source_ref': 'Native CARLA actor transform and bounding box',
                    'body_vertices_m': body(ego_x),
                    'speed_mps': setup['ego_target_speed_mps']},
            'leader': {'actor_id': 2, 'source_ref': 'Native CARLA actor transform and bounding box',
                       'body_vertices_m': body(leader_x),
                       'speed_mps': setup['leader_target_speed_mps']},
            'surrounding_vehicle_count': setup['surrounding_vehicle_count'],
            'traffic_actor_ids': list(range(3,3+setup['surrounding_vehicle_count']-1)),
            'traffic_source': 'Native CARLA actor inventory',
            'highway_condition': condition,
            'lane_change': {'source_ref': 'Native lane waypoint and route',
                            'ego_road_id': 12, 'leader_road_id': 12,
                            'ego_lane_id': -2 if change else -1,
                            'leader_lane_id': -1, 'started': change}})
    files['following-history.jsonl'] = ''.join(json.dumps(row, sort_keys=True)+'\n'
                                               for row in history)
    names = ['following-history.jsonl', 'following-context.json',
             'video_frames.jsonl']
    files['acquisition.json'] = json.dumps({name: {'kind': 'original_native',
        'sha256': digest(files[name])} for name in names},sort_keys=True)+'\n'
    files['fixture-provenance.json'] = json.dumps({
        'scope': 'CPU software diagnostic with sparse logical following window, original 9-frame media shape',
        'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
        'diagnostic_window_remap': 'sparse_source_shape_only',
        'case_specific_sources': names}, sort_keys=True)+'\n'
    path = ROOT/('diagnostic-'+suffix+'.json')
    path.write_text(json.dumps(fixture,ensure_ascii=False,separators=(',',':'))+'\n')
    assignment = REPO/'inputs'/ROOT.name/'assignment.json'
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json',
                  'source': str(assignment.relative_to(REPO)),
                  'sha256': sha(assignment)}],
              'generator': {'source': str(path.relative_to(REPO)),
                            'sha256': sha(path)}}
    (ROOT/('diagnostic-'+suffix+'-recipe.json')).write_text(
        json.dumps(recipe,indent=2)+'\n')


if __name__ == '__main__':
    plan = json.loads((ROOT/'case-plan.json').read_text())
    for case in plan['cases']:
        write_case(case)
    print(json.dumps({'diagnostic_recipes': len(plan['cases'])}))
