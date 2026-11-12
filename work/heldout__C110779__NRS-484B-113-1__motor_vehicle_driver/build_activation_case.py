"""Stage the forward-only activation control using the same reviewed corridor."""
from hashlib import sha256
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / '.runtime-work/c110779-native-stage'
WORK = ROOT / 'work/heldout__C110779__NRS-484B-113-1__motor_vehicle_driver'
CASE = WORK.name + '__no_reverse_control'
BASE = WORK.name + '__backing_clear_vehicle'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')
    return sha256(path.read_bytes()).hexdigest()


def audit_activation_pair(base, control):
    """Compare original source rows while allowing only ego activation to change."""
    left, right = base['files'], control['files']
    if set(left) != set(right):
        raise ValueError('Activation pair source inventory differs')
    for name in left:
        if name in ('capture/manifest.json', 'backing_motion.jsonl'):
            continue
        if left[name] != right[name]:
            raise ValueError('Activation pair changed fixed source: ' + name)
    lrows = [json.loads(line) for line in left['backing_motion.jsonl'].splitlines() if line]
    rrows = [json.loads(line) for line in right['backing_motion.jsonl'].splitlines() if line]
    if len(lrows) != len(rrows) or not lrows:
        raise ValueError('Activation pair frame inventory differs')
    for a, b in zip(lrows, rrows):
        for key in ('frame', 'time_s', 'ego_heading_xy', 'participants'):
            if a[key] != b[key]:
                raise ValueError('Activation pair changed fixed source: ' + key)
        if a['ego']['y_m'] != b['ego']['y_m'] or a['ego']['body_radius_m'] != b['ego']['body_radius_m']:
            raise ValueError('Activation pair changed fixed ego body')
    if not all(a['ego_velocity_xy'][0] < 0 for a in lrows):
        raise ValueError('Backing side lacks original reverse motion')
    if not all(b['ego_velocity_xy'][0] > 0 for b in rrows):
        raise ValueError('Control side lacks original forward-only motion')
    return {'format': 'worker-activation-comparison-audit', 'passed': True,
            'frames': len(lrows), 'fixed_traffic_source': True,
            'backing_observed': True, 'forward_only_observed': True,
            'legal_acceptance_claimed': False}


def prove_activation_audit():
    base = json.loads((WORK / 'diagnostic-first-primary.json').read_text())
    control = json.loads((STAGE / 'diagnostic-no-reverse-control.json').read_text())
    proof = audit_activation_pair(base, control)
    tampered = json.loads(json.dumps(control))
    rows = [json.loads(line) for line in tampered['files']['backing_motion.jsonl'].splitlines() if line]
    rows[0]['participants']['20']['x_m'] += 1
    tampered['files']['backing_motion.jsonl'] = ''.join(json.dumps(row) + '\n' for row in rows)
    try:
        audit_activation_pair(base, tampered)
    except ValueError as error:
        if 'fixed source' not in str(error):
            raise
    else:
        raise ValueError('Changed traffic source was not rejected')
    rows[0]['participants']['20']['x_m'] -= 1
    for row in rows:
        row['ego_velocity_xy'] = [-2, 0]
    tampered['files']['backing_motion.jsonl'] = ''.join(json.dumps(row) + '\n' for row in rows)
    try:
        audit_activation_pair(base, tampered)
    except ValueError as error:
        if 'forward-only' not in str(error):
            raise
    else:
        raise ValueError('Absent activation difference was not rejected')
    return proof


def main():
    source = json.loads((WORK / 'diagnostic-first-primary.json').read_text())
    capture = json.loads(source['files']['capture/manifest.json'])
    capture['case_id'] = CASE
    source['files']['capture/manifest.json'] = json.dumps(capture, indent=2) + '\n'
    rows = [json.loads(line) for line in source['files']['backing_motion.jsonl'].splitlines() if line]
    for index, row in enumerate(rows):
        row['ego']['x_m'] = 20 + index
        row['ego_velocity_xy'] = [2, 0]
    source['files']['backing_motion.jsonl'] = ''.join(json.dumps(row) + '\n' for row in rows)
    diagnostic = STAGE / 'diagnostic-no-reverse-control.json'
    diagnostic_sha = write(diagnostic, source)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': str(diagnostic.relative_to(ROOT)),
                           'sha256': diagnostic_sha}],
              'generator': {'source': str(diagnostic.relative_to(ROOT)), 'sha256': diagnostic_sha}}
    recipe_path = STAGE / 'diagnostic-recipe-no-reverse-control.json'
    write(recipe_path, recipe)

    manifest = json.loads((STAGE / 'execution-manifest.json').read_text())
    base_entry = next(entry for entry in manifest['cases'] if entry['case_id'] == BASE)
    base = json.loads((STAGE / base_entry['construction']).read_text())
    construction = json.loads(json.dumps(base))
    construction['case_id'] = CASE
    construction['mechanisms'].append('Forward-only Native control with original signed ego velocity proves activation control')
    for file in construction['files']:
        if file['path'] == 'config.json':
            config = json.loads(file['content'])
            config['selected_case_id'] = CASE
            config['supported_case_ids'] = [CASE]
            config['case']['case_id'] = CASE
            config['forward_throttle'] = .2
            file['content'] = json.dumps(config, indent=2) + '\n'
        elif file['path'] == 'runner.py':
            runner = file['content'].replace("'backing_near_vehicle'}", "'backing_near_vehicle','no_reverse_control'}")
            anchor = "if config.get('other_throttle',.15) not in (.15,.25):"
            runner = runner.replace(anchor,
                "if config.get('forward_throttle',.2) not in (.1,.2,.3):\n"
                "        raise ValueError('Unsupported forward throttle')\n    " + anchor)
            pattern = (r"            request=command\(\(loc.x,loc.y\).*?"
                       r"steer=request\['steer'\],reverse=True\)\)")
            replacement = ("            ego.apply_control(carla.VehicleControl("
                           "throttle=config.get('forward_throttle',.2),brake=0,steer=0,reverse=False))")
            runner, count = re.subn(pattern, replacement, runner, flags=re.S)
            if count != 1 or 'no_reverse_control' not in runner:
                raise ValueError('Forward-only runner patch did not match once')
            file['content'] = runner
        elif file['path'] == 'backing_finalizer.py':
            finalizer = file['content']
            finalizer = finalizer.replace(
                "'measured':observed['backing_onset_frame'],'method':'original signed longitudinal speed',",
                "'measured':sum(row['backing_observed'] for row in observed['observations']),"
                "'method':'original signed longitudinal speed across the full window',")
            if finalizer == file['content']:
                raise ValueError('Forward-only target check patch did not match')
            file['content'] = finalizer

    contract = json.loads((WORK / 'measurement-first-primary.json').read_text())
    contract['case_id'] = CASE
    contract_path = STAGE / 'measurement-no-reverse-control.json'
    write(contract_path, contract)
    entry = {key: json.loads(json.dumps(value)) for key, value in base_entry.items() if key != 'candidates'}
    entry.update(case_id=CASE, measurement_contract=contract_path.name,
                 fixture_recipe=str(recipe_path.relative_to(ROOT)),
                 candidate_risk={'status': 'physical', 'reason': 'Native forward-only movement and camera coverage require original source readback.'},
                 candidates=[])
    alternatives = [
        ('fallback1', '.1', 'signed forward speed', 'movement is too fast to retain the full control window'),
        ('fallback2', '.3', 'signed forward speed', 'movement is too slow to establish forward activation'),
        ('fallback3', '2', 'overview camera coverage', 'forward actor leaves the overview source stream'),
    ]
    for candidate, value, metric, failure in [('primary', '.2', '', '')] + alternatives:
        alternate = json.loads(json.dumps(construction))
        config_file = next(file for file in alternate['files'] if file['path'] == 'config.json')
        config = json.loads(config_file['content'])
        knob = 'overview_height_delta_m' if candidate == 'fallback3' else 'forward_throttle'
        config[knob] = int(value) if candidate == 'fallback3' else float(value)
        config_file['content'] = json.dumps(config, indent=2) + '\n'
        path = STAGE / f'construction-no-reverse-{candidate}.json'
        digest = write(path, alternate)
        if candidate == 'primary':
            entry['construction'] = path.name
            entry['construction_sha256'] = digest
        else:
            entry['candidates'].append({'id': candidate, 'construction': path.name,
                                        'construction_sha256': digest,
                                        'trigger': {'source': 'original 20 Hz signed ego motion and four camera streams',
                                                    'metric': metric, 'failure_condition': failure},
                                        'changed_knobs': [f'{knob}: {value}']})
    manifest['cases'] = [case for case in manifest['cases'] if case['case_id'] != CASE] + [entry]
    write(STAGE / 'execution-manifest.json', manifest)
    plan = json.loads((STAGE / 'case-plan.json').read_text())
    disposition = plan['requirement_dispositions'][0]
    disposition['case_ids'] = sorted(set(disposition['case_ids']) | {CASE})
    for case in plan['cases']:
        if case['case_id'] == CASE:
            case['construction_status'] = 'staged_unproven'
    write(STAGE / 'case-plan.json', plan)
    proposal_path = STAGE / 'proposals/cases.json'
    proposal = json.loads(proposal_path.read_text())
    proposal['cases'] = [case for case in proposal['cases'] if case['case_id'] != CASE]
    case = json.loads(json.dumps(next(case for case in proposal['cases'] if case['case_id'] == BASE)))
    case.update(case_id=CASE,
                rationale='Same corridor and other traffic with measured forward-only ego activation; no safety judgment inferred',
                variable_assignments={'ego_motion': 'forward only'})
    proposal['cases'].append(case)
    write(proposal_path, proposal)
    return {'case_id': CASE, 'diagnostic_sha256': diagnostic_sha,
            'candidate_hashes': [entry['construction_sha256']] + [x['construction_sha256'] for x in entry['candidates']]}


if __name__ == '__main__':
    print(json.dumps({'construction': main(), 'comparison_audit': prove_activation_audit()}, indent=2))
