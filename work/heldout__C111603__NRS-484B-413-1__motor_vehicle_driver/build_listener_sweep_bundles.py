"""Author exact route-relative listener variants without altering proven cases.

These standalone manifests are draft exact constructions until their fallback,
saved-processing, comparison and delivery proof chains are complete.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = HERE.name + '__ped_horn_audio'
BASE = json.loads((HERE / 'ped-horn-manifest.json').read_text())
CONSTRUCTION = json.loads((HERE / 'ped-horn-construction.json').read_text())
DIAGNOSTIC = json.loads((HERE / 'ped-horn-diagnostic.json').read_text())
CONTRACT = json.loads((HERE / 'ped-horn-measurement-contract.json').read_text())
LOCATION = 'ped_location = scene[\'approach\'][0].transform.location + carla.Location(x=6, y=2, z=.5)'


def save(path, value, compact=False):
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2, allow_nan=False) + '\n')


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


for index, offset in enumerate((2, 4, 6)):
    case = HERE.name + f'__ped_horn_listener_{offset}m'
    prefix = f'listener-{offset}m'
    construction = deepcopy(CONSTRUCTION)
    construction['case_id'] = case
    for item in construction['files']:
        content = item['content'].replace(OLD, case)
        if item['path'] == 'runner.py':
            if content.count(LOCATION) != 1:
                raise ValueError('Pedestrian spawn source changed')
            content = content.replace('from turn_native_route import select_left_turn, route_targets, control_step',
                                      'from turn_native_route import select_left_turn, route_targets, control_step\nfrom listener_sweep_placement import spawnable_listener_points')
            placement = (
                "route = [scene['approach'][-2], scene['approach'][-1], scene['junction'], scene['exit']]\n"
                "        route_xy = [(wp.transform.location.x, wp.transform.location.y) for wp in route]\n"
                f"        listener_waypoint = spawnable_listener_points(world.get_map(), carla, route_xy)[{index}]\n"
                "        ped_location = carla.Location(x=listener_waypoint['spawn_x_m'], "
                "y=listener_waypoint['spawn_y_m'], z=listener_waypoint['spawn_z_m'])")
            content = content.replace(LOCATION, placement)
            content = content.replace("'listener_position_source': 'original Native pedestrian transform',",
                                      "'listener_position_source': 'original Native pedestrian transform and route-relative sidewalk waypoint',\n"
                                      f"            'listener_requested_route_offset_m': {offset},\n"
                                      "            'listener_sidewalk_road_id': listener_waypoint['road_id'],\n"
                                      "            'listener_sidewalk_lane_id': listener_waypoint['lane_id'],")
        item['content'] = content
    construction['files'].append({'path': 'listener_sweep_placement.py',
                                  'content': (HERE / 'listener_sweep_placement.py').read_text()})
    construction_path = HERE / f'{prefix}-construction.json'
    save(construction_path, construction)
    contract = deepcopy(CONTRACT)
    contract['case_id'] = case
    save(HERE / f'{prefix}-measurement-contract.json', contract)
    diagnostic = deepcopy(DIAGNOSTIC)
    participants = [json.loads(line) for line in diagnostic['files']['participant_bodies.jsonl'].splitlines()]
    for row in participants:
        row['bodies']['ped_listener']['x_m'] = 0
        row['bodies']['ped_listener']['y_m'] = offset
    diagnostic['files']['participant_bodies.jsonl'] = ''.join(json.dumps(row) + '\n' for row in participants)
    provenance = json.loads(diagnostic['files']['turn_fixture_provenance.json'])
    provenance['case_id'] = case
    provenance['source'] = f'C111603 synthetic route-relative {offset} m listener point'
    diagnostic['files']['turn_fixture_provenance.json'] = json.dumps(provenance) + '\n'
    save(HERE / f'{prefix}-diagnostic.json', diagnostic, compact=True)
    diagnostic_path = HERE / f'{prefix}-diagnostic.json'
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json',
                           'source': str(diagnostic_path.relative_to(ROOT)),
                           'sha256': digest(diagnostic_path)}],
              'generator': {'source': str(diagnostic_path.relative_to(ROOT)),
                            'sha256': digest(diagnostic_path)}}
    save(HERE / f'{prefix}-recipe.json', recipe)
    manifest = deepcopy(BASE)
    entry = manifest['cases'][0]
    for key in ('candidates', 'offline', 'compatibility', 'saved_processing',
                'post_capture', 'delivery_acceptance'):
        entry.pop(key, None)
    entry['case_id'] = case
    entry['construction'] = construction_path.name
    entry['construction_sha256'] = digest(construction_path)
    entry['measurement_contract'] = f'{prefix}-measurement-contract.json'
    entry['fixture_recipe'] = str((HERE / f'{prefix}-recipe.json').relative_to(ROOT))
    entry['candidate_risk']['reason'] = (
        f'Route-relative {offset} m listener sidewalk may be absent or physically unsuitable; '
        'audio and affected status require original-source review')
    save(HERE / f'{prefix}-manifest.json', manifest)
    print(case, digest(construction_path))
