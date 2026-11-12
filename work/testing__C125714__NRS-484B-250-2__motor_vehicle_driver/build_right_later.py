"""Build the same right-side crossing with a later other-body entry."""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = ROOT.name + '__source_verified_other_right_near_time'
CASE = ROOT.name + '__source_verified_other_right_later'
OUT = ROOT / 'cases/source_verified_other_right_later'


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
    return min(8, -8 + .8 * max(0, index - 40))


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    construction = copy.deepcopy(json.loads((ROOT / 'construction.json').read_text()))
    construction['case_id'] = CASE
    files = {item['path']: item for item in construction['files']}
    config = json.loads(files['config.json']['content'])
    config['selected_case_id'] = CASE
    config['supported_case_ids'] = [BASE, ROOT.name + '__source_verified_other_left_near_time',
                                    ROOT.name + '__source_verified_other_right_earlier', CASE]
    config['other_release_frame'] = 40
    config['ego_release_frame'] = 20
    files['config.json']['content'] = dump(config)
    files['runner.py']['content'] = files['runner.py']['content'].replace(BASE, CASE)
    runner = files['runner.py']['content']
    old = 'hold, entered_once = near_time_entry_hold(other_inside, entered_once)'
    if runner.count(old) != 1:
        raise ValueError('Expected one near-time hold call')
    runner = runner.replace(old, 'hold, entered_once = later_entry_hold(i, config["ego_release_frame"], other_inside, entered_once)')
    runner = runner.replace('near_time_entry_hold', 'later_entry_hold')
    old_check = '    verify_site_packet(config, base_dir)\n    return config'
    if runner.count(old_check) != 1:
        raise ValueError('Expected exact configuration check')
    runner = runner.replace(old_check,
        '    if type(config.get("ego_release_frame")) is not int or not 0 <= config["ego_release_frame"] < config["other_release_frame"]:\n'
        '        raise ValueError("Ego must release before later other participant")\n'
        '    verify_site_packet(config, base_dir)\n    return config')
    files['runner.py']['content'] = runner
    controller = files['yield_controller.py']['content']
    controller += '''\n\ndef later_entry_hold(frame, ego_release_frame, other_inside, other_entered_once):
    """Attempt ego-first arrival when the right-side other is deliberately later."""
    if type(frame) is not int or type(ego_release_frame) is not int or frame < 0 or ego_release_frame < 0:
        raise ValueError("Nonnegative integer release frames required")
    if type(other_inside) is not bool or type(other_entered_once) is not bool:
        raise ValueError("Measured Boolean other-body state required")
    return frame < ego_release_frame, other_entered_once or other_inside
'''
    files['yield_controller.py']['content'] = controller
    files['tests/test_bundle.py']['content'] = files['tests/test_bundle.py']['content'].replace(
        "self.assertEqual(validate_config(config)['selected_case_id'],config['selected_case_id'])",
        "self.assertEqual(validate_config(config)['selected_case_id'],config['selected_case_id'])\n"
        "  self.assertEqual(config['other_release_frame'],40)\n"
        "  self.assertEqual(config['ego_release_frame'],20)")
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
        entered_once = index > 40 and other_y(index - 1) >= -5.3
        inside_before_tick = index > 40 and abs(other_y(index - 1)) <= 5.3
        control['other_inside_before_tick'] = inside_before_tick
        control['other_entered_once'] = entered_once
        control['ego_control']['hold'] = index < 20
        participant = next(p for p in source['original_observations']['participants'] if p['actor_id'] == 102)
        participant['position_m'] = [0, y, 0]
        participant['body_vertices_m'] = body3(y)
        moving = 40 <= index < 60
        participant['speed_mps'] = 16 if moving else 0
        participant['velocity_mps'] = [0, 16 if moving else 0, 0]
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
                          'reason': 'Later other release may miss the intended crossing or camera coverage'},
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
        row['rationale'] = 'Right-side other vehicle enters later; synthetic CPU diagnostic only'
        proposal['cases'].append(row)
        proposals.write_text(dump(proposal))
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    for index, disposition in enumerate(plan['requirement_dispositions']):
        if index in (0, 1, 2) and CASE not in disposition['case_ids']:
            disposition['case_ids'].append(CASE)
        if index not in (0, 1, 2) and CASE in disposition['case_ids']:
            disposition['case_ids'].remove(CASE)
    plan_path.write_text(dump(plan))
    contract = copy.deepcopy(json.loads((ROOT / 'measurement-contract.json').read_text()))
    contract['requirements'] = [row for row in contract['requirements']
                                if row['disposition_index'] in (0, 1, 2)]
    contract['negative'] = {'remove': ['crossing_history.jsonl'],
                            'error_contains': 'Missing required source: crossing_history.jsonl'}
    contract_path = OUT / 'measurement-contract.json'
    contract_path.write_text(dump(contract))
    manifest = json.loads(manifest_path.read_text())
    next(entry for entry in manifest['cases'] if entry['case_id'] == CASE)['measurement_contract'] = str(
        contract_path.relative_to(ROOT))
    manifest_path.write_text(dump(manifest))
    print(json.dumps({'case_id': CASE, 'construction_sha256': sha(text),
                      'diagnostic_sha256': hashlib.sha256(diagnostic_path.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    build()
