"""Independent contact comparison over original fixture source packets."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / '.runtime-work/c110779-native-stage'
PREFIX = 'heldout__C110779__NRS-484B-113-1__motor_vehicle_driver__'


def rows(text):
    return [json.loads(line) for line in text.splitlines() if line]


def check(near, contact, near_receipt, contact_receipt):
    near, contact = json.loads(json.dumps(near)), json.loads(json.dumps(contact))
    if set(near['files']) != set(contact['files']):
        raise ValueError('Contact comparison source inventory differs')
    for spec, suffix in ((near, 'backing_near_vehicle'),
                         (contact, 'backing_vehicle_contact')):
        capture = json.loads(spec['files']['capture/manifest.json'])
        if capture.get('case_id') != PREFIX + suffix:
            raise ValueError('Contact comparison case identity differs')
        capture['case_id'] = 'CONTROLLED_CASE'
        spec['files']['capture/manifest.json'] = json.dumps(capture, sort_keys=True)
    original = rows(near['files']['backing_contacts.jsonl'])
    changed = rows(contact['files']['backing_contacts.jsonl'])
    if len(original) != len(changed):
        raise ValueError('Contact packet frame count differs')
    for old, new in zip(original, changed):
        if (old['frame'], old['time_s']) != (new['frame'], new['time_s']):
            raise ValueError('Contact packet frame join differs')
    near['files'].pop('backing_contacts.jsonl')
    contact['files'].pop('backing_contacts.jsonl')
    if near != contact:
        raise ValueError('Undeclared contact comparison source differs')
    before = [r['frame'] for r in original if r['contact_actor_ids']]
    after = [r['frame'] for r in changed if r['contact_actor_ids'] == ['20']]
    if before or after != [38038]:
        raise ValueError('Declared synthetic contact packet absent')
    for receipt, suffix in ((near_receipt, 'backing_near_vehicle'),
                            (contact_receipt, 'backing_vehicle_contact')):
        if receipt.get('case_id') != PREFIX + suffix or not receipt.get('passed'):
            raise ValueError('Exact compatibility receipt missing')
    measured = contact_receipt['measurement_examples']['backing_safety_observation']['value']
    if measured['contact_frames_during_backing'] != after:
        raise ValueError('Original contact was not measured during backing')
    return {'format': 'worker-comparison-cpu-audit',
            'comparison_id': 'contact_observation',
            'source_packets_fixed_except_contact': True,
            'synthetic_contact_frames': after,
            'legal_safety_claimed': False, 'physical_acceptance_claimed': False}


def load(path):
    return json.loads(path.read_text())


def main():
    near = load(STAGE / 'diagnostic-near-vehicle.json')
    contact = load(ROOT / 'work/heldout__C110779__NRS-484B-113-1__motor_vehicle_driver/diagnostic-contact-vehicle.json')
    near_receipt = load(STAGE / 'compat-near-primary/compatibility.json')
    contact_receipt = load(STAGE / 'compat-contact-primary-v2/compatibility.json')
    result = check(near, contact, near_receipt, contact_receipt)
    print(json.dumps(result, indent=2))
    bad = json.loads(json.dumps(contact))
    bad['files']['backing_motion.jsonl'] += ' '
    try:
        check(near, bad, near_receipt, contact_receipt)
    except ValueError as error:
        if str(error) != 'Undeclared contact comparison source differs':
            raise
    else:
        raise AssertionError('Changed fixed motion was not rejected')
    bad_receipt = json.loads(json.dumps(contact_receipt))
    bad_receipt['measurement_examples']['backing_safety_observation']['value']['contact_frames_during_backing'] = []
    try:
        check(near, contact, near_receipt, bad_receipt)
    except ValueError as error:
        if str(error) != 'Original contact was not measured during backing':
            raise
    else:
        raise AssertionError('Missing measured contact was not rejected')


if __name__ == '__main__':
    main()
