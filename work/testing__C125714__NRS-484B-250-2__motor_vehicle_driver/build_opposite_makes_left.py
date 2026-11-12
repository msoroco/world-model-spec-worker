"""Build a CPU diagnostic for an observed left turn from the opposing approach."""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OLD = ROOT.name + '__source_verified_opposite_intends_left'
CASE = ROOT.name + '__source_verified_opposite_makes_left'
BASE = ROOT / 'cases/source_verified_opposite_intends_left'
OUT = ROOT / 'cases/source_verified_opposite_makes_left'


def dump(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def change(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Expected one occurrence of {old!r}; found {text.count(old)}')
    return text.replace(old, new)


def box(x, y):
    return [[x-.3, y-.3], [x+.3, y-.3], [x+.3, y+.3], [x-.3, y+.3]]


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    construction = copy.deepcopy(json.loads((BASE / 'construction.json').read_text()))
    construction['case_id'] = CASE
    files = {row['path']: row for row in construction['files']}
    config = json.loads(files['config.json']['content'])
    config['selected_case_id'] = CASE
    config['supported_case_ids'] = list(config['supported_case_ids']) + [CASE]
    config['site']['routes']['other'] = [[10, 3.5], [4, 3.5], [0, 3.5], [0, 0], [0, -10]]
    packet = json.loads(files['site-review.json']['content'])
    packet['site'] = config['site']
    files['site-review.json']['content'] = dump(packet)
    config['site_review']['sha256'] = hashlib.sha256(files['site-review.json']['content'].encode()).hexdigest()
    files['config.json']['content'] = dump(config)
    files['runner.py']['content'] = change(files['runner.py']['content'], OLD, CASE)
    finalizer = files['finalizer.py']['content']
    finalizer = change(finalizer,
        'if len(headings) < 2 or any(abs((heading - 180 + 180) % 360 - 180) > 15 for heading in headings):\n'
        '        raise ValueError("Other original heading did not remain straight")',
        'if len(headings) < 2 or abs(headings[0] - 180) > 15 or max(headings) < 255:\n'
        '        raise ValueError("Original headings do not show an opposing approach and completed left turn")')
    finalizer = change(finalizer, '"observed_turn_completed": False',
                       '"observed_turn_completed": True')
    files['finalizer.py']['content'] = finalizer
    construction_path = OUT / 'construction.json'
    construction_path.write_text(dump(construction))

    diagnostic = copy.deepcopy(json.loads((BASE / 'diagnostic.json').read_text()))
    sources = diagnostic['files']
    history = [json.loads(row) for row in sources['crossing_history.jsonl'].splitlines()]
    evidence = [json.loads(row) for row in sources['capture/evidence.jsonl'].splitlines()]
    for index, (row, observation) in enumerate(zip(history, evidence)):
        if index <= 30:
            continue
        y = max(-8, 3.5 - .8*(index-30))
        row['other']['position_xy_m'] = [0, y]
        row['other']['body_vertices_xy_m'] = box(0, y)
        participant = next(p for p in observation['original_observations']['participants']
                           if p['actor_id'] == 102)
        participant['position_m'] = [0, y, 0]
        participant['body_vertices_m'] = [[x, yy, z] for x, yy in box(0, y) for z in (0, 1.5)]
        participant['heading_deg'] = 270
        participant['velocity_mps'] = [0, -participant['speed_mps'], 0]
        for graph in diagnostic['graphs'][2*index:2*index+2]:
            graph['attributes']['observed_evidence'] = copy.deepcopy(observation['original_observations'])
    sources['crossing_history.jsonl'] = ''.join(json.dumps(row) + '\n' for row in history)
    sources['capture/evidence.jsonl'] = ''.join(json.dumps(row) + '\n' for row in evidence)
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
                   'and observed changing heading history identify a completed left turn '
                   'without deciding legal applicability')
    source = 'NRS 484B.250(2); inputs/' + ROOT.name + '/assignment.json'
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    for index in (0, 2):
        if CASE not in plan['requirement_dispositions'][index]['case_ids']:
            plan['requirement_dispositions'][index]['case_ids'].append(CASE)
    found = next((i for i, row in enumerate(plan['requirement_dispositions'])
                  if row['requirement'] == requirement), None)
    if found is None:
        found = len(plan['requirement_dispositions'])
        plan['requirement_dispositions'].append({
            'requirement': requirement, 'source': source, 'status': 'selected_required',
            'case_ids': [CASE], 'output_key': 'opposite_approach',
            'evidence_or_gap': 'Synthetic CPU headings only; physical Native turn unverified'})
    plan_path.write_text(dump(plan))
    contract = copy.deepcopy(json.loads((BASE / 'measurement-contract.json').read_text()))
    contract['requirements'][-1]['disposition_index'] = found
    contract['requirements'][-1]['requirement'] = requirement
    (OUT / 'measurement-contract.json').write_text(dump(contract))
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if CASE not in {row['case_id'] for row in manifest['cases']}:
        row = copy.deepcopy(next(row for row in manifest['cases'] if row['case_id'] == OLD))
        row.update({'case_id': CASE, 'construction': str(construction_path.relative_to(ROOT)),
                    'construction_sha256': sha(construction_path),
                    'fixture_recipe': str((OUT / 'diagnostic-recipe.json').relative_to(REPO)),
                    'measurement_contract': str((OUT / 'measurement-contract.json').relative_to(ROOT)),
                    'candidate_risk': {'status': 'physical',
                                       'reason': 'Native left turn may miss crossing, capture or complete turn'},
                    'candidates': []})
        for key in ('offline', 'compatibility', 'negative'):
            row.pop(key, None)
        manifest['cases'].append(row)
        manifest_path.write_text(dump(manifest))
    proposals_path = ROOT / 'proposals/cases.json'
    proposals = json.loads(proposals_path.read_text())
    if CASE not in {row['case_id'] for row in proposals['cases']}:
        row = copy.deepcopy(next(row for row in proposals['cases'] if row['case_id'] == OLD))
        row['case_id'] = CASE
        row['rationale'] = 'Opposite left turn observed in synthetic CPU source; physical completion unverified'
        proposals['cases'].append(row)
        proposals_path.write_text(dump(proposals))
    print(json.dumps({'case_id': CASE, 'construction_sha256': sha(construction_path),
                      'diagnostic_sha256': sha(diagnostic_path)}))


if __name__ == '__main__':
    build()
