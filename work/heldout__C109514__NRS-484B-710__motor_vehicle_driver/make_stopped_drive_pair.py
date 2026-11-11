"""Expand the source-proved stopped drive-to primary into 499/500/501 ft probes."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREFIX = HERE.name + '__stopped_drive_to_'
SOURCE = HERE / 'cases/stopped_drive_to_500ft'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':') if path.name == 'diagnostic.json' else None,
                               indent=None if path.name == 'diagnostic.json' else 2) + '\n')


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def one(value, old, new):
    if value.count(old) != 1:
        raise ValueError('Expected one stopped case knob: ' + old)
    return value.replace(old, new)


def construction(base, target):
    result = deepcopy(base)
    case = PREFIX + str(target) + 'ft'
    result['case_id'] = case
    files = {item['path']: item for item in result['files']}
    runner = files['runner.py']['content']
    runner = runner.replace('__stopped_drive_to_500ft', '__stopped_drive_to_' + str(target) + 'ft')
    runner = runner.replace('stopped drive-to 500 ft', 'stopped drive-to ' + str(target) + ' ft')
    runner = one(runner, 'config.get("target_distance_ft") != 500',
                 'config.get("target_distance_ft") != ' + str(target))
    runner = one(runner, 'target_gap_ft=520', 'target_gap_ft=' + str(target + 20))
    runner = one(runner, 'target_distance_ft=500,', 'target_distance_ft=' + str(target) + ',')
    files['runner.py']['content'] = runner
    test = files['tests/test_runner.py']['content']
    test = test.replace('__stopped_drive_to_500ft', '__stopped_drive_to_' + str(target) + 'ft')
    test = test.replace('stopped drive-to 500 ft', 'stopped drive-to ' + str(target) + ' ft')
    test = one(test, '"target_distance_ft": 500', '"target_distance_ft": ' + str(target))
    test = one(test, 'config["target_distance_ft"] = 499',
               'config["target_distance_ft"] = ' + str(target + 2))
    files['tests/test_runner.py']['content'] = test
    config = json.loads(files['config.json']['content'])
    config['selected_case_id'] = case
    config['supported_case_ids'] = [case]
    config['target_distance_ft'] = target
    config['case']['case_id'] = case
    files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
    result['files'] = list(files.values())
    return result


def diagnostic(base, target, folder):
    spec = deepcopy(base)
    rows = [json.loads(line) for line in spec['files']['participant_footprints.jsonl'].splitlines()]
    delta = (target - 500) / 3.280839895013123
    for row in rows:
        for corner in row['apparatus_corners']:
            corner[0] += delta
    spec['files']['participant_footprints.jsonl'] = ''.join(
        json.dumps(row, separators=(',', ':')) + '\n' for row in rows)
    case = PREFIX + str(target) + 'ft'
    for name in ('capture/manifest.json', 'fixture-provenance.json'):
        value = json.loads(spec['files'][name]); value['case_id'] = case
        spec['files'][name] = json.dumps(value, indent=2) + '\n'
    path = folder / 'diagnostic.json'
    save(path, spec)
    relative = path.relative_to(ROOT).as_posix()
    save(folder / 'diagnostic-recipe.json', {
        'format': 'worker-fixture-recipe',
        'sources': [{'path': 'diagnostic.json', 'source': relative, 'sha256': digest(path)}],
        'generator': {'source': relative, 'sha256': digest(path)}})


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    reference = next(row for row in manifest['cases'] if row['case_id'] == PREFIX + '500ft')
    existing = {row['case_id']: row for row in manifest['cases']}
    plan_path = HERE / 'case-plan.json'; plan = json.loads(plan_path.read_text())
    proposal_path = HERE / 'proposals/cases.json'; proposal = json.loads(proposal_path.read_text())
    reference_proposal = next(row for row in proposal['cases'] if row['case_id'] == PREFIX + '500ft')
    base_diagnostic = json.loads((SOURCE / 'diagnostic.json').read_text())
    contract = json.loads((SOURCE / 'measurement-contract.json').read_text())
    for target in (499, 501):
        case = PREFIX + str(target) + 'ft'
        folder = HERE / 'cases' / ('stopped_drive_to_' + str(target) + 'ft')
        folder.mkdir(parents=True, exist_ok=True)
        save(folder / 'construction.json', construction(json.loads((SOURCE / 'construction.json').read_text()), target))
        diagnostic(base_diagnostic, target, folder)
        selected_contract = deepcopy(contract); selected_contract['case_id'] = case
        save(folder / 'measurement-contract.json', selected_contract)
        entry = {'case_id': case, 'kind': 'delivery',
                 'construction': (folder / 'construction.json').relative_to(HERE).as_posix(),
                 'construction_sha256': digest(folder / 'construction.json'),
                 'measurement_contract': (folder / 'measurement-contract.json').relative_to(HERE).as_posix(),
                 'measurement_procedure': {'entrypoint': 'fire_finalizer.py'},
                 'fixture_recipe': (folder / 'diagnostic-recipe.json').relative_to(ROOT).as_posix(),
                 'native_handoff': deepcopy(reference['native_handoff']),
                 'candidate_risk': deepcopy(reference['candidate_risk']),
                 'acquisition': deepcopy(reference['acquisition']), 'candidates': []}
        for candidate in reference['candidates']:
            ident = candidate['id']
            path = folder / (ident + '-construction.json')
            save(path, construction(json.loads((SOURCE / (ident + '-construction.json')).read_text()), target))
            entry['candidates'].append({'id': ident,
                'construction': path.relative_to(HERE).as_posix(),
                'construction_sha256': digest(path),
                'trigger': deepcopy(candidate['trigger']),
                'changed_knobs': deepcopy(candidate['changed_knobs'])})
        existing[case] = entry
        plan['cases'] = [row for row in plan['cases'] if row['case_id'] != case]
        plan['cases'].append({'case_id': case, 'target_law_id': 'NRS-484B-710',
                              'branch': 'stopped_drive_to', 'target_distance_ft': target,
                              'gap_ids': ['stopped-drive-to'],
                              'construction_status': 'exact_bundle_pending_proofs',
                              'physical_risk': deepcopy(next(row for row in plan['cases']
                                     if row['case_id'] == PREFIX + '500ft')['physical_risk'])})
        proposed = deepcopy(reference_proposal); proposed['case_id'] = case
        proposed['rationale'] = 'Measure stopped-apparatus drive-to centre distance at the ' + str(target) + ' ft engineering command'
        proposed['variable_assignments']['target_distance_ft']['value'] = target
        proposal['cases'] = [row for row in proposal['cases'] if row['case_id'] != case] + [proposed]
    ids = [PREFIX + str(value) + 'ft' for value in (499, 500, 501)]
    plan['requirement_dispositions'][1]['case_ids'] = ids
    plan['comparisons'] = [row for row in plan['comparisons'] if row['comparison_id'] != 'stopped_drive_to_500_boundary']
    plan['comparisons'].append({'comparison_id': 'stopped_drive_to_500_boundary',
        'case_ids': ids,
        'fixed_conditions': ['C109514 connected through-intersection route',
                             'ordinary subject, stopped apparatus in answer to alarm',
                             'same four-camera/duration plan and approach policy'],
        'deliberate_differences': ['commanded centre distance 499/500/501 ft; actual distance measured from original footprints']})
    plan['observations'][0]['case_ids'] = list(dict.fromkeys(plan['observations'][0]['case_ids'] + ids))
    manifest['cases'] = list(existing.values())
    save(plan_path, plan); save(proposal_path, proposal); save(manifest_path, manifest)


if __name__ == '__main__':
    main()
