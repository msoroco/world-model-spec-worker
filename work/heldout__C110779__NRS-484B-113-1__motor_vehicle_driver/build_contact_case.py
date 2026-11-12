"""Build the contact probe from the narrower-clearance backing case.

Fixture contact is a synthetic packet. The Native collision sensor remains the
only source of a physical contact observation.
"""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
STAGE = ROOT / '.runtime-work/c110779-native-stage'
PREFIX = WORK.name + '__'
NEAR = PREFIX + 'backing_near_vehicle'
CONTACT = PREFIX + 'backing_vehicle_contact'


def write(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n')
    return sha256(path.read_bytes()).hexdigest()


def main():
    near = json.loads((STAGE / 'diagnostic-near-vehicle.json').read_text())
    spec = json.loads(json.dumps(near))
    files = spec['files']
    capture = json.loads(files['capture/manifest.json'])
    capture['case_id'] = CONTACT
    files['capture/manifest.json'] = json.dumps(capture, indent=2) + '\n'
    contacts = [json.loads(line) for line in files['backing_contacts.jsonl'].splitlines() if line]
    contacts[5]['contact_actor_ids'] = ['20']
    files['backing_contacts.jsonl'] = ''.join(json.dumps(row) + '\n' for row in contacts)
    diagnostic = WORK / 'diagnostic-contact-vehicle.json'
    source_sha = write(diagnostic, spec, compact=True)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json',
                           'source': str(diagnostic.relative_to(ROOT)), 'sha256': source_sha}],
              'generator': {'source': str(diagnostic.relative_to(ROOT)), 'sha256': source_sha}}
    recipe_path = WORK / 'diagnostic-recipe-contact-vehicle.json'
    write(recipe_path, recipe)

    manifest = json.loads((STAGE / 'execution-manifest.json').read_text())
    near_entry = next(e for e in manifest['cases'] if e['case_id'] == NEAR)
    base = json.loads((STAGE / near_entry['construction']).read_text())
    construction = json.loads(json.dumps(base))
    construction['case_id'] = CONTACT
    construction['mechanisms'].append(
        'Hold through vehicle at its reviewed near start with Native braking; '
        'only the original collision sensor may establish contact')
    for item in construction['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['selected_case_id'] = CONTACT
            config['supported_case_ids'] = [CONTACT]
            config['case']['case_id'] = CONTACT
            config['hold_other_for_contact'] = True
            config['contact_hold_brake'] = 1.0
            item['content'] = json.dumps(config, indent=2) + '\n'
        elif item['path'] == 'runner.py':
            runner = item['content']
            runner = runner.replace("'backing_near_vehicle'}", "'backing_near_vehicle','backing_vehicle_contact'}")
            anchor = "if config.get('other_throttle',.15) not in (.15,.25):"
            runner = runner.replace(anchor,
                "if config.get('hold_other_for_contact') not in (None,True):\n"
                "        raise ValueError('Unsupported contact hold policy')\n"
                "    if config.get('contact_hold_brake',1.0) not in (.7,1.0):\n"
                "        raise ValueError('Unsupported contact hold brake')\n"
                "    " + anchor)
            anchor = "other.apply_control(carla.VehicleControl(throttle=config.get('other_throttle',.15),steer=0))"
            runner = runner.replace(anchor,
                "other.apply_control(carla.VehicleControl(\n"
                "                throttle=0 if config.get('hold_other_for_contact') else config.get('other_throttle',.15),\n"
                "                brake=config.get('contact_hold_brake',1.0) if config.get('hold_other_for_contact') else 0,steer=0))")
            if runner == item['content'] or 'hold_other_for_contact' not in runner:
                raise ValueError('Contact runner patch failed')
            item['content'] = runner
    construction_path = STAGE / 'construction-contact-primary.json'
    construction_sha = write(construction_path, construction)
    contract = json.loads((STAGE / near_entry['measurement_contract']).read_text())
    contract['case_id'] = CONTACT
    contract_path = STAGE / 'measurement-contact-primary.json'
    write(contract_path, contract)
    entry = {key: json.loads(json.dumps(value)) for key, value in near_entry.items()
             if key != 'candidates'}
    entry.update(case_id=CONTACT, construction=construction_path.name,
                 construction_sha256=construction_sha,
                 measurement_contract=contract_path.name,
                 fixture_recipe=str(recipe_path.relative_to(ROOT)),
                 candidate_risk={'status': 'physical', 'reason':
                    'A held through vehicle may not yield a Native collision packet during backing.'},
                 candidates=[])
    for fallback in near_entry['candidates']:
        source = json.loads((STAGE / fallback['construction']).read_text())
        source_config = json.loads(next(f['content'] for f in source['files']
                                        if f['path'] == 'config.json'))
        alternate = json.loads(json.dumps(construction))
        config_item = next(f for f in alternate['files'] if f['path'] == 'config.json')
        config = json.loads(config_item['content'])
        for knob in ('target_reverse_speed_mps', 'overview_height_delta_m'):
            if knob in source_config:
                config[knob] = source_config[knob]
        if fallback['id'] == 'fallback2':
            config['contact_hold_brake'] = .7
        config_item['content'] = json.dumps(config, indent=2) + '\n'
        alternate['mechanisms'].append('Shared engineering ' + fallback['id'])
        path = STAGE / ('construction-contact-' + fallback['id'] + '.json')
        digest = write(path, alternate)
        trigger = fallback['trigger']
        knobs = fallback['changed_knobs']
        if fallback['id'] == 'fallback2':
            trigger = {'source': 'original other-vehicle motion and collision sensor',
                       'metric': 'through-vehicle displacement during held contact probe',
                       'failure_condition': 'full hold brake stalls traffic before the reviewed backing contact window'}
            knobs = ['contact_hold_brake: 0.7']
        entry['candidates'].append({'id': fallback['id'], 'construction': path.name,
                                    'construction_sha256': digest,
                                    'trigger': trigger, 'changed_knobs': knobs})
    manifest['cases'] = [e for e in manifest['cases'] if e['case_id'] != CONTACT]
    manifest['cases'].append(entry)
    write(STAGE / 'execution-manifest.json', manifest)
    plan = json.loads((STAGE / 'case-plan.json').read_text())
    disposition = plan['requirement_dispositions'][0]
    disposition['case_ids'] = sorted(set(disposition['case_ids']) | {CONTACT})
    for case in plan['cases']:
        if case['case_id'] == CONTACT:
            case['construction_status'] = 'staged_offline_proven'
    write(STAGE / 'case-plan.json', plan)
    proposal_path = STAGE / 'proposals/cases.json'
    proposal = json.loads(proposal_path.read_text())
    proposal['cases'] = [case for case in proposal['cases'] if case['case_id'] != CONTACT]
    case = json.loads(json.dumps(next(case for case in proposal['cases']
                                     if case['case_id'] == NEAR)))
    case['case_id'] = CONTACT
    case['rationale'] = ('Same near backing route, with a held other vehicle and '
                         'an original Native collision sensor; contact is observed, not presumed')
    case['variable_assignments'] = {'hold_other_for_contact': True}
    proposal['cases'].append(case)
    write(proposal_path, proposal)
    return {'case_id': CONTACT, 'construction_sha256': construction_sha,
            'diagnostic_sha256': source_sha,
            'fallbacks': {e['id']: e['construction_sha256'] for e in entry['candidates']}}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
