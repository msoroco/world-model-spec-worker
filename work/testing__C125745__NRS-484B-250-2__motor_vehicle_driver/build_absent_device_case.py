"""Build an exact CPU case for an entrance with no Native control device.

The source packet is a synthetic candidate. No official-status or physical
absence claim follows from the CPU construction.
"""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__stop_ego_left_near_time_no_device'


def emit(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def variant(name, edits):
    value = (HERE / name).read_text()
    for old, new in edits:
        if value.count(old) != 1:
            raise ValueError('Expected one occurrence in ' + name + ': ' + old)
        value = value.replace(old, new)
    path = HERE / ('absent-' + name)
    path.write_text(value)
    return path


def diagnostic(site_path):
    data = json.loads((HERE / 'diagnostic.json').read_text())
    context = json.loads(data['files']['junction_context.json'])
    context['native_stop_sign_id'] = None
    context['entrance_device_presence'] = 'absent'
    data['files']['junction_context.json'] = json.dumps(context, allow_nan=False) + '\n'
    entries = [json.loads(line) for line in data['files']['crossing_history.jsonl'].splitlines()]
    for entry in entries:
        entry['governing_stop_sign_id'] = None
        entry['entrance_device_presence'] = 'absent'
    data['files']['crossing_history.jsonl'] = ''.join(
        json.dumps(entry, allow_nan=False) + '\n' for entry in entries)
    capture = json.loads(data['files']['capture/manifest.json'])
    capture['case_id'] = CASE
    data['files']['capture/manifest.json'] = json.dumps(capture, indent=2) + '\n'
    for graph in data['graphs']:
        graph['attributes']['case_id'] = CASE
    path = HERE / 'absent-diagnostic.json'
    emit(path, data)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'site-source.json',
                           'source': str(site_path.relative_to(ROOT)),
                           'sha256': sha(site_path)}],
              'generator': {'source': str(path.relative_to(ROOT)),
                            'sha256': sha(path)}}
    recipe_path = HERE / 'absent-diagnostic-recipe.json'
    emit(recipe_path, recipe)
    return recipe_path


def build():
    scene = json.loads((HERE / 'site.json').read_text())
    scene['stop_sign'] = None
    scene['expected_entrance_device'] = 'absent'
    source_paths = {}
    for role in ('sign_governance_source', 'sign_face_video_source'):
        source = json.loads((HERE / scene['source_documents'][role]['path']).read_text())
        source['review_basis'] = ('Synthetic absent-device construction for CPU '
                                  'compatibility; Native and official status unverified')
        source['reviewed_site_fields']['stop_sign'] = None
        path = HERE / 'absent-review' / (role + '.json')
        emit(path, source)
        scene['source_documents'][role]['sha256'] = sha(path)
        source_paths['review/' + role + '.json'] = path
    site = HERE / 'absent-site.json'
    emit(site, scene)
    config = json.loads((HERE / 'config.json').read_text())
    config['selected_case_id'] = CASE
    config['site_packet'] = {'path': 'site.json', 'sha256': sha(site)}
    config_path = HERE / 'absent-config.json'
    emit(config_path, config)

    control = variant('median_route_control.py', [
        ('if sign.get("governed_lane_id") != ego["lane_id"] or not sign.get("native_id"):',
         'if sign is not None or scene.get("expected_entrance_device") != "absent":'),
        ('Stop sign must govern the ego entrance',
         'Absent-device case needs a sourced empty ego entrance')])
    pair = variant('native_pair.py', [
        ('from stop_sign_control import find_governing_stop_sign',
         'from device_branch import entrance_devices, check_entrance_device_expectation'),
        ("    sign = find_governing_stop_sign(world, ego_approach_waypoint)\n"
         "    if sign.id != scene['stop_sign']['native_id']:\n"
         "        raise ValueError('Governing Native stop sign ID differs from reviewed scene')",
         "    devices = entrance_devices(world, ego_approach_waypoint)\n"
         "    check_entrance_device_expectation(devices, 'absent')\n"
         "    sign = None")])
    capture = variant('capture_sources.py', [
        ("    if sign.id!=scene['stop_sign']['native_id']:\n"
         "        raise ValueError('Governing Native stop sign changed')",
         "    if sign is not None or scene.get('expected_entrance_device')!='absent':\n"
         "        raise ValueError('Absent Native entrance changed')"),
        ("'governing_stop_sign_id':sign.id,",
         "'governing_stop_sign_id':None,'entrance_device_presence':'absent',")])
    runner = variant('runner.py', [
        ("'stop_ego_left_separated','stop_opposite_left_turn')}",
         "'stop_ego_left_separated','stop_opposite_left_turn',\n    'stop_ego_left_near_time_no_device')}"),
        ("'native_stop_sign_id':scene['stop_sign']['native_id'],",
         "'native_stop_sign_id':None,'entrance_device_presence':'absent',")])
    analyzer = variant('simultaneous_entries.py', [
        ('if ctx.get(key) is None:raise ValueError("Missing sourced crossing context: "+key)',
         'if ctx.get(key) is None and key!="native_stop_sign_id":raise ValueError("Missing sourced crossing context: "+key)'),
        ('if row.get("governing_stop_sign_id")!=ctx["native_stop_sign_id"]:',
         'if ("governing_stop_sign_id" not in row or row.get("governing_stop_sign_id") is not None or\n'
         '                row.get("entrance_device_presence")!="absent" or\n'
         '                ctx.get("entrance_device_presence")!="absent"):'),
        ('Governing Native stop sign identity mismatch',
         'Native absent-device entrance identity mismatch')])
    finalizer = variant('finalizer.py', [
        ("'native_stop_sign_id': context['native_stop_sign_id'],",
         "'native_stop_sign_id': context['native_stop_sign_id'],\n            'entrance_device_presence': context['entrance_device_presence'],")])
    construction = json.loads((HERE / 'construction.json').read_text())
    construction['case_id'] = CASE
    construction['case_design'] = {
        'changed_device_presence': 'absent Native device actor at the ego entrance',
        'fixed_crossing_and_routes': True,
        'official_device_judgment': 'unresolved',
        'physical_acceptance_claimed': False}
    sources = {'site.json': site, 'config.json': config_path,
               'runner.py': runner, 'native_pair.py': pair,
               'median_route_control.py': control,
               'capture_sources.py': capture,
               'simultaneous_entries.py': analyzer,
               'finalizer.py': finalizer,
               'device_branch.py': HERE / 'device_branch.py',
               **source_paths}
    for item in construction['files']:
        path = sources.get(item['path'])
        if path is not None:
            item['source'] = str(path.relative_to(ROOT))
            item['content'] = path.read_text()
        elif item['path'] == 'tests/test_bundle.py':
            item['content'] = item['content'].replace(
                HERE.name + '__stop_ego_left_near_time', CASE)
    construction['files'].append({
        'path': 'device_branch.py',
        'source': str((HERE / 'device_branch.py').relative_to(ROOT)),
        'content': (HERE / 'device_branch.py').read_text()})
    construction_path = HERE / 'absent-construction.json'
    emit(construction_path, construction)
    recipe = diagnostic(site)
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    manifest['cases'] = [entry for entry in manifest['cases']
                         if entry['case_id'] != CASE]
    manifest['cases'].append({
        'case_id': CASE, 'kind': 'delivery',
        'construction': construction_path.name,
        'construction_sha256': sha(construction_path),
        'physical_risk': {'status': 'physical',
                          'reason': 'Native entrance may still contain a baked traffic device'},
        'candidates': [], 'measurement_contract': 'measurement-contract.json',
        'measurement_procedure': {'entrypoint': 'finalizer.py'},
        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                           'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
        'fixture_recipe': str(recipe.relative_to(ROOT))})
    path = HERE / 'absent-execution-manifest.json'
    emit(path, manifest)
    return {'case_id': CASE, 'construction_sha256': sha(construction_path),
            'manifest': path.name, 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
