"""Independently compare two sealed original packets and their controlled variable."""
import argparse
import hashlib
import json
from pathlib import Path

from contest_aid import CASES, SOURCE_FIELDS
from native_source import AID

DIFFERENCES = {
    'cue': ('start_cue_candidate_contest', 'no_cue_candidate_contest', 'cue'),
    'episode': ('start_cue_candidate_contest', 'start_cue_no_contest', 'candidate_contest'),
    'highway': ('start_cue_candidate_contest', 'start_cue_off_highway', 'highway'),
}
IDENTITY = ('ego_person_id', 'other_person_id', 'ego_vehicle_id', 'other_vehicle_id',
            'ego_route_xy', 'other_route_xy', 'lane_marking_xy',
            'municipal_jurisdiction', 'cue_frame', 'other_start_frame')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(attempt, suffix):
    root = Path(attempt).resolve()
    packet_path = root / 'contest-packet.json'
    receipt_path = root / 'original-source-receipt.json'
    if not packet_path.is_file() or not receipt_path.is_file():
        raise ValueError('original contest packet and receipt required')
    packet = json.loads(packet_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    if (packet.get('assignment_id') != AID or packet.get('case_id') != AID + '__' + suffix or
            receipt.get('case_id') != packet['case_id'] or
            receipt.get('packet_sha256') != sha(packet_path) or
            receipt.get('source_kind') != 'original_native_capture' or
            receipt.get('diagnostic_fixture') is not False):
        raise ValueError('sealed original case or receipt differs')
    rows = packet.get('frames')
    if not isinstance(rows, list) or len(rows) != 900:
        raise ValueError('900 original comparison frames required')
    first = rows[0].get('native_frame')
    for index, row in enumerate(rows):
        if (row.get('original_frame') != index or row.get('native_frame') != first + index or
                row.get('highway') is not packet['scene']['highway'] or
                row.get('candidate_contest') is not packet['scene']['candidate_contest']):
            raise ValueError('original frame/context chain differs')
    return packet, receipt, {'packet_sha256': sha(packet_path),
                             'receipt_sha256': sha(receipt_path)}


def audit(comparison, left, right):
    if comparison not in DIFFERENCES:
        raise ValueError('unknown fixed comparison')
    a, b, variable = DIFFERENCES[comparison]
    left, _, left_source = load(left, a)
    right, _, right_source = load(right, b)
    ls, rs = left['scene'], right['scene']
    for name in IDENTITY:
        if ls.get(name) != rs.get(name):
            raise ValueError('fixed comparison condition changed: ' + name)
    for name in SOURCE_FIELDS:
        if name in ('cue_conduct', 'cue_timing') and variable == 'cue':
            continue
        if name == 'contest_episode' and variable == 'candidate_contest':
            continue
        if name == 'highway_status' and variable == 'highway':
            continue
        if ls.get(name + '_source_sha256') != rs.get(name + '_source_sha256'):
            raise ValueError('fixed source changed: ' + name)
    for name in ('cue', 'candidate_contest', 'highway'):
        if name == variable:
            if ls.get(name) is rs.get(name):
                raise ValueError('declared comparison difference absent: ' + name)
        elif ls.get(name) is not rs.get(name):
            raise ValueError('undeclared comparison difference: ' + name)
    cue_a = [i for i, row in enumerate(left['frames']) if row.get('cue_observed') is True]
    cue_b = [i for i, row in enumerate(right['frames']) if row.get('cue_observed') is True]
    if cue_a != ([ls['cue_frame']] if ls['cue'] else []) or \
            cue_b != ([rs['cue_frame']] if rs['cue'] else []):
        raise ValueError('original cue realization differs')
    return {'format': 'worker-independent-comparison-audit', 'comparison_id': comparison,
            'assignment_id': AID, 'case_ids': [left['case_id'], right['case_id']],
            'fixed_conditions_checked': list(IDENTITY),
            'deliberate_difference': variable,
            'sources': {'left': left_source, 'right': right_source},
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
            'limitations': ['The source comparison does not decide contest, aid or abet.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', choices=DIFFERENCES, required=True)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior comparison audit')
    args.output.write_text(json.dumps(audit(args.comparison, args.left, args.right), indent=2) + '\n')
