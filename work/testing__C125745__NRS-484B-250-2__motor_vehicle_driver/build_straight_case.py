"""Build an exact opposite-approach straight-intent CPU construction.

This adds an independent case without altering the hash-bound left-turn case.
The case remains a candidate until its saved-source and comparison proofs pass.
"""
import copy
import hashlib
import json
from pathlib import Path

from turn_branch import validate_turn_pair

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__stop_opposite_straight'


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(value, old, new):
    if value.count(old) != 1:
        raise ValueError('Expected one source occurrence: ' + old)
    return value.replace(old, new)


def variant(name, replacements):
    value = (HERE / name).read_text()
    for old, new in replacements:
        value = replace_once(value, old, new)
    output = HERE / ('straight-' + name)
    output.write_text(value)
    return output


def rows(value):
    return [json.loads(line) for line in value.splitlines() if line.strip()]


def row_text(values):
    return ''.join(json.dumps(value, allow_nan=False) + '\n' for value in values)


def diagnostic(site_path):
    data = json.loads((HERE / 'fourth-diagnostic.json').read_text())
    for name in ('crossing_history.jsonl', 'controller_history.jsonl'):
        entries = rows(data['files'][name])
        for entry in entries:
            entry['other_left_turn_intended'] = False
        data['files'][name] = row_text(entries)
    context = json.loads(data['files']['junction_context.json'])
    context['other_left_turn_intended'] = False
    data['files']['junction_context.json'] = json.dumps(context, allow_nan=False) + '\n'
    capture = json.loads(data['files']['capture/manifest.json'])
    capture['case_id'] = CASE
    data['files']['capture/manifest.json'] = json.dumps(capture, indent=2) + '\n'
    for graph in data['graphs']:
        graph['attributes']['case_id'] = CASE
    path = HERE / 'straight-diagnostic.json'
    write_json(path, data)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'site-source.json',
                           'source': str(site_path.relative_to(ROOT)),
                           'sha256': sha(site_path)}],
              'generator': {'source': str(path.relative_to(ROOT)),
                            'sha256': sha(path)}}
    recipe_path = HERE / 'straight-diagnostic-recipe.json'
    write_json(recipe_path, recipe)
    return recipe_path


def build():
    left = json.loads((HERE / 'fourth-site.json').read_text())
    straight = copy.deepcopy(left)
    straight['other_left_turn_intended'] = False
    straight['approaches']['other']['route_xy_m'][-1] = [-15, 0]
    comparison = validate_turn_pair(left, straight)
    site = HERE / 'straight-site.json'
    write_json(site, straight)
    config = json.loads((HERE / 'fourth-config.json').read_text())
    config['selected_case_id'] = CASE
    config['site_packet'] = {'path': 'site.json', 'sha256': sha(site)}
    config_path = HERE / 'straight-config.json'
    write_json(config_path, config)

    control = variant('median_route_control.py', [
        ('or not scene.get("other_left_turn_intended")',
         'or scene.get("other_left_turn_intended") is not False'),
        ('Opposite headings and sourced left-turn intention required',
         'Opposite headings and sourced straight intention required'),
        ('    stop = _xy(scene["ego_stop_line_xy_m"], "stop line")',
         '    other_route = [_xy(p, "other route") for p in other["route_xy_m"]]\n'
         '    ox, oy = _xy(other["forward_xy"], "other forward")\n'
         '    direction = math.hypot(ox, oy)\n'
         '    span = (other_route[-1][0] - other_route[0][0],\n'
         '            other_route[-1][1] - other_route[0][1])\n'
         '    longitudinal = (ox * span[0] + oy * span[1]) / direction\n'
         '    lateral = (ox * span[1] - oy * span[0]) / direction\n'
         '    if longitudinal <= 1 or abs(lateral) > 1:\n'
         '        raise ValueError("Commanded straight exit required")\n'
         '    stop = _xy(scene["ego_stop_line_xy_m"], "stop line")')])
    # Keep imported names local to the construction; every case gets its own
    # source bytes, while the embedded module filenames remain conventional.
    capture = variant('capture_sources.py', [
        ('other_left_turn_intended is not True',
         'other_left_turn_intended is not scene.get("other_left_turn_intended")'),
        ('Original left-turn intention required',
         'Original selected turn intention required')])
    runner = variant('runner.py', [
        ("'stop_ego_left_separated','stop_opposite_left_turn')}",
         "'stop_ego_left_separated','stop_opposite_left_turn',\n    'stop_opposite_straight')}"),
        ("scene['approach_relation']=='opposite_directions')\n",
         "scene['other_left_turn_intended'])\n"),
        ("'other_left_turn_intended':scene['approach_relation']=='opposite_directions',",
         "'other_left_turn_intended':scene['other_left_turn_intended'],")])
    analyzer = variant('simultaneous_entries.py', [
        ('row.get("other_left_turn_intended") is not True',
         'row.get("other_left_turn_intended") is not False'),
        ('Original left-turn intention missing',
         'Original straight intention missing'),
        ('"opposite_direction_left_turn_exception_judgment":"unresolved",',
         '"opposite_direction_left_turn_exception_judgment":"not invoked; straight intention recorded",')])
    finalizer = variant('finalizer.py', [
        ('from simultaneous_entries import analyze',
         'from simultaneous_entries import analyze'),
        ("row.get('other_left_turn_intended') is not True",
         "row.get('other_left_turn_intended') is not False"),
        ('Original opposite left-turn controller intention missing',
         'Original opposite straight controller intention missing'),
        ("return {'opposite_approach': relation == 'opposite_directions',",
         "return {'opposite_approach': relation == 'opposite_directions',\n            'other_left_turn_intended': False,"),
        ("case_id.endswith('stop_opposite_left_turn')",
         "case_id.endswith(('stop_opposite_left_turn','stop_opposite_straight'))"),
        ('Opposite left-turn context must cite original controller history',
         'Opposite-direction context must cite original controller history')])
    # The selected runner uses ordinary local imports inside the embedded
    # construction. No existing selected source or proof is changed.
    construction = json.loads((HERE / 'fourth-construction.json').read_text())
    construction['case_id'] = CASE
    construction['case_design'] = {
        'changed_relation': 'same opposite approach with other commanded straight',
        'turn_intent_source': 'controller_history.jsonl',
        'exception_judgment': 'unresolved',
        'physical_acceptance_claimed': False,
        'comparison': comparison}
    sources = {'runner.py': runner, 'median_route_control.py': control,
               'capture_sources.py': capture,
               'simultaneous_entries.py': analyzer, 'finalizer.py': finalizer,
               'site.json': site,
               'config.json': config_path}
    for item in construction['files']:
        if item['path'] in sources:
            source = sources[item['path']]
            item['source'] = str(source.relative_to(ROOT))
            item['content'] = source.read_text()
        elif item['path'] == 'tests/test_bundle.py':
            item['content'] = item['content'].replace(
                HERE.name + '__stop_opposite_left_turn', CASE)
    construction_path = HERE / 'straight-construction.json'
    write_json(construction_path, construction)
    recipe = diagnostic(site)
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    manifest['cases'] = [entry for entry in manifest['cases']
                         if entry['case_id'] != CASE]
    manifest['cases'].append({
        'case_id': CASE, 'kind': 'delivery',
        'construction': construction_path.name,
        'construction_sha256': sha(construction_path),
        'physical_risk': {'status': 'physical',
                          'reason': 'Native opposite straight motion and crossing geometry require later capture'},
        'candidates': [], 'measurement_contract': 'measurement-contract.json',
        'measurement_procedure': {'entrypoint': 'finalizer.py'},
        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                           'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
        'fixture_recipe': str(recipe.relative_to(ROOT))})
    manifest_path = HERE / 'straight-execution-manifest.json'
    write_json(manifest_path, manifest)
    return {'case_id': CASE, 'construction_sha256': sha(construction_path),
            'manifest': manifest_path.name, 'comparison': comparison}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
