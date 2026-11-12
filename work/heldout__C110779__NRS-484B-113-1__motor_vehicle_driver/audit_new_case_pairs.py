"""Independent source comparisons for activation and pedestrian exact cases.

This checks source-shaped software fixtures. Actual Native motion and visibility
must be checked against captured originals after local execution.
"""

import json
from pathlib import Path

WORK = Path(__file__).resolve().parent
PREFIX = WORK.name + '__'


def rows(spec):
    return [json.loads(line) for line in spec['files']['backing_motion.jsonl'].splitlines() if line]


def capture_id(spec, expected):
    if json.loads(spec['files']['capture/manifest.json']).get('case_id') != PREFIX + expected:
        raise ValueError('Exact capture case identity differs')


def audit_activation(base, control):
    capture_id(base, 'backing_clear_vehicle')
    capture_id(control, 'no_reverse_control')
    a, b = base['files'], control['files']
    if set(a) != set(b) or base['graphs'] != control['graphs'] or base['videos'] != control['videos']:
        raise ValueError('Activation fixed source inventory differs')
    for name in a:
        if name not in ('capture/manifest.json', 'backing_motion.jsonl') and a[name] != b[name]:
            raise ValueError('Activation fixed original differs: ' + name)
    left, right = rows(base), rows(control)
    if len(left) != len(right) or not left:
        raise ValueError('Activation frame history differs')
    for old, new in zip(left, right):
        for key in ('frame', 'time_s', 'ego_heading_xy', 'participants'):
            if old[key] != new[key]:
                raise ValueError('Activation fixed source differs: ' + key)
        for key in ('y_m', 'body_radius_m'):
            if old['ego'][key] != new['ego'][key]:
                raise ValueError('Activation fixed ego geometry differs')
        if old['ego_velocity_xy'][0] >= 0 or new['ego_velocity_xy'][0] <= 0:
            raise ValueError('Declared reverse/forward activation difference absent')
    return {'comparison_id': 'backing_activation', 'case_ids': [PREFIX + 'backing_clear_vehicle', PREFIX + 'no_reverse_control'],
            'passed': True, 'frames': len(left), 'physical_acceptance_claimed': False}


def audit_pedestrian(base, crossing):
    capture_id(base, 'backing_clear_vehicle')
    capture_id(crossing, 'backing_pedestrian')
    a, b = base['files'], crossing['files']
    if set(a) != set(b) or base['graphs'] != crossing['graphs'] or base['videos'] != crossing['videos']:
        raise ValueError('Pedestrian fixed source inventory differs')
    for name in a:
        if name not in ('capture/manifest.json', 'backing_context.json', 'backing_motion.jsonl') and a[name] != b[name]:
            raise ValueError('Pedestrian fixed original differs: ' + name)
    old_context = json.loads(a['backing_context.json'])
    new_context = json.loads(b['backing_context.json'])
    added = new_context['participants'].pop('30', None)
    if not added or added.get('kind') != 'pedestrian' or new_context != old_context:
        raise ValueError('Pedestrian context is absent or fixed traffic changed')
    left, right = rows(base), rows(crossing)
    if len(left) != len(right) or not left:
        raise ValueError('Pedestrian frame history differs')
    for old, new in zip(left, right):
        person = new['participants'].pop('30', None)
        if person is None or old != new:
            raise ValueError('Pedestrian original body absent or fixed motion changed')
    return {'comparison_id': 'pedestrian_safety', 'case_ids': [PREFIX + 'backing_clear_vehicle', PREFIX + 'backing_pedestrian'],
            'passed': True, 'frames': len(left), 'physical_acceptance_claimed': False}


def main():
    base = json.loads((WORK / 'diagnostic-first-primary.json').read_text())
    control = json.loads((WORK / 'diagnostic-no-reverse-control.json').read_text())
    pedestrian = json.loads((WORK / 'diagnostic-backing-pedestrian.json').read_text())
    proofs = [audit_activation(base, control), audit_pedestrian(base, pedestrian)]
    for name, target, audit in [('activation', control, audit_activation), ('pedestrian', pedestrian, audit_pedestrian)]:
        tampered = json.loads(json.dumps(target))
        samples = rows(tampered)
        samples[0]['participants']['20']['x_m'] += 1
        tampered['files']['backing_motion.jsonl'] = ''.join(json.dumps(row) + '\n' for row in samples)
        try:
            audit(base, tampered)
        except ValueError:
            pass
        else:
            raise AssertionError(name + ' accepted changed fixed traffic')
        proofs[0 if name == 'activation' else 1]['negative_fixed_traffic_rejected'] = True
        missing = json.loads(json.dumps(target))
        if name == 'activation':
            samples = rows(missing)
            for sample in samples:
                sample['ego_velocity_xy'] = [-2, 0]
            missing['files']['backing_motion.jsonl'] = ''.join(json.dumps(row) + '\n' for row in samples)
        else:
            context = json.loads(missing['files']['backing_context.json'])
            context['participants'].pop('30')
            missing['files']['backing_context.json'] = json.dumps(context) + '\n'
        try:
            audit(base, missing)
        except ValueError:
            pass
        else:
            raise AssertionError(name + ' accepted absent declared difference')
        proofs[0 if name == 'activation' else 1]['negative_missing_difference_rejected'] = True
    print(json.dumps({'format': 'worker-new-case-comparison-proofs', 'proofs': proofs}, indent=2))


if __name__ == '__main__':
    main()
