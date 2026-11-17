"""Build the opposite-direction left-turn stop-sign CPU case and sources."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__stop_opposite_left_turn'


def emit(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows)


def body(cx, cy):
    return [[cx - 1, cy - 1], [cx - 1, cy + 1],
            [cx + 1, cy + 1], [cx + 1, cy - 1]]


def build():
    site = copy.deepcopy(json.loads((HERE / 'site.json').read_text()))
    site['approach_relation'] = 'opposite_directions'
    site['other_left_turn_intended'] = True
    other = site['approaches']['other']
    other.update(highway_id='EW', road_id=1, lane_id='westbound',
                 forward_xy=[-1, 0], route_xy_m=[[30, 0], [15, 0], [15, -15]],
                 spawn_pose=[30, 0, 0, 180])
    site_path = HERE / 'fourth-site.json'
    emit(site_path, site)
    config = copy.deepcopy(json.loads((HERE / 'config.json').read_text()))
    config['selected_case_id'] = CASE
    config['site_packet'] = {'path': 'site.json', 'sha256': sha(site_path)}
    config_path = HERE / 'fourth-config.json'
    emit(config_path, config)
    construction = copy.deepcopy(json.loads((HERE / 'construction.json').read_text()))
    construction['case_id'] = CASE
    construction['case_design'] = {'changed_relation': 'opposite-direction approach with other left turn',
                                   'turn_intent_source': 'controller_history.jsonl',
                                   'exception_judgment': 'unresolved',
                                   'physical_acceptance_claimed': False}
    for file in construction['files']:
        if file['path'] == 'config.json':
            file['source'] = str(config_path.relative_to(ROOT))
            file['content'] = config_path.read_text()
        elif file['path'] == 'site.json':
            file['source'] = str(site_path.relative_to(ROOT))
            file['content'] = site_path.read_text()
        elif file['path'] == 'tests/test_bundle.py':
            file['content'] = file['content'].replace(HERE.name + '__stop_ego_left_near_time', CASE)
    construction_path = HERE / 'fourth-construction.json'
    emit(construction_path, construction)

    spec = copy.deepcopy(json.loads((HERE / 'diagnostic.json').read_text()))
    files = spec['files']
    context = json.loads(files['junction_context.json'])
    context.update(other_highway_id='EW', other_road_id=1,
                   other_approach_forward_xy=[-1, 0],
                   approach_relation='opposite_directions',
                   turn_intent_source='controller_history.jsonl')
    files['junction_context.json'] = json.dumps(context, allow_nan=False) + '\n'
    crossing = [json.loads(row) for row in files['crossing_history.jsonl'].splitlines()]
    centers = [(30, 0), (18, 0), (15, 0)]
    for row, center in zip(crossing, centers):
        row['other']['road_id'] = 1
        row['other']['body_vertices_xy_m'] = body(*center)
        row['other_left_turn_intended'] = True
    files['crossing_history.jsonl'] = lines(crossing)
    controls = [json.loads(row) for row in files['controller_history.jsonl'].splitlines()]
    for row in controls:
        row['other_left_turn_intended'] = True
    files['controller_history.jsonl'] = lines(controls)
    evidence = [json.loads(row) for row in files['capture/evidence.jsonl'].splitlines()]
    for item, center in zip(evidence, centers):
        other_actor = item['original_observations']['participants'][1]
        other_actor['heading_deg'] = 180
        other_actor['position_m'][:2] = center
        other_actor['body_vertices_m'] = [[x, y, z] for x, y in body(*center)
                                          for z in (0, 1.5)]
    files['capture/evidence.jsonl'] = lines(evidence)
    for graph in spec['graphs']:
        frame = graph['attributes']['frame']
        other_actor = graph['attributes']['observed_evidence']['participants'][1]
        center = centers[frame - 100]
        other_actor['heading_deg'] = 180
        other_actor['position_m'][:2] = center
        other_actor['body_vertices_m'] = [[x, y, z] for x, y in body(*center)
                                          for z in (0, 1.5)]
    capture_manifest = json.loads(files['capture/manifest.json'])
    capture_manifest['case_id'] = CASE
    files['capture/manifest.json'] = json.dumps(capture_manifest, indent=2, allow_nan=False) + '\n'
    diagnostic_path = HERE / 'fourth-diagnostic.json'
    emit(diagnostic_path, spec)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'site-source.json', 'source': str(site_path.relative_to(ROOT)),
                           'sha256': sha(site_path)}],
              'generator': {'source': str(diagnostic_path.relative_to(ROOT)),
                            'sha256': sha(diagnostic_path)}}
    emit(HERE / 'fourth-diagnostic-recipe.json', recipe)

    manifest_path = HERE / 'execution-manifest.json'
    execution = json.loads(manifest_path.read_text())
    fourth = {'case_id': CASE, 'kind': 'delivery', 'construction': construction_path.name,
              'construction_sha256': sha(construction_path),
              'physical_risk': {'status': 'physical',
                                'reason': 'Median opening may not support safe opposite-direction left turn'},
              'candidates': [], 'measurement_contract': 'measurement-contract.json',
              'measurement_procedure': {'entrypoint': 'finalizer.py'},
              'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST',
                                 'port_env_var': 'CARLA_PORT'},
              'fixture_recipe': str((HERE / 'fourth-diagnostic-recipe.json').relative_to(ROOT))}
    execution['cases'] = [entry for entry in execution['cases'] if entry['case_id'] != CASE] + [fourth]
    emit(manifest_path, execution)
    return {'case_id': CASE, 'construction_sha256': fourth['construction_sha256'],
            'diagnostic_sha256': recipe['generator']['sha256']}


def build_turn_sweep_point(output, turn):
    """Build one opposite-approach route probe for CPU offline construction.

    These probes share the same crossing, sign, spawns, cameras and release frame.
    They do not establish that a Native actor realized a turn or a legal exception.
    """
    if turn not in ('left', 'straight', 'right'):
        raise ValueError('Turn probe must be left, straight or right')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    site = json.loads((HERE / 'fourth-site.json').read_text())
    routes = {'left': [[30, 0], [15, 0], [15, -15]],
              'straight': [[30, 0], [15, 0], [-15, 0]],
              'right': [[30, 0], [15, 0], [15, 15]]}
    site['approaches']['other']['route_xy_m'] = routes[turn]
    site['other_left_turn_intended'] = turn == 'left'
    site_path = output / 'site.json'
    emit(site_path, site)
    config = json.loads((HERE / 'fourth-config.json').read_text())
    config['site_packet'] = {'path': 'site.json', 'sha256': sha(site_path)}
    config_path = output / 'config.json'
    emit(config_path, config)
    construction = json.loads((HERE / 'fourth-construction.json').read_text())
    construction['sweep_point'] = {
        'sweep_id': 'c125745-4', 'axis': 'commanded_turn_path',
        'commanded_value': turn, 'unit': 'route waypoints',
        'scope': 'CPU offline construction; realized turn and legal judgment unresolved'}
    for item in construction['files']:
        if item['path'] == 'site.json':
            item['content'] = site_path.read_text()
            item.pop('source', None)
        elif item['path'] == 'config.json':
            item['content'] = config_path.read_text()
            item.pop('source', None)
    construction_path = output / 'construction.json'
    emit(construction_path, construction)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'cases': [{'case_id': CASE, 'construction': 'construction.json',
                           'construction_sha256': sha(construction_path)}]}
    emit(output / 'execution-manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
