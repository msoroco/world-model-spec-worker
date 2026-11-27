"""Independent saved-only comparison isolation for median-opening packets."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import verify_sources
from case_protocol import ASSIGNMENT, SUFFIXES
from saved_signal_audit import audit as audit_history
from signal_crossing import validate_source_packet
from source_bindings import validate_review_refs


def audit_pair(left: dict, right: dict, *, variable: str):
    if variable not in {'entry_order', 'signal_state', 'crossing_response'}:
        raise ValueError('undeclared comparison variable')
    required = ('map_sha256', 'review_sha256', 'crossing_id', 'ego_route_sha256',
                'other_route_sha256', 'camera_plan_sha256', 'duration_frames',
                'ego_blueprint', 'other_blueprint')
    for key in required:
        if not left.get(key) or left.get(key) != right.get(key):
            raise ValueError(f'fixed condition differs or absent: {key}')
    if left.get('case_id') == right.get('case_id'):
        raise ValueError('comparison repeats one case')
    for report in (left, right):
        if report.get('physical_review_pending') is not True:
            raise ValueError('report lacks physical-review boundary')
        for key in ('ego_entry_frame', 'other_entry_frame', 'signal_states_observed'):
            if key not in report:
                raise ValueError(f'measurement absent: {key}')
    if variable == 'entry_order':
        a = left['other_entry_frame'] < left['ego_entry_frame']
        b = right['other_entry_frame'] < right['ego_entry_frame']
        if a == b:
            raise ValueError('declared entry order did not vary')
    elif variable == 'signal_state':
        if set(left['signal_states_observed']) == set(right['signal_states_observed']):
            raise ValueError('declared signal state did not vary')
        if ((left['other_entry_frame'] < left['ego_entry_frame']) !=
                (right['other_entry_frame'] < right['ego_entry_frame'])):
            raise ValueError('entry order changed in signal comparison')
    else:
        if [left['case_id'], right['case_id']] != [ASSIGNMENT + '__precedence',
                                                  ASSIGNMENT + '__advance']:
            raise ValueError('response comparison needs precedence and advance cases')
        if (not left.get('signal_initial_state') or
                not isinstance(left.get('signal_transition_frames'), list) or
                not left['signal_transition_frames'] or
                set(left['signal_states_observed']) != set(right['signal_states_observed']) or
                left.get('signal_initial_state') != right.get('signal_initial_state') or
                left.get('signal_transition_frames') != right.get('signal_transition_frames')):
            raise ValueError('signal state changed in response comparison')
        for report in (left, right):
            clear = report.get('other_clear_frame')
            if not isinstance(clear, int) or isinstance(clear, bool):
                raise ValueError('measured other clearance absent')
            if not (report['other_entry_frame'] < clear and
                    report['other_entry_frame'] < report['ego_entry_frame']):
                raise ValueError('other-first crossing chronology absent')
        if (left['other_entry_frame'] != right['other_entry_frame'] or
                left['other_clear_frame'] != right['other_clear_frame']):
            raise ValueError('other vehicle entry or clearance changed in response comparison')
        if left['ego_entry_frame'] < left['other_clear_frame']:
            raise ValueError('precedence case did not wait for other clearance')
        if right['ego_entry_frame'] >= right['other_clear_frame']:
            raise ValueError('advance case did not enter before other clearance')
    return {'comparison_variable': variable, 'case_ids': [left['case_id'], right['case_id']],
            'fixed_conditions_checked': list(required), 'physical_review_pending': True,
            'legal_judgment': 'unresolved',
            **({'measured_crossing_response': {
                'precedence_entered_before_other_cleared': False,
                'advance_entered_before_other_cleared': True,
                'precedence_entry_minus_other_clear_frames':
                    left['ego_entry_frame'] - left['other_clear_frame'],
                'advance_entry_minus_other_clear_frames':
                    right['ego_entry_frame'] - right['other_clear_frame']}}
               if variable == 'crossing_response' else {})}


def _source_report(attempt):
    attempt = Path(attempt).resolve()
    if not attempt.is_dir() or attempt.is_symlink():
        raise ValueError('original Native attempt directory missing or redirected')
    selected = json.loads((attempt / 'config.json').read_text()).get('selected_case_id')
    if selected not in {ASSIGNMENT + '__' + suffix for suffix in SUFFIXES}:
        raise ValueError('comparison attempt selects another exact case')
    verify_sources(selected, attempt)
    acquisition = json.loads((attempt / 'acquisition.json').read_text())
    names = ('signal-packet.json', 'signal-history.json', 'review.json',
             'map.xodr', 'source-packet.json', 'reviewed-packet.json',
             'acquisition-provenance.json', 'trace.jsonl', 'video_frames.jsonl')
    for name in names:
        path = attempt / name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(attempt):
            raise ValueError('Missing required source: ' + name)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        entry = acquisition.get(name, {})
        if entry.get('kind') != 'original_native' or entry.get('sha256') != actual:
            raise ValueError('Missing or stale original Native source: ' + name)
    packet = json.loads((attempt / 'signal-packet.json').read_text())
    source_packet = json.loads((attempt / 'source-packet.json').read_text())
    if (attempt / 'source-packet.json').read_bytes() != (attempt / 'reviewed-packet.json').read_bytes():
        raise ValueError('retained reviewed packet differs from original')
    validate_source_packet(source_packet, (attempt / 'map.xodr').read_bytes(),
                           (attempt / 'review.json').read_bytes())
    for ref in validate_review_refs((attempt / 'review.json').read_bytes(), attempt):
        path = attempt / ref['path']
        if acquisition.get(ref['path'], {}).get('sha256') != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError('review source acquisition binding differs')
    if (packet['map_sha256'] != hashlib.sha256((attempt / 'map.xodr').read_bytes()).hexdigest() or
            packet['review_sha256'] != source_packet['review_sha256']):
        raise ValueError('original map/review source binding differs')
    measured = audit_history(packet, (attempt / 'signal-history.json').read_bytes(),
                             packet['case_id'],
                             hashlib.sha256((attempt / 'review.json').read_bytes()).hexdigest())
    report_path = attempt / 'analysis-report.json'
    if report_path.is_file():
        report = json.loads(report_path.read_text())
        value = report.get('measurements', {}).get('signal_crossing', {}).get('value')
        if value != measured:
            raise ValueError('saved analysis differs from independently measured originals')
    return measured


def audit_saved_pair(left_attempt, right_attempt, *, variable):
    return audit_pair(_source_report(left_attempt), _source_report(right_attempt),
                      variable=variable)


def main():
    parser = argparse.ArgumentParser(description='Audit sealed crossing comparison reports')
    parser.add_argument('--left', type=Path)
    parser.add_argument('--right', type=Path)
    parser.add_argument('--left-attempt', type=Path)
    parser.add_argument('--right-attempt', type=Path)
    parser.add_argument('--variable', choices=('entry_order', 'signal_state',
                                               'crossing_response'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.left_attempt and args.right_attempt and not args.left and not args.right:
        report = audit_saved_pair(args.left_attempt, args.right_attempt,
                                  variable=args.variable)
    elif args.left and args.right and not args.left_attempt and not args.right_attempt:
        report = audit_pair(json.loads(args.left.read_text()),
                            json.loads(args.right.read_text()), variable=args.variable)
    else:
        parser.error('supply both reports or both original attempts')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
