"""Build all three controlled C228670 primary turn cases from current sources."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
FIRST = 'approach_near_depart_right'
SPECS = {
    FIRST: (1.25, 1.80),
    'approach_far_depart_right': (2.20, 1.80),
    'approach_near_depart_left': (1.25, -1.00),
}


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value, compact=False):
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n')


def main():
    base_construction = json.loads((ROOT / 'construction.json').read_text())
    base_manifest = json.loads((ROOT / 'probe-compatibility-manifest.json').read_text())
    base_fixture = json.loads((ROOT / ('diagnostic-' + FIRST + '.json')).read_text())
    base_contract = json.loads((ROOT / ('measurement-contract-' + FIRST + '.json')).read_text())
    base_proposals = json.loads((ROOT / 'proposals/cases.json').read_text())
    source_files = tuple(item['path'] for item in base_construction['files'] if item['path'] != 'config.json')
    entries = []
    proposals = []
    for slug, (approach, departure) in SPECS.items():
        case = ROOT.name + '__' + slug
        config = json.loads((ROOT / 'config.json').read_text())
        config['selected_case_id'] = case
        config['case']['case_id'] = case
        bundle = deepcopy(base_construction)
        bundle['case_id'] = case
        for item in bundle['files']:
            if item['path'] == 'config.json':
                item['content'] = json.dumps(config, indent=2) + '\n'
                item.pop('source', None)
            elif item['path'] in source_files:
                item['content'] = (ROOT / item['path']).read_text()
        construction_path = ROOT / ('construction-' + slug + '.json')
        write(construction_path, bundle)
        fixture = deepcopy(base_fixture)
        files = fixture['files']
        provenance = json.loads(files['fixture-provenance.json'])
        provenance['scope'] = 'Marked synthetic C228670 ' + slug + ' contrast; no actual Native turn evidence'
        files['fixture-provenance.json'] = json.dumps(provenance) + '\n'
        bodies = json.loads(files['body_footprints.json'])
        for row in bodies['frames']:
            if row['phase'] == 'approach' and approach != 1.25:
                row['ground_corners'] = [[point[0] + approach - 1.25, point[1]] for point in row['ground_corners']]
            if slug == 'approach_near_depart_left' and row['phase'] == 'leaving_intersection':
                row['ground_corners'] = [[point[0], point[1] + 2.0] for point in row['ground_corners']]
        files['body_footprints.json'] = json.dumps(bodies) + '\n'
        files['body_footprints.jsonl'] = ''.join(json.dumps(row) + '\n' for row in bodies['frames'])
        fixture_path = ROOT / ('diagnostic-' + slug + '.json')
        write(fixture_path, fixture, compact=True)
        recipe_path = ROOT / ('diagnostic-recipe-' + slug + '.json')
        write(recipe_path, {'format': 'worker-fixture-recipe',
            'sources': [{'path': 'diagnostic-input.json',
                         'source': str(fixture_path.relative_to(REPO)),
                         'sha256': digest(fixture_path)}],
            'generator': {'source': str(fixture_path.relative_to(REPO)),
                          'sha256': digest(fixture_path)}})
        contract = deepcopy(base_contract)
        contract['case_id'] = case
        contract_path = ROOT / ('measurement-contract-' + slug + '.json')
        write(contract_path, contract)
        proposal = deepcopy(base_proposals['cases'][0])
        proposal['case_id'] = case
        proposal['rationale'] = 'Measure exact ' + slug + ' controlled turn contrast without a legal cutoff.'
        proposal['variable_assignments']['approach_left_curb_offset_m']['value'] = approach
        proposal['variable_assignments']['departure_centerline_offset_m']['value'] = departure
        proposal['paired_probe_id'] = ('departure_centerline_side' if slug == 'approach_near_depart_left'
                                       else 'approach_curb_position')
        proposal['deliberate_differences'] = (['departure_centerline_offset_m'] if slug == 'approach_near_depart_left'
                                               else ['approach_left_curb_offset_m'])
        proposal['probe']['primary_variable'] = proposal['deliberate_differences'][0]
        proposal['probe']['target_value_or_branch'] = departure if slug == 'approach_near_depart_left' else approach
        proposals.append(proposal)
        entries.append({'case_id': case, 'construction': construction_path.name,
                        'construction_sha256': digest(construction_path), 'kind': 'delivery',
                        'measurement_contract': contract_path.name,
                        'measurement_procedure': {'entrypoint': 'turn_finalizer.py'},
                        'fixture_recipe': str(recipe_path.relative_to(REPO)),
                        'acquisition': deepcopy(base_manifest['cases'][0]['acquisition'])})
    base_proposals['cases'] = proposals
    write(ROOT / 'proposals/cases.json', base_proposals)
    base_manifest['cases'] = entries
    write(ROOT / 'probe-compatibility-manifest.json', base_manifest)
    write(ROOT / 'construction-probe-manifest.json', {
        'format': 'worker-compatibility-manifest', 'assignment_id': ROOT.name,
        'runtime_manifest_sha256': base_manifest['runtime_manifest_sha256'],
        'cases': [{key: item[key] for key in ('case_id', 'construction', 'construction_sha256', 'kind')}
                  for item in entries]})
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    existing = {row['case_id'] for row in plan['cases']}
    for slug in SPECS:
        case = ROOT.name + '__' + slug
        if case not in existing:
            row = deepcopy(plan['cases'][0])
            row.update(case_id=case, branch=slug)
            plan['cases'].append(row)
    for row in plan['cases']:
        row['construction_status'] = 'exact_primary_constructed_cpu_proof_pending'
    write(ROOT / 'case-plan.json', plan)
    print('Built three exact C228670 primary cases and marked diagnostic source fixtures')


if __name__ == '__main__':
    main()
