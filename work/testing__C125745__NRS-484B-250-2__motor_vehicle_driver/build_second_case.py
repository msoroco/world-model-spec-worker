"""Build a synthetic exact ego-right stop-sign case and diagnostic sources."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__stop_ego_right_near_time'


def emit(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows)


def build():
    site = copy.deepcopy(json.loads((HERE / 'site.json').read_text()))
    other = site['approaches']['other']
    other['lane_id'] = 'southbound'
    other['forward_xy'] = [0, -1]
    other['route_xy_m'] = [[15, 15], [15, 0], [15, -15]]
    other['spawn_pose'] = [15, 15, 0, -90]
    site_path = HERE / 'second-site.json'
    emit(site_path, site)

    config = copy.deepcopy(json.loads((HERE / 'config.json').read_text()))
    config['selected_case_id'] = CASE
    config['site_packet'] = {'path': 'site.json', 'sha256': sha(site_path)}
    config_path = HERE / 'second-config.json'
    emit(config_path, config)

    construction = copy.deepcopy(json.loads((HERE / 'construction.json').read_text()))
    construction['case_id'] = CASE
    construction['case_design'] = {'changed_relation': 'ego spatially right of the other original approach',
                                   'retained': 'same synthetic crossing, stop-sign identity, actor classes and close-entry timing method',
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
    construction_path = HERE / 'second-construction.json'
    emit(construction_path, construction)

    spec = copy.deepcopy(json.loads((HERE / 'diagnostic.json').read_text()))
    files = spec['files']
    context = json.loads(files['junction_context.json'])
    context['other_approach_forward_xy'] = [0, -1]
    files['junction_context.json'] = json.dumps(context, allow_nan=False) + '\n'
    crossing = [json.loads(row) for row in files['crossing_history.jsonl'].splitlines()]
    first = crossing[0]['other']['body_vertices_xy_m']
    crossing[0]['other']['body_vertices_xy_m'] = [[x, y + 20] for x, y in first]
    files['crossing_history.jsonl'] = lines(crossing)
    manifest = json.loads(files['capture/manifest.json'])
    manifest['case_id'] = CASE
    files['capture/manifest.json'] = json.dumps(manifest, indent=2, allow_nan=False) + '\n'
    for graph in spec['graphs']:
        observations = graph['attributes']['observed_evidence']
        other_participant = observations['participants'][1]
        other_participant['heading_deg'] = -90
        if observations['frame'] == crossing[0]['frame']:
            other_participant['position_m'][1] += 20
            other_participant['body_vertices_m'] = [[x, y + 20, z]
                                                    for x, y, z in other_participant['body_vertices_m']]
    evidence = [json.loads(row) for row in files['capture/evidence.jsonl'].splitlines()]
    for row in evidence:
        other_participant = row['original_observations']['participants'][1]
        other_participant['heading_deg'] = -90
        if row['original_frame'] == crossing[0]['frame']:
            other_participant['position_m'][1] += 20
            other_participant['body_vertices_m'] = [[x, y + 20, z]
                                                    for x, y, z in other_participant['body_vertices_m']]
    files['capture/evidence.jsonl'] = lines(evidence)
    diagnostic_path = HERE / 'second-diagnostic.json'
    emit(diagnostic_path, spec)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'site-source.json', 'source': str(site_path.relative_to(ROOT)),
                           'sha256': sha(site_path)}],
              'generator': {'source': str(diagnostic_path.relative_to(ROOT)),
                            'sha256': sha(diagnostic_path)}}
    emit(HERE / 'second-diagnostic-recipe.json', recipe)

    manifest_path = HERE / 'execution-manifest.json'
    execution = json.loads(manifest_path.read_text())
    second = {'case_id': CASE, 'kind': 'delivery',
              'construction': construction_path.name,
              'construction_sha256': sha(construction_path),
              'physical_risk': {'status': 'physical',
                                'reason': 'Changing the other approach may alter the fixed crossing or sign conditions'},
              'candidates': [], 'measurement_contract': 'measurement-contract.json',
              'measurement_procedure': {'entrypoint': 'finalizer.py'},
              'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST',
                                 'port_env_var': 'CARLA_PORT'},
              'fixture_recipe': str((HERE / 'second-diagnostic-recipe.json').relative_to(ROOT))}
    execution['cases'] = [entry for entry in execution['cases'] if entry['case_id'] != CASE] + [second]
    emit(manifest_path, execution)
    return {'case_id': CASE, 'construction_sha256': second['construction_sha256'],
            'diagnostic_sha256': recipe['generator']['sha256']}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
