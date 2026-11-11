"""Build the first exact parked-apparatus case from the proved stopped source pattern."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE / 'cases/stopped_drive_to_500ft'
DEST = HERE / 'cases/stopped_park_500ft'
CASE = HERE.name + '__stopped_park_500ft'


def put(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(',', ':') if path.name == 'diagnostic.json' else None,
                               indent=None if path.name == 'diagnostic.json' else 2) + '\n')


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def one(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Expected one parking construction knob: ' + old)
    return text.replace(old, new)


def main():
    construction = deepcopy(json.loads((SOURCE / 'construction.json').read_text()))
    construction['case_id'] = CASE
    files = {item['path']: item for item in construction['files']}
    runner = files['runner.py']['content']
    runner = runner.replace('__stopped_drive_to_500ft', '__stopped_park_500ft')
    runner = runner.replace('stopped drive-to 500 ft', 'stopped park 500 ft')
    runner = one(runner, 'config.get("fire_branch") != "stopped_drive_to"',
                 'config.get("fire_branch") != "stopped_park"')
    runner = one(runner, 'from stopped_controller import approach_step',
                 'from park_controller import park_step')
    runner = one(runner, 'target_gap_ft=520)', 'target_gap_ft=510)')
    runner = one(runner, 'approach_step(ego, apparatus, target_distance_ft=500,',
                 'park_step(ego, apparatus, target_distance_ft=500,')
    files['runner.py']['content'] = runner
    files['park_controller.py'] = {'path': 'park_controller.py',
                                   'content': (HERE / 'park_controller.py').read_text()}
    config = json.loads(files['config.json']['content'])
    config.update(selected_case_id=CASE, supported_case_ids=[CASE], fire_branch='stopped_park')
    config['case']['case_id'] = CASE
    files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
    test = files['tests/test_runner.py']['content']
    test = test.replace('__stopped_drive_to_500ft', '__stopped_park_500ft')
    test = test.replace('stopped drive-to 500 ft', 'stopped park 500 ft')
    test = test.replace('"fire_branch": "stopped_drive_to"', '"fire_branch": "stopped_park"')
    files['tests/test_runner.py']['content'] = test
    construction['files'] = list(files.values())
    put(DEST / 'construction.json', construction)

    diagnostic = deepcopy(json.loads((SOURCE / 'diagnostic.json').read_text()))
    rows = [json.loads(line) for line in diagnostic['files']['participant_footprints.jsonl'].splitlines()]
    metres = [0, .1, .2, 1 / 3.280839895013123] + [1 / 3.280839895013123] * (len(rows) - 4)
    for index, row in enumerate(rows):
        for corner in row['ego_corners']:
            corner[0] += metres[index] - .15 * index
    diagnostic['files']['participant_footprints.jsonl'] = ''.join(
        json.dumps(row, separators=(',', ':')) + '\n' for row in rows)
    states = [json.loads(line) for line in diagnostic['files']['participant_state.jsonl'].splitlines()]
    for index, row in enumerate(states):
        row['ego_moving'] = index < 4
        row['ego_parked'] = index >= 4
    diagnostic['files']['participant_state.jsonl'] = ''.join(
        json.dumps(row, separators=(',', ':')) + '\n' for row in states)
    for name in ('capture/manifest.json', 'fixture-provenance.json'):
        data = json.loads(diagnostic['files'][name]); data['case_id'] = CASE
        diagnostic['files'][name] = json.dumps(data, indent=2) + '\n'
    put(DEST / 'diagnostic.json', diagnostic)
    relative = (DEST / 'diagnostic.json').relative_to(ROOT).as_posix()
    put(DEST / 'diagnostic-recipe.json', {
        'format': 'worker-fixture-recipe',
        'sources': [{'path': 'diagnostic.json', 'source': relative,
                     'sha256': digest(DEST / 'diagnostic.json')}],
        'generator': {'source': relative, 'sha256': digest(DEST / 'diagnostic.json')}})
    contract = deepcopy(json.loads((SOURCE / 'measurement-contract.json').read_text()))
    contract['case_id'] = CASE
    contract['requirements'][0]['disposition_index'] = 2
    contract['requirements'][0]['requirement'] = 'park within the boundary of stopped fire apparatus'
    put(DEST / 'measurement-contract.json', contract)

    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    reference = next(row for row in manifest['cases'] if row['case_id'].endswith('__stopped_drive_to_500ft'))
    entry = {'case_id': CASE, 'kind': 'delivery',
             'construction': (DEST / 'construction.json').relative_to(HERE).as_posix(),
             'construction_sha256': digest(DEST / 'construction.json'),
             'measurement_contract': (DEST / 'measurement-contract.json').relative_to(HERE).as_posix(),
             'measurement_procedure': {'entrypoint': 'fire_finalizer.py'},
             'fixture_recipe': (DEST / 'diagnostic-recipe.json').relative_to(ROOT).as_posix(),
             'native_handoff': deepcopy(reference['native_handoff']),
             'candidate_risk': {'status': 'physical', 'reason':
                 'Actual approach, full stop and parking brake may not occur at the intended centre distance'},
             'acquisition': deepcopy(reference['acquisition']), 'candidates': []}
    manifest['cases'] = [row for row in manifest['cases'] if row['case_id'] != CASE] + [entry]
    put(manifest_path, manifest)

    path = HERE / 'case-plan.json'; plan = json.loads(path.read_text())
    plan['cases'] = [row for row in plan['cases'] if row['case_id'] != CASE]
    plan['cases'].append({'case_id': CASE, 'target_law_id': 'NRS-484B-710',
        'branch': 'stopped_park', 'target_distance_ft': 500,
        'gap_ids': ['stopped-park'], 'construction_status': 'exact_bundle_pending_proofs',
        'physical_risk': {'risk': 'Subject may fail to stop and park near the apparatus',
                          'trigger_source': 'original participant state and footprint streams',
                          'trigger_metric': 'parked active frames and measured centre distance',
                          'failure_condition': 'No stationary handbraked frame at the engineering target'}})
    plan['requirement_dispositions'][2]['status'] = 'selected_required'
    plan['requirement_dispositions'][2]['case_ids'] = [CASE]
    plan['requirement_dispositions'][2]['evidence_or_gap'] = 'No accepted recording; first parking case has an exact CPU construction draft.'
    put(path, plan)
    path = HERE / 'proposals/cases.json'; proposals = json.loads(path.read_text())
    row = deepcopy(next(row for row in proposals['cases'] if row['case_id'].endswith('__stopped_drive_to_500ft')))
    row['case_id'] = CASE
    row['rationale'] = 'Measure full stop and parking near apparatus stopped in answer to alarm at the 500 ft engineering command'
    proposals['cases'] = [item for item in proposals['cases'] if item['case_id'] != CASE] + [row]
    put(path, proposals)


if __name__ == '__main__':
    main()
