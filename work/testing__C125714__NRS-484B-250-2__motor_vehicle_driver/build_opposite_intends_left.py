"""Build the opposing left-intention diagnostic with the straight path held fixed."""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OLD = ROOT.name + '__source_verified_opposite_straight'
CASE = ROOT.name + '__source_verified_opposite_intends_left'
BASE = ROOT / 'cases/source_verified_opposite_straight'
OUT = ROOT / 'cases/source_verified_opposite_intends_left'


def dump(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def change(text, before, after):
    if text.count(before) != 1:
        raise ValueError(f'Expected one occurrence of {before!r}; found {text.count(before)}')
    return text.replace(before, after)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    construction = copy.deepcopy(json.loads((BASE / 'construction.json').read_text()))
    construction['case_id'] = CASE
    files = {item['path']: item for item in construction['files']}
    config = json.loads(files['config.json']['content'])
    config['selected_case_id'] = CASE
    config['supported_case_ids'] = list(config['supported_case_ids']) + [CASE]
    config['other_intent'] = 'left'
    files['config.json']['content'] = dump(config)
    runner = change(files['runner.py']['content'], OLD, CASE)
    runner = change(runner, 'config.get("other_intent") != "straight"',
                    'config.get("other_intent") != "left"')
    runner = change(runner, 'Opposite straight intention required',
                    'Opposite left intention required')
    files['runner.py']['content'] = runner
    finalizer = change(files['finalizer.py']['content'],
                       'intent.get("intended_maneuver") != "straight"',
                       'intent.get("intended_maneuver") != "left"')
    finalizer = change(finalizer, 'Missing authored opposite straight intention',
                       'Missing authored opposite left intention')
    finalizer = change(finalizer, '"intended_maneuver": "straight", "observed_heading_range_deg":',
                       '"intended_maneuver": "left", "observed_turn_completed": False, "observed_heading_range_deg":')
    files['finalizer.py']['content'] = finalizer
    files['tests/test_bundle.py']['content'] = change(
        files['tests/test_bundle.py']['content'],
        "self.assertEqual(config['other_intent'],'straight')",
        "self.assertEqual(config['other_intent'],'left')")
    construction_path = OUT / 'construction.json'
    construction_path.write_text(dump(construction))

    diagnostic = copy.deepcopy(json.loads((BASE / 'diagnostic.json').read_text()))
    sources = diagnostic['files']
    intent = json.loads(sources['turn_intent.json'])
    intent['intended_maneuver'] = 'left'
    sources['turn_intent.json'] = dump(intent)
    capture = json.loads(sources['capture/manifest.json'])
    capture['case_id'] = CASE
    sources['capture/manifest.json'] = dump(capture)
    diagnostic_path = OUT / 'diagnostic.json'
    diagnostic_path.write_text(dump(diagnostic))
    origin = OUT / 'fixture-origin.json'
    origin.write_text(dump({'format': 'worker-synthetic-diagnostic-origin',
                            'case_id': CASE, 'physical_evidence': False,
                            'purpose': 'CPU compatibility only'}))
    def ref(path):
        return {'source': str(path.relative_to(REPO)), 'sha256': sha(path)}
    (OUT / 'diagnostic-recipe.json').write_text(dump({
        'format': 'worker-fixture-recipe',
        'sources': [{'path': 'fixture-origin.json', **ref(origin)}],
        'generator': ref(diagnostic_path)}))

    requirement = ('Original opposite approach headings, authored left-turn intention, '
                   'and observed unturned heading history distinguish intention from '
                   'completed turning without deciding legal applicability')
    source = 'NRS 484B.250(2); inputs/' + ROOT.name + '/assignment.json'
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    for index in (0, 2):
        rows = plan['requirement_dispositions'][index]['case_ids']
        if CASE not in rows:
            rows.append(CASE)
    found = next((index for index, row in enumerate(plan['requirement_dispositions'])
                  if row['requirement'] == requirement), None)
    if found is None:
        found = len(plan['requirement_dispositions'])
        plan['requirement_dispositions'].append({
            'requirement': requirement, 'source': source, 'status': 'selected_required',
            'case_ids': [CASE], 'output_key': 'opposite_approach',
            'evidence_or_gap': 'Synthetic CPU sources only; original Native intention and turn completion unverified'})
    plan_path.write_text(dump(plan))

    contract = copy.deepcopy(json.loads((BASE / 'measurement-contract.json').read_text()))
    row = contract['requirements'][-1]
    row['disposition_index'] = found
    row['requirement'] = requirement
    (OUT / 'measurement-contract.json').write_text(dump(contract))

    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if CASE not in {entry['case_id'] for entry in manifest['cases']}:
        old = next(entry for entry in manifest['cases'] if entry['case_id'] == OLD)
        entry = copy.deepcopy(old)
        entry.update({'case_id': CASE,
                      'construction': str(construction_path.relative_to(ROOT)),
                      'construction_sha256': sha(construction_path),
                      'fixture_recipe': str((OUT / 'diagnostic-recipe.json').relative_to(REPO)),
                      'measurement_contract': str((OUT / 'measurement-contract.json').relative_to(ROOT)),
                      'candidate_risk': {'status': 'physical',
                                         'reason': 'Opposite Native path may not remain straight or preserve four-camera coverage'},
                      'candidates': []})
        for key in ('offline', 'compatibility', 'negative'):
            entry.pop(key, None)
        manifest['cases'].append(entry)
        manifest_path.write_text(dump(manifest))
    proposals_path = ROOT / 'proposals/cases.json'
    proposals = json.loads(proposals_path.read_text())
    if CASE not in {row['case_id'] for row in proposals['cases']}:
        proposal = copy.deepcopy(next(row for row in proposals['cases'] if row['case_id'] == OLD))
        proposal['case_id'] = CASE
        proposal['rationale'] = 'Opposite authored left intention with observed straight heading; synthetic CPU diagnostic only'
        proposals['cases'].append(proposal)
        proposals_path.write_text(dump(proposals))
    print(json.dumps({'case_id': CASE, 'construction_sha256': sha(construction_path),
                      'diagnostic_sha256': sha(diagnostic_path)}))


if __name__ == '__main__':
    build()
