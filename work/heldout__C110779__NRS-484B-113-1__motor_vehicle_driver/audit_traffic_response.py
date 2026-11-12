"""Independent source comparison for the fixed backing route and traffic response."""

from hashlib import sha256
import json
from pathlib import Path


WORK = Path(__file__).resolve().parent
CLEAR = WORK.name + '__backing_clear_vehicle'
BRAKES = WORK.name + '__backing_vehicle_brakes'


def rows(source):
    return [json.loads(line) for line in source.splitlines() if line.strip()]


def audit(clear, braking):
    a, b = clear['files'], braking['files']
    if (set(a), set(b), clear['graphs'], braking['graphs'], clear['videos'], braking['videos']) != (
            set(a), set(a), clear['graphs'], clear['graphs'], clear['videos'], clear['videos']):
        raise ValueError('Backing comparison fixed source inventory differs')
    ca, cb = json.loads(a['capture/manifest.json']), json.loads(b['capture/manifest.json'])
    if ca.get('case_id') != CLEAR or cb.get('case_id') != BRAKES:
        raise ValueError('Backing comparison case identities differ')
    ca['case_id'] = cb['case_id']
    if ca != cb:
        raise ValueError('Backing comparison capture conditions differ')
    for name in a:
        if name not in ('capture/manifest.json', 'backing_motion.jsonl') and a[name] != b[name]:
            raise ValueError('Backing comparison fixed original differs: ' + name)
    ma, mb = rows(a['backing_motion.jsonl']), rows(b['backing_motion.jsonl'])
    if len(ma) != len(mb) or len(ma) < 3:
        raise ValueError('Backing comparison motion history incomplete')
    speeds_a, speeds_b = [], []
    for original, response in zip(ma, mb):
        if set(original['participants']) != {'20'} or set(response['participants']) != {'20'}:
            raise ValueError('Backing comparison traffic identities differ')
        pa, pb = original.pop('participants'), response.pop('participants')
        if original != response:
            raise ValueError('Backing comparison ego motion or frame differs')
        for key in ('y_m', 'body_radius_m'):
            if pa['20'][key] != pb['20'][key]:
                raise ValueError('Backing comparison traffic fixed geometry differs')
        speeds_a.append(pa['20']['speed_mps'])
        speeds_b.append(pb['20']['speed_mps'])
    decel_a = min((speeds_a[i] - speeds_a[i-1]) / .05 for i in range(1, len(speeds_a)))
    decel_b = min((speeds_b[i] - speeds_b[i-1]) / .05 for i in range(1, len(speeds_b)))
    if decel_a != 0 or decel_b >= decel_a:
        raise ValueError('Backing comparison lacks distinct sampled traffic deceleration')
    return {'format': 'worker-backing-traffic-response-comparison',
            'fixed_source_inventory_sha256': sha256(''.join(sorted(a)).encode()).hexdigest(),
            'case_ids': [CLEAR, BRAKES],
            'baseline_min_sampled_acceleration_mps2': decel_a,
            'braking_min_sampled_acceleration_mps2': decel_b,
            'legal_interference_judgment': None,
            'physical_acceptance_claimed': False}


def main():
    clear = json.loads((WORK / 'diagnostic-clear-audit.json').read_text())
    braking = json.loads((WORK / 'diagnostic-braking-vehicle.json').read_text())
    proof = audit(json.loads(json.dumps(clear)), json.loads(json.dumps(braking)))
    changed = json.loads(json.dumps(braking))
    motion = rows(changed['files']['backing_motion.jsonl'])
    motion[0]['ego']['x_m'] += 1
    changed['files']['backing_motion.jsonl'] = ''.join(json.dumps(row) + '\n' for row in motion)
    try:
        audit(json.loads(json.dumps(clear)), changed)
    except ValueError as error:
        if 'ego motion' not in str(error):
            raise
    else:
        raise AssertionError('Changed ego motion was accepted')
    changed = json.loads(json.dumps(braking))
    changed['files']['backing_motion.jsonl'] = clear['files']['backing_motion.jsonl']
    try:
        audit(json.loads(json.dumps(clear)), changed)
    except ValueError as error:
        if 'lacks distinct' not in str(error):
            raise
    else:
        raise AssertionError('Missing response difference was accepted')
    proof['negative_fixed_ego_rejected'] = True
    proof['negative_missing_response_rejected'] = True
    (WORK / 'traffic-response-comparison-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
