"""CPU-only independent source audit for one exact rider delivery case."""
import argparse
import json
from pathlib import Path

from rider_delivery_audit import audit_attempt
from rider_device_delivery_audit import audit as audit_device
from rider_safety_delivery_audit import audit as audit_safety
from turn_lane_delivery_audit import audit as audit_lane
from both_hands_delivery_audit import audit as audit_hands

PREFIX = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__'


def audit(attempt, case, *, negative=False):
    root = Path(attempt)
    report = json.loads((root / 'analysis-report.json').read_text())
    if report.get('case_id') != case or not case.startswith(PREFIX):
        raise ValueError('Wrong exact rider audit case')
    if negative:
        report = json.loads(json.dumps(report))
        report['measurements']['rider_turn_signal_observation']['sources']['rider_arm_bones.jsonl'] = '0' * 64
    slug = case[len(PREFIX):]
    if slug == 'electric_bicycle_signal_once':
        return audit_device(root, report, 'electric_bicycle')
    if slug == 'electric_scooter_signal_once':
        return audit_device(root, report, 'electric_scooter')
    if slug in ('safety_wide','safety_narrow'):
        return audit_safety(root, report)
    if slug == 'turn_lane_no_signal':
        return audit_lane(root, report)
    if slug == 'both_hands_no_signal':
        return audit_hands(root, report)
    if slug in ('bicycle_signal_once','bicycle_no_signal','bicycle_signal_continuous'):
        return audit_attempt(root, report)
    raise ValueError('Unknown exact rider audit case')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    receipt = audit(args.attempt, args.case, negative=args.negative)
    print(json.dumps({'case_id': args.case,
                      'source_integrity_passed': receipt['source_integrity_passed'],
                      'physical_visibility_verified': False,
                      'legal_acceptance_claimed': False}))
