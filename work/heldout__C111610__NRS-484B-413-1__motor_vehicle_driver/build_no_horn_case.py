"""Build the matched no-horn construction from the proved same-law template."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'heldout__C111603__NRS-484B-413-1__motor_vehicle_driver'
OLD = 'heldout__C111603__NRS-484B-413-1__motor_vehicle_driver'
NEW = ROOT.name
OLD_CASE = OLD + '__ped_no_horn_audio'
NEW_CASE = NEW + '__pedestrian_no_horn_before_turn'


def write(name, content):
    path = ROOT / name
    path.write_text(content, encoding='utf-8')
    return sha256(path.read_bytes()).hexdigest()


def transform(name):
    return (SOURCE / name).read_text(encoding='utf-8').replace(OLD_CASE, NEW_CASE).replace(OLD, NEW).replace('C111603', 'C111610')


def main():
    construction_name = 'pedestrian-no-horn-construction.json'
    construction = json.loads(transform('ped-no-horn-construction.json'))
    assert construction['case_id'] == NEW_CASE
    assert construction['cell_id'] == 'C111610'
    assert any(f['path'] == 'runner.py' and 'no-horn' in f['content'] for f in construction['files'])
    construction_hash = write(construction_name, json.dumps(construction, indent=2) + '\n')

    diagnostic_name = 'pedestrian-no-horn-diagnostic.json'
    diagnostic_hash = write(diagnostic_name, transform('ped-no-horn-diagnostic.json'))
    recipe_name = 'pedestrian-no-horn-recipe.json'
    recipe = json.loads(transform('ped-no-horn-recipe.json').replace('ped-no-horn-diagnostic.json', diagnostic_name))
    for item in recipe['sources']:
        item['sha256'] = diagnostic_hash
    recipe['generator']['sha256'] = diagnostic_hash
    write(recipe_name, json.dumps(recipe, indent=2) + '\n')

    contract_name = 'pedestrian-no-horn-measurement-contract.json'
    contract = json.loads(transform('ped-no-horn-measurement-contract.json'))
    contract['requirements'][0]['disposition_index'] = 0
    contract['requirements'][0]['requirement'] = json.loads((ROOT / 'case-plan.json').read_text())['requirement_dispositions'][0]['requirement']
    write(contract_name, json.dumps(contract, indent=2) + '\n')

    proposals_path = ROOT / 'proposals/cases.json'
    proposals = json.loads(proposals_path.read_text())
    source_proposals = json.loads((SOURCE / 'proposals/cases.json').read_text())
    proposal = next(c for c in source_proposals['cases'] if c['case_id'] == OLD_CASE)
    proposal = json.loads(json.dumps(proposal).replace(OLD_CASE, NEW_CASE).replace(OLD, NEW))
    proposals['cases'] = [c for c in proposals['cases'] if c['case_id'] != NEW_CASE] + [proposal]
    proposals_path.write_text(json.dumps(proposals, indent=2) + '\n')

    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['cases'] = [c for c in manifest['cases'] if c['case_id'] != NEW_CASE]
    manifest['cases'].append({
        'case_id': NEW_CASE, 'kind': 'delivery',
        'construction': construction_name, 'construction_sha256': construction_hash,
        'measurement_procedure': {'entrypoint': 'turn_finalizer.py'},
        'measurement_contract': contract_name,
        'fixture_recipe': f'work/{NEW}/{recipe_name}',
        'candidate_risk': {
            'status': 'physical',
            'reason': 'Pedestrian route proximity, independent listener audio continuity and camera visibility need physical readback.'
        },
        'candidates': [],
        'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
    })
    write('execution-manifest.json', json.dumps(manifest, indent=2) + '\n')
    print(NEW_CASE, construction_hash, diagnostic_hash)


if __name__ == '__main__':
    main()
