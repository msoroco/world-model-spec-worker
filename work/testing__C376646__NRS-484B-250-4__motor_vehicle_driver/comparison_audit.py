"""Independent source comparison for the selected inoperative-signal cases.

Software fixtures exercise the checks; Native source review decides physical
realization and any legal judgment.
"""

import argparse
import hashlib
import json
from pathlib import Path

from inoperative_stop_measurements import analyze


MODES = ('stop_reference_hierarchy', 'other_priority_basis', 'stop_halt_condition')


def _read(path):
    return json.loads(Path(path).read_text())


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit_pair(left, right, mode):
    if mode not in MODES:
        raise ValueError('Named C376646 comparison mode required')
    left, right = Path(left), Path(right)
    a, b = analyze(left), analyze(right)
    ac, bc = _read(left / 'junction_context.json'), _read(right / 'junction_context.json')
    ca, cb = _read(left / 'config.json'), _read(right / 'config.json')
    fixed_context = ('intersection_id', 'native_signal_id', 'other_native_signal_id',
                     'installed_uncovered_vehicular_heads', 'intersection_polygon_xy_m')
    if any(ac.get(k) != bc.get(k) for k in fixed_context):
        raise ValueError('Fixed junction and signal context changed')
    if ac['installed_uncovered_vehicular_heads'] is not True:
        raise ValueError('Installed uncovered source context absent')
    if (ca['rate_hz'], ca['duration_s']) != (cb['rate_hz'], cb['duration_s']):
        raise ValueError('Fixed capture cadence or duration changed')
    if [x['name'] for x in ca['cameras']] != [x['name'] for x in cb['cameras']]:
        raise ValueError('Fixed source cameras changed')
    if _sha(left / 'video_frames.jsonl') != _sha(right / 'video_frames.jsonl'):
        raise ValueError('Fixed original frame map changed')
    for folder in (left, right):
        rows = _rows(folder / 'vehicle_signal_history.jsonl')
        if not rows or any(row.get('signal_state') != 'Off' or
                           row.get('other_signal_state') != 'Off' for row in rows):
            raise ValueError('Original signal history is not all-head Off')
    if mode == 'stop_reference_hierarchy':
        values = (a['selected_stop_boundary'], b['selected_stop_boundary'])
        if not all(x['ego_stopped_before_entry_observed'] for x in (a, b)):
            raise ValueError('Reference comparison lacks observed ego full stop')
        if values[0] == values[1]:
            raise ValueError('Declared stopping reference difference absent')
    else:
        if ac.get('native_map_id') != bc.get('native_map_id') or _sha(left / 'junction_context.json') != _sha(right / 'junction_context.json'):
            raise ValueError('Priority or halt comparison changed fixed stop-line site')
        if a['selected_stop_boundary'] != 'stop_line' or b['selected_stop_boundary'] != 'stop_line':
            raise ValueError('Same marked stopping reference required')
        if mode == 'stop_halt_condition':
            values = (a['ego_stopped_before_entry_observed'], b['ego_stopped_before_entry_observed'])
            if values != (True, False):
                raise ValueError('Declared full-halt versus rolling difference absent')
        else:
            if (ca['actor_routes']['ego']['release_rule'] != 'after_partner_entry' or
                    cb['actor_routes']['ego']['release_rule'] != 'after_other_clear'):
                raise ValueError('Priority release controllers do not isolate the declared basis')
            values = (a['other_body_inside_at_ego_entry_observed'],
                      b['other_completed_stop_before_ego_observed'],
                      b['other_body_inside_at_ego_entry_observed'])
            if values != (True, True, False):
                raise ValueError('Other-priority basis is not isolated in observed sources')
    return {'format': 'worker-inoperative-signal-comparison-audit',
            'mode': mode, 'fixed_context_fields': list(fixed_context),
            'left_case_id': ca['selected_case_id'], 'right_case_id': cb['selected_case_id'],
            'left_source_sha256': _sha(left / 'vehicle_signal_history.jsonl'),
            'right_source_sha256': _sha(right / 'vehicle_signal_history.jsonl'),
            'observed_values': values, 'observed_difference': True,
            'physical_acceptance_claimed': False, 'legal_verdict_asserted': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--left', required=True)
    parser.add_argument('--right', required=True)
    parser.add_argument('--third')
    parser.add_argument('--mode', choices=MODES, required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit_pair(args.left, args.right, args.mode)
    if args.third:
        if args.mode != 'stop_reference_hierarchy':
            raise ValueError('Third source is only valid for stopping-reference hierarchy')
        result = {'comparison_id': args.mode, 'pairs': [result,
                  audit_pair(args.right, args.third, args.mode)],
                  'physical_acceptance_claimed': False}
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
