"""Build the same right-side crossing with an earlier other-body entry."""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = ROOT.name + '__source_verified_other_right_near_time'
CASE = ROOT.name + '__source_verified_other_right_earlier'
OUT = ROOT / 'cases/source_verified_other_right_earlier'


def dump(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows)


def box(y):
    return [[-.3, y-.3], [.3, y-.3], [.3, y+.3], [-.3, y+.3]]


def body3(y):
    return [[x, v, z] for x, v in box(y) for z in (0, 1.5)]


def other_y(index):
    return min(8, -8 + .8 * index)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    construction = copy.deepcopy(json.loads((ROOT / 'construction.json').read_text()))
    construction['case_id'] = CASE
    files = {item['path']: item for item in construction['files']}
    config = json.loads(files['config.json']['content'])
    config['selected_case_id'] = CASE
    config['supported_case_ids'] = [BASE, ROOT.name + '__source_verified_other_left_near_time', CASE]
    config['other_release_frame'] = 0
    files['config.json']['content'] = dump(config)
    files['runner.py']['content'] = files['runner.py']['content'].replace(BASE, CASE)
    files['tests/test_bundle.py']['content'] = files['tests/test_bundle.py']['content'].replace(
        "self.assertEqual(validate_config(config)['selected_case_id'],config['selected_case_id'])",
        "self.assertEqual(validate_config(config)['selected_case_id'],config['selected_case_id'])\n"
        "  self.assertEqual(config['other_release_frame'],0)")
    text = dump(construction)
    (OUT / 'construction.json').write_text(text)
    diagnostic = copy.deepcopy(json.loads((ROOT / 'diagnostic.json').read_text()))
    sources = diagnostic['files']
    history = [json.loads(row) for row in sources['crossing_history.jsonl'].splitlines()]
    controls = [json.loads(row) for row in sources['controller_history.jsonl'].splitlines()]
    evidence = [json.loads(row) for row in sources['capture/evidence.jsonl'].splitlines()]
    if not (len(history) == len(controls) == len(evidence) == 60):
        raise ValueError('Expected 60 original diagnostic frames')
    for index, (row, control, source) in enumerate(zip(history, controls, evidence)):
        y = other_y(index)
        row['other']['position_xy_m'] = [0, y]
        row['other']['body_vertices_xy_m'] = box(y)
        entered_once = index > 0 and other_y(index - 1) >= -5.3
        inside_before_tick = index > 0 and abs(other_y(index - 1)) <= 5.3
        control['other_inside_before_tick'] = inside_before_tick
        control['other_entered_once'] = entered_once
        control['ego_control']['hold'] = not entered_once
        participant = next(p for p in source['original_observations']['participants'] if p['actor_id'] == 102)
        participant['position_m'] = [0, y, 0]
        participant['body_vertices_m'] = body3(y)
        participant['speed_mps'] = 16 if index < 20 else 0
        participant['velocity_mps'] = [0, 16 if index < 20 else 0, 0]
        for graph in diagnostic['graphs'][2*index:2*index+2]:
            graph['attributes']['observed_evidence'] = copy.deepcopy(source['original_observations'])
    sources['crossing_history.jsonl'] = lines(history)
    sources['controller_history.jsonl'] = lines(controls)
    sources['capture/evidence.jsonl'] = lines(evidence)
    capture_manifest = json.loads(sources['capture/manifest.json'])
    capture_manifest['case_id'] = CASE
    sources['capture/manifest.json'] = dump(capture_manifest)
    diagnostic_path = OUT / 'diagnostic.json'
    diagnostic_path.write_text(dump(diagnostic))
    origin = OUT / 'fixture-origin.json'
    origin.write_text(dump({'format': 'worker-synthetic-diagnostic-origin',
                            'case_id': CASE, 'physical_evidence': False,
                            'purpose': 'CPU compatibility only'}))
    def ref(path):
        return {'source': str(path.relative_to(REPO)),
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    (OUT / 'diagnostic-recipe.json').write_text(dump({
        'format': 'worker-fixture-recipe',
        'sources': [{'path': 'fixture-origin.json', **ref(origin)}],
        'generator': ref(diagnostic_path)}))
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if CASE not in {entry['case_id'] for entry in manifest['cases']}:
        entry = copy.deepcopy(manifest['cases'][0])
        entry.update({'case_id': CASE, 'construction': str((OUT / 'construction.json').relative_to(ROOT)),
                      'construction_sha256': sha(text),
                      'fixture_recipe': str((OUT / 'diagnostic-recipe.json').relative_to(REPO)),
                      'candidate_risk': {'status': 'physical',
                          'reason': 'Earlier other release may miss the intended source frame or camera coverage'},
                      'candidates': []})
        for key in ('offline', 'compatibility', 'negative'):
            entry.pop(key, None)
        manifest['cases'].append(entry)
        manifest_path.write_text(dump(manifest))
    proposals = ROOT / 'proposals/cases.json'
    proposal = json.loads(proposals.read_text())
    if CASE not in {row['case_id'] for row in proposal['cases']}:
        row = copy.deepcopy(proposal['cases'][0])
        row['case_id'] = CASE
        row['rationale'] = 'Right-side other vehicle enters earlier; synthetic CPU diagnostic only'
        proposal['cases'].append(row)
        proposals.write_text(dump(proposal))
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    for disposition in plan['requirement_dispositions']:
        if CASE not in disposition['case_ids']:
            disposition['case_ids'].append(CASE)
    plan_path.write_text(dump(plan))
    print(json.dumps({'case_id': CASE, 'construction_sha256': sha(text),
                      'diagnostic_sha256': hashlib.sha256(diagnostic_path.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    build()
