"""Materialize all four exact officer indication/response diagnostic cases."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASES = {
    'stop_responds': ('stop', 'stopped_after_indication', [2, 2, 2, 2, 1, .5, 0, 0, 0]),
    'stop_does_not_respond': ('stop', 'no_observed_stop', [2] * 9),
    'proceed_responds': ('proceed', 'moved_after_indication', [0, 0, 0, 0, 1, 2, 2, 2, 2]),
    'proceed_does_not_respond': ('proceed', 'no_observed_movement', [0] * 9),
}


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def write(path, value, *, compact=False):
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n')


def main():
    (ROOT / 'cases').mkdir(exist_ok=True)
    construction = json.loads((ROOT / 'construction.json').read_text())
    config = json.loads((ROOT / 'config.json').read_text())
    fixture = json.loads((ROOT / 'diagnostic-stop_responds.json').read_text())
    contract = json.loads((ROOT / 'measurement-contract-stop_responds.json').read_text())
    first = json.loads((ROOT / 'probe-compatibility-manifest.json').read_text())
    primary_entry = first['cases'][0]
    entries = []
    probes = []
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    for suffix, (command, observed_response, speeds) in CASES.items():
        case_id = ROOT.name + '__' + suffix
        selected_config = deepcopy(config)
        selected_config['selected_case_id'] = case_id
        selected_config['case']['case_id'] = case_id
        selected_config['case']['intended_observed_response'] = observed_response
        selected_construction = deepcopy(construction)
        selected_construction['case_id'] = case_id
        next(item for item in selected_construction['files'] if item['path'] == 'config.json')['content'] = (
            json.dumps(selected_config, indent=2) + '\n')
        construction_path = ROOT / 'cases' / f'construction-{suffix}.json'
        write(construction_path, selected_construction)
        probes.append({'case_id': case_id,
                       'construction': str(construction_path.relative_to(ROOT)),
                       'construction_sha256': digest(construction_path)})
        source = deepcopy(fixture)
        files = source['files']
        indication = json.loads(files['officer_direction.json'])
        indication['command'] = command
        files['officer_direction.json'] = json.dumps(indication) + '\n'
        motion = json.loads(files['subject_motion.json'])
        for row, speed in zip(motion['frames'], speeds):
            row['speed_mps'] = speed
        files['subject_motion.json'] = json.dumps(motion) + '\n'
        files['subject_motion_history.jsonl'] = ''.join(json.dumps(row) + '\n' for row in motion['frames'])
        provenance = json.loads(files['fixture-provenance.json'])
        provenance['scope'] = 'Marked synthetic exact '+suffix+' officer indication and response; no Native lawful-order evidence'
        files['fixture-provenance.json'] = json.dumps(provenance) + '\n'
        diagnostic_path = ROOT / f'diagnostic-{suffix}.json'
        write(diagnostic_path, source, compact=True)
        recipe_path = ROOT / f'diagnostic-recipe-{suffix}.json'
        write(recipe_path, {'format': 'worker-fixture-recipe',
            'sources': [{'path': 'diagnostic-input.json',
                         'source': str(diagnostic_path.relative_to(REPO)),
                         'sha256': digest(diagnostic_path)}],
            'generator': {'source': str(diagnostic_path.relative_to(REPO)),
                          'sha256': digest(diagnostic_path)}})
        selected_contract = deepcopy(contract)
        selected_contract['case_id'] = case_id
        contract_path = ROOT / 'cases' / f'measurement-contract-{suffix}.json'
        write(contract_path, selected_contract)
        entries.append({**primary_entry, **probes[-1],
                        'measurement_contract': str(contract_path.relative_to(ROOT)),
                        'fixture_recipe': str(recipe_path.relative_to(REPO))})
        planned = next(row for row in plan['cases'] if row['case_id'] == case_id)
        planned['construction_status'] = 'exact_inline_primary_materialized_cpu_proofs_pending'
    write(ROOT / 'construction-probe-manifest.json', {
        'format': 'worker-construction-cases', 'assignment_id': ROOT.name, 'cases': probes})
    first['cases'] = entries
    write(ROOT / 'probe-compatibility-manifest.json', first)
    write(plan_path, plan)
    print('Materialized four exact C10365 primary constructions, contracts and distinct fixtures')


if __name__ == '__main__':
    main()
