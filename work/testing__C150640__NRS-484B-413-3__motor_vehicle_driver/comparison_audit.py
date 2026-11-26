"""Independent original-only stop/decrease, signal order and rear-driver contrasts."""
from __future__ import annotations

import json
from pathlib import Path

AID = 'testing__C150640__NRS-484B-413-3__motor_vehicle_driver'
PAIRS = {
    'stop_signal_order': ('stop_signal_before', 'stop_signal_after'),
    'decrease_signal_order': ('decrease_signal_before', 'decrease_signal_after'),
    'stop_vs_decrease': ('stop_signal_before', 'decrease_signal_before'),
    'rear_driver_presence': ('stop_signal_before', 'stop_no_rear_driver'),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit_pair(comparison_id, reports):
    suffixes = PAIRS.get(comparison_id)
    require(suffixes is not None, 'unknown rear-signal comparison')
    case_ids = [AID + '__' + suffix for suffix in suffixes]
    left, right = (reports.get(case_id) for case_id in case_ids)
    for case_id, report in zip(case_ids, (left, right)):
        require(isinstance(report, dict) and report.get('format') == 'worker-delivery-audit' and
                report.get('passed') is True and report.get('protocol_fixture_checked') is False and
                report.get('case_id') == case_id and report.get('frame_count') == 900 and
                report.get('physical_acceptance_claimed') is True and
                report.get('comparison_record', {}).get('source_kind') == 'original_native_capture',
                'original accepted report required: ' + case_id)
    a, b = left['comparison_record'], right['comparison_record']
    for key in ('fixed_source_sha256', 'camera_plan', 'duration_s'):
        require(a.get(key) and a.get(key) == b.get(key),
                'changed fixed original condition: ' + key)
    x, y = a['measurement'], b['measurement']
    require(x.get('frame_count') == y.get('frame_count') == 900,
            'original measurement frame count differs')
    for key in ('signal_onset_frame', 'event_onset_frame', 'signal_precedes_event',
                'rear_driver_present', 'terminal_max_speed_mps', 'rear_gap_at_event_m'):
        require(x.get(key) is not None and y.get(key) is not None,
                'original rear-signal measurement missing: ' + key)
    if comparison_id in ('stop_signal_order', 'decrease_signal_order'):
        requested = 'stop' if comparison_id == 'stop_signal_order' else 'sudden_decrease'
        require(a['requested_maneuver'] == b['requested_maneuver'] == requested and
                a['requested_rear_driver_present'] is b['requested_rear_driver_present'] is True and
                a['requested_signal_policy'] == 'before' and b['requested_signal_policy'] == 'after' and
                x['signal_precedes_event'] is True and y['signal_precedes_event'] is False and
                x['signal_onset_frame'] < x['event_onset_frame'] and
                y['signal_onset_frame'] > y['event_onset_frame'],
                'signal onset order contrast not measured')
    elif comparison_id == 'stop_vs_decrease':
        require(a['requested_signal_policy'] == b['requested_signal_policy'] == 'before' and
                a['requested_maneuver'] == 'stop' and b['requested_maneuver'] == 'sudden_decrease' and
                x['terminal_max_speed_mps'] <= .1 and y['terminal_max_speed_mps'] > .1 and
                y['event_speed_drop_mps'] > 0,
                'stop/decrease motion contrast not measured')
    else:
        require(a['requested_maneuver'] == b['requested_maneuver'] == 'stop' and
                a['requested_signal_policy'] == b['requested_signal_policy'] == 'before' and
                a['requested_rear_driver_present'] is True and
                b['requested_rear_driver_present'] is False and
                x['rear_driver_present'] is True and y['rear_driver_present'] is False and
                a['rear_driver_source_sha256'] != b['rear_driver_source_sha256'],
                'rear-driver presence contrast not measured')
    return {'format': 'c150640-independent-original-comparison-v1',
            'comparison_id': comparison_id, 'case_ids': case_ids,
            'fixed_source_sha256': a['fixed_source_sha256'],
            'signal_precedes_event': [x['signal_precedes_event'], y['signal_precedes_event']],
            'rear_driver_present': [x['rear_driver_present'], y['rear_driver_present']],
            'terminal_max_speed_mps': [x['terminal_max_speed_mps'], y['terminal_max_speed_mps']],
            'physical_comparison_passed': True, 'legal_verdict_claimed': False}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--report-map', type=Path, required=True)
    parser.add_argument('--comparison', choices=tuple(PAIRS), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = json.loads(args.report_map.read_text())
    reports = {case_id: json.loads(Path(path).read_text()) for case_id, path in paths.items()}
    selected = audit_pair(args.comparison, reports)
    if args.output.exists():
        raise ValueError('refusing to overwrite prior comparison audit')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(selected, indent=2) + '\n')
    print(json.dumps(selected))


if __name__ == '__main__':
    main()
