"""Build source-shaped button diagnostics for the two exact course cases.

These textual sources exercise saved processing; their authority claims and
physical indication readbacks remain unverified until original capture review.
"""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name


def write(path, value):
    path.write_text(json.dumps(value, separators=(',', ':')) + '\n')
    return sha256(path.read_bytes()).hexdigest()


def build():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    proposal_path = ROOT / 'proposals/cases.json'
    proposal = json.loads(proposal_path.read_text())
    built = {}
    for variant, stem in (('indicated_course', 'button-indicated'),
                          ('divergent_course', 'button-divergent')):
        case_id = ASSIGNMENT + '__button_' + variant
        source_stem = 'indicated' if variant == 'indicated_course' else 'divergent'
        spec = json.loads((ROOT / (source_stem + '-diagnostic.json')).read_text())
        files = spec['files']
        authority = json.loads(files['authority_source_original.json'])
        authority['authorization_source'] = 'CPU diagnostic button claim; unverified'
        authority['indication_form'] = 'button'
        authority['indications'] = [{'form': 'button', 'x': 0.0, 'y': 0.0}]
        original = json.dumps(authority, sort_keys=True) + '\n'
        scene = json.loads(files['marked_intersection.json'])
        scene.update({key: authority[key] for key in
                      ('authorization_source', 'indication_form')})
        scene['case_id'] = case_id
        scene.pop('physical_markers_xy_m', None)
        scene['physical_indications_xy_m'] = [[0.0, 0.0]]
        scene['authority_source_sha256'] = sha256(original.encode()).hexdigest()
        files['authority_source_original.json'] = original
        files['marked_intersection.json'] = json.dumps(scene) + '\n'
        diagnostic = ROOT / (stem + '-diagnostic.json')
        digest = write(diagnostic, spec)
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json',
                               'source': f'work/{ASSIGNMENT}/{diagnostic.name}',
                               'sha256': digest}],
                  'generator': {'source': f'work/{ASSIGNMENT}/{diagnostic.name}',
                                'sha256': digest}}
        recipe_path = ROOT / (stem + '-recipe.json')
        write(recipe_path, recipe)
        contract = json.loads((ROOT / (source_stem + '-measurement-contract.json')).read_text())
        contract['case_id'] = case_id
        contract['requirements'][0]['method'] = 'measure_marked_course'
        contract_path = ROOT / (stem + '-measurement-contract.json')
        write(contract_path, contract)
        entry = next(c for c in manifest['cases'] if c['case_id'] == case_id)
        entry['fixture_recipe'] = f'work/{ASSIGNMENT}/{recipe_path.name}'
        entry['measurement_contract'] = contract_path.name
        exemplar = next(c for c in proposal['cases']
                        if c['case_id'] == ASSIGNMENT + '__' + variant)
        selected = json.loads(json.dumps(exemplar))
        selected['case_id'] = case_id
        selected['rationale'] = ('Source-shaped button-indicated course; original '
                                 'municipal authority, pixels and motion remain unverified.')
        construction = json.loads((ROOT / entry['construction']).read_text())
        config = json.loads(next(f['content'] for f in construction['files']
                                 if f['path'] == 'config.json'))
        selected['recording_description'] = config['case']['recording_description']
        proposal['cases'] = [c for c in proposal['cases'] if c['case_id'] != case_id]
        proposal['cases'].append(selected)
        built[case_id] = digest
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    proposal_path.write_text(json.dumps(proposal, indent=2) + '\n')
    return built


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
