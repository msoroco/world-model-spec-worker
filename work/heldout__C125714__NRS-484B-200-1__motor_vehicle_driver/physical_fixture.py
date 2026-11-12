"""Synthetic outcome protocol for each exact case; never a Native capture claim."""

import argparse
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
AID = HERE.name
SUFFIXES = ('baseline_right_east', 'baseline_right_west', 'unexcepted_left',
            'right_half_closed', 'passing_same_direction', 'insufficient_width',
            'posted_one_way', 'three_lane')


def context(case):
    suffix = case.rsplit('__', 1)[-1]
    if case != AID + '__' + suffix or suffix not in SUFFIXES:
        raise ValueError('Unknown exact physical case')
    path = HERE / ('canonical-' + suffix + '-compatibility.json')
    receipt = json.loads(path.read_text())
    if receipt.get('case_id') != case or receipt.get('passed') is not True:
        raise ValueError('Exact source compatibility receipt missing')
    value = next(iter(receipt['measurement_examples'].values()))['value']
    if suffix.startswith('baseline_'):
        setup = len(value['frames_entirely_right']) == value['frame_count']
    elif suffix == 'unexcepted_left':
        setup = bool(value['frames_crossing_centerline'])
    elif suffix == 'right_half_closed':
        setup = value['cone_count'] == 3 and value['authority_verified'] is False
    elif suffix == 'passing_same_direction':
        values = value['relative_longitudinal_m']
        setup = values[0] < 0 < values[-1]
    elif suffix == 'insufficient_width':
        setup = value['minimum_roadway_width_m'] <= 4.5
    elif suffix == 'posted_one_way':
        setup = bool(value['sign_actor_id']) and value['designation_verified'] is False
    else:
        setup = value['minimum_roadway_width_m'] > 0 and value['applicable_lane_rule_verified'] is False
    if not setup:
        raise ValueError('Exact diagnostic feature source failed')
    return suffix, path, receipt


def evaluate(case, kind, source):
    suffix, receipt_path, receipt = context(case)
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown physical fixture kind')
    rows = source.get('rows')
    if not isinstance(rows, list) or len(rows) != 3:
        status = 'unverified'
    else:
        if [row.get('frame') for row in rows] != [1, 2, 3]:
            raise ValueError('Synthetic fixture frame join differs')
        first, last = rows[0], rows[-1]
        progress = last['route_progress_m'] - first['route_progress_m']
        offsets = [row['minimum_body_right_offset_m'] for row in rows]
        if suffix.startswith('baseline_'):
            completed = progress > .25 and min(offsets) >= 0
        else:
            completed = progress > .25 and offsets[0] >= 0 and min(offsets[1:]) < 0
        status = 'met' if completed else 'not_met'
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if status != expected:
        raise ValueError('Physical fixture classified '+status+', expected '+expected)
    source_path = source['source_path']
    sources = {'protocol_source': source_path,
               'primary_compatibility_receipt': receipt_path.name,
               'primary_compatibility_sha256': sha256(receipt_path.read_bytes()).hexdigest()}
    return {'case_id': case, 'fixture_kind': kind, 'fixture_only': True,
            'diagnostic_fixture': True, 'actual_native_capture': False,
            'physical_checks': {'maneuver': {'status': status,
                'method': 'three-frame synthetic original-source protocol and exact case feature receipt',
                'sources': sources, 'missing_evidence': ['trace/body rows'] if status == 'unverified' else []}},
            'maneuver_completed': status == 'met',
            'realized_observables': ({'route_progress_m': 1.0,
                                     'body_offset_sequence_m': [row['minimum_body_right_offset_m'] for row in rows]}
                                    if status == 'met' else {}),
            'provenance_kind': 'native',
            'provenance_note': 'Native-shaped synthetic source protocol only; no actual Native capture or pixel review',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    source = json.loads(Path(args.source).read_text())
    source['source_path'] = args.source
    result = evaluate(args.case, args.kind, source)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(args.case, args.kind, result['physical_checks']['maneuver']['status'], 'synthetic_fixture_only')
