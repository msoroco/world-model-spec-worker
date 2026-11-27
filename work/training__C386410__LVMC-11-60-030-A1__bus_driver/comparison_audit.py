"""Independent source-bound comparison of two Native bus standing attempts.

The comparison checks isolation and measured events; it assigns no legal result.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / 'analysis'))
from bus_standing import measure_saved

FIXED = ('vehicle_class', 'route_id', 'street_id', 'controller_policy',
         'weather_policy', 'capture_profile')
ZONE_PAIRS = {
    'location_terminus': ('route_destination', 'other_street'),
    'location_bus_stop': ('bus_stop', 'other_street'),
    'location_bus_stand': ('bus_stand', 'other_street'),
    'location_origin': ('route_origin', 'other_street'),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(left, right, comparison_id, *, source_kind='original_native'):
    if comparison_id not in ZONE_PAIRS:
        raise ValueError('unknown exact bus comparison')
    left, right = Path(left), Path(right)
    measured = [measure_saved(root, source_kind=source_kind) for root in (left, right)]
    contexts = [json.loads((root / 'bus-context.json').read_text()) for root in (left, right)]
    for key in FIXED:
        if not contexts[0].get(key) or contexts[0].get(key) != contexts[1].get(key):
            raise ValueError('fixed comparison condition differs: ' + key)
    actual = tuple(context['zone']['kind'] for context in contexts)
    if actual != ZONE_PAIRS[comparison_id]:
        raise ValueError('declared location difference absent or reversed')
    if contexts[0]['zone']['id'] == contexts[1]['zone']['id']:
        raise ValueError('distinct zone identities required')
    for root, result in zip((left, right), measured):
        if result['stationary_frames'] <= 0 or result['zone_occupied_frames'] <= 0:
            raise ValueError('observed stationary event or zone occupancy absent')
        if result['source_kind'] != source_kind:
            raise ValueError('source provenance differs')
    return {'format': 'bus-standing-comparison-audit-v1',
            'comparison_id': comparison_id, 'passed': True,
            'fixed_conditions': list(FIXED), 'deliberate_difference': 'zone.kind',
            'observed_zone_kinds': list(actual),
            'measurements': measured,
            'context_sha256': [digest(root / 'bus-context.json') for root in (left, right)],
            'legal_judgment': 'unresolved', 'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--left', required=True)
    parser.add_argument('--right', required=True)
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.left, args.right, args.comparison)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
