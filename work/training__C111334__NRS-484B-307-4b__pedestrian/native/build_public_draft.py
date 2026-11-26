"""Bind exact offline bundles and first diagnostic to a partial public draft."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ROOT = FOLDER.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def build():
    selected = json.loads((FOLDER / 'native-selected/construction-manifest.json').read_text())
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    recording = json.loads((HERE / 'config.json').read_text())['recording_description']
    proposal = {'cell_id': 'C111334', 'actor': 'pedestrian',
        'status': 'partial_source_bound_draft', 'sweep_specs': [],
        'sweeps_expanded': True, 'cases': []}
    for item in plan['cases']:
        case = dict(item)
        case['recording_description'] = recording
        case['rationale'] = 'Exact NRS 484B.307(4)(b) controlled pedestrian entry and permission comparison; no physical finding.'
        case['variable_assignments'] = {
            'pedestrian_entry_request': {'kind': 'controller',
                'value': item['case_id'].split('__')[-1] != 'probe_1'},
            'other_device_permission_request': {'kind': 'controller',
                'value': item['case_id'].split('__')[-1] == 'permission_before_entry'}}
        case['unresolved_judgment_calls'] = [
            'Original green turn arrow alone and facing',
            'Other device permission under NRS 484B.283']
        proposal['cases'].append(case)
    write(FOLDER / 'proposals/cases.json', proposal)
    entries = []
    for entry in selected['cases']:
        item = dict(entry)
        for key in ('construction', 'measurement_contract'):
            item[key] = 'native-selected/' + item[key]
        item['offline'] = dict(item['offline'])
        item['offline']['log'] = 'native-selected/' + item['offline']['log']
        suffix = item['case_id'].rsplit('__', 1)[1]
        recipe = FOLDER / 'native/diagnostic' / suffix / 'fixture-recipe.json'
        if recipe.is_file():
            item['fixture_recipe'] = str(recipe.relative_to(ROOT))
        entries.append(item)
    manifest = {'format': 'worker-execution-manifest',
        'assignment_id': selected['assignment_id'],
        'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
        'delivery_ready': False, 'status': 'partial_public_diagnostic',
        'cases': entries}
    write(FOLDER / 'native-draft-manifest.json', manifest)
    return {'cases': len(entries), 'first_fixture': entries[1].get('fixture_recipe')}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
