"""Independent source-bound comparison of two measured scooter path runs.

This audit checks the controlled difference and provenance; it issues no legal verdict.
"""
import argparse
import json
from pathlib import Path

AID = 'training__C230224__NRS-484B-785-1a__cycle_or_scooter_operator'


def audit(low, high, original_only=True):
    if low.get('case_id') != AID + '__controlled_1' or high.get('case_id') != AID + '__controlled_2':
        raise ValueError('Comparison case identities differ')
    if not (0 < low.get('requested_speed_mps', 0) < 15*.44704 < high.get('requested_speed_mps', 0) <= 20*.44704):
        raise ValueError('Comparison requested-speed sources differ')
    if any(x.get('format') != 'source-bound-scooter-path-speed-v1' or
           x.get('assignment_id') != AID or x.get('samples') != 600 or
           x.get('physical_acceptance_claimed') is not False or
           x.get('legal_result') is not None for x in (low, high)):
        raise ValueError('Wrong comparison measurement contract')
    if original_only and any(x.get('review_kind') != 'original_source_review' for x in (low, high)):
        raise ValueError('Original Native measurements required')
    if low.get('fixed_context') != high.get('fixed_context'):
        raise ValueError('Comparison fixed path, device or ordinance context differs')
    if any(x.get('path_center_frames') != 600 for x in (low, high)):
        raise ValueError('Scooter path occupancy incomplete')
    if low.get('above_15_mph_frames') != 0:
        raise ValueError('Lower-speed case crosses 15 mph')
    if high.get('above_15_mph_frames') != 600:
        raise ValueError('Higher-speed case does not stay above 15 mph')
    if not low.get('max_speed_mph', 0) < 15 < high.get('min_speed_mph', 0):
        raise ValueError('Measured continuous speed separation missing')
    for x in (low, high):
        sources = x.get('source_sha256', {})
        required = {'video_frames.jsonl', 'native_rider_trace.jsonl', 'scooter_context.json'}
        if original_only:
            required |= {'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'}
        if not required <= set(sources) or any(len(sources[k]) != 64 for k in required):
            raise ValueError('Comparison original source hashes missing')
    return {'format': 'scooter-speed-comparison-audit-v1', 'assignment_id': AID,
            'fixed_context_checked': True, 'source_bound': True,
            'low_max_mph': low['max_speed_mph'], 'high_min_mph': high['min_speed_mph'],
            'legal_result': None, 'physical_acceptance_claimed': False}


def audit_boundary(low, at_cap, high, original_only=True):
    pair = audit(low, high, original_only=original_only)
    if at_cap.get('case_id') != AID + '__controlled_at_cap' or \
            abs(at_cap.get('requested_speed_mps', -1) - 15*.44704) > 1e-9:
        raise ValueError('At-cap case must bind an exact 15 mph request')
    if (at_cap.get('format') != low.get('format') or
            at_cap.get('assignment_id') != AID or
            at_cap.get('fixed_context') != low.get('fixed_context') or
            at_cap.get('samples') != 600 or at_cap.get('path_center_frames') != 600 or
            at_cap.get('physical_acceptance_claimed') is not False or
            at_cap.get('legal_result') is not None):
        raise ValueError('At-cap case differs in fixed source conditions')
    if original_only and at_cap.get('review_kind') != 'original_source_review':
        raise ValueError('At-cap original Native measurement required')
    source = at_cap.get('source_sha256', {})
    required = {'video_frames.jsonl', 'native_rider_trace.jsonl', 'scooter_context.json'}
    if original_only:
        required |= {'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'}
    if not required <= set(source) or any(len(source[k]) != 64 for k in required):
        raise ValueError('At-cap original source hashes missing')
    return {**pair, 'format': 'scooter-speed-boundary-audit-v1',
            'requested_at_cap_mph': 15,
            'at_cap_measured_min_mph': at_cap['min_speed_mph'],
            'at_cap_measured_max_mph': at_cap['max_speed_mph'],
            'at_cap_above_15_mph_frames': at_cap['above_15_mph_frames'],
            'at_cap_legal_classification': None}


def audit_selected_pair(first, second, comparison_id, original_only=True):
    """Audit one frozen ordered speed pair without assigning a legal result."""
    pairs = {
        AID + '__comparison': ('controlled_1', 'controlled_2'),
        AID + '__below_vs_requested_at_cap': ('controlled_1', 'controlled_at_cap'),
        AID + '__requested_at_cap_vs_above': ('controlled_at_cap', 'controlled_2'),
    }
    if comparison_id not in pairs:
        raise ValueError('Unknown selected scooter comparison')
    suffix_a, suffix_b = pairs[comparison_id]
    if first.get('case_id') != AID + '__' + suffix_a or second.get('case_id') != AID + '__' + suffix_b:
        raise ValueError('Comparison case identities differ')
    expected_a, expected_b = {'controlled_1': 12, 'controlled_at_cap': 15,
                              'controlled_2': 17}[suffix_a], {'controlled_1': 12,
                              'controlled_at_cap': 15, 'controlled_2': 17}[suffix_b]
    for item, expected in ((first, expected_a), (second, expected_b)):
        if item.get('format') != 'source-bound-scooter-path-speed-v1' or item.get('assignment_id') != AID:
            raise ValueError('Wrong comparison measurement contract')
        if abs(item.get('requested_speed_mps', -1) - expected*.44704) > 1e-8:
            raise ValueError('Comparison requested-speed sources differ')
        if item.get('samples') != 600 or item.get('path_center_frames') != 600:
            raise ValueError('Scooter path occupancy incomplete')
        if item.get('physical_acceptance_claimed') is not False or item.get('legal_result') is not None:
            raise ValueError('Comparison claims an unsupported result')
        if original_only and item.get('review_kind') != 'original_source_review':
            raise ValueError('Original Native measurements required')
        required = {'video_frames.jsonl', 'native_rider_trace.jsonl', 'scooter_context.json'}
        if original_only:
            required |= {'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'}
        sources = item.get('source_sha256', {})
        if not required <= set(sources) or any(len(sources[name]) != 64 for name in required):
            raise ValueError('Comparison original source hashes missing')
    if first.get('fixed_context') != second.get('fixed_context'):
        raise ValueError('Comparison fixed path, device or ordinance context differs')
    if not first['max_speed_mph'] < second['min_speed_mph']:
        raise ValueError('Measured continuous speed separation missing')
    return {'format': 'scooter-selected-pair-audit-v1', 'assignment_id': AID,
            'comparison_id': comparison_id, 'case_ids': [first['case_id'], second['case_id']],
            'requested_speeds_mph': [expected_a, expected_b],
            'measured_extrema_mph': [first['max_speed_mph'], second['min_speed_mph']],
            'fixed_context_checked': True, 'original_source_required': original_only,
            'legal_result': None, 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--low', type=Path, required=True)
    parser.add_argument('--high', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--comparison-id')
    args = parser.parse_args()
    first, second = json.loads(args.low.read_text()), json.loads(args.high.read_text())
    result = audit_selected_pair(first, second, args.comparison_id,
                                 original_only=not args.diagnostic) if args.comparison_id else \
             audit(first, second, original_only=not args.diagnostic)
    print(json.dumps(result, sort_keys=True))
