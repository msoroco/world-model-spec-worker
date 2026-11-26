"""Recorded-only C245490 source analysis; no physical or legal acceptance claim."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_lane_change import measure, read_trace

VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')
SOURCES = ('native-ego-frames.jsonl', 'native-driver-checks.jsonl',
           'driving-context.json', 'video_frames.jsonl')


def required(attempt, name):
    path = Path(attempt) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(attempt, output):
    from worker_exchange.native_output import provenance_record, write_result

    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Use fresh recorded-only analysis output')
    config = json.loads(required(attempt, 'config.json').read_text())
    context = json.loads(required(attempt, 'driving-context.json').read_text())
    for video in VIDEOS:
        required(attempt, video)
    rows = read_trace(required(attempt, 'native-ego-frames.jsonl'))
    checks = read_trace(required(attempt, 'native-driver-checks.jsonl'))
    observed = measure(rows, context['source_kind'], checks)
    channel_values = {
        'ego_lane': lambda row: {'occupied_lane_id': row['occupied_lane_id'],
                                 'current_lane_id': row['current_lane_id'],
                                 'lateral_offset_m': row['ego_lateral_offset_from_occupied_lane_center_m']},
        'front_actor': lambda row: {'position_m': row['target_front_position_m'],
                                    'surface_gap_m': row['target_front_surface_gap_m']},
        'rear_actor': lambda row: {'position_m': row['target_rear_position_m'],
                                   'surface_gap_m': row['target_rear_surface_gap_m']},
        'observed_indicator': lambda row: {'requested_on': row['target_direction_indicator_requested_on'],
                                          'observed_on': row['target_direction_indicator_observed_on']},
        'controller_check': lambda row: {'action': checks[0]['action'],
                                         'check_frame': checks[0]['video_frame']},
    }
    channel_evidence = []
    (attempt / 'channels').mkdir(exist_ok=True)
    for name, project in channel_values.items():
        reference = 'channels/' + name + '.jsonl'
        with (attempt / reference).open('w') as stream:
            for row in rows:
                stream.write(json.dumps({'time_s': row['time_s'], 'value': project(row)},
                                        allow_nan=False) + '\n')
        channel_evidence.append({'name': name, 'unit': 'structured', 'reference': reference})
    if config['case_id'] != config['selected_case_id']:
        raise ValueError('Selected exact case identity mismatch')
    suffix = config['case_id'].split('__')[-1]
    targets = {
        'signal_before_safe': observed['signal_precedes_departure'] and
                              observed['controller_check_action'] == 'evaluated' and
                              observed['controller_decision_to_depart'] is True,
        'signal_after_safe': not observed['signal_precedes_departure'] and
                             observed['controller_check_action'] == 'evaluated' and
                             observed['controller_decision_to_depart'] is True,
        'signal_before_unsafe': observed['signal_precedes_departure'] and
                                observed['controller_check_action'] == 'evaluated' and
                                observed['controller_decision_to_depart'] is False,
        'signal_before_no_check': observed['signal_precedes_departure'] and
                                  observed['controller_check_action'] == 'skipped',
    }
    if suffix not in targets:
        raise ValueError('Unknown exact selected case')
    hashes = {name: sha(required(attempt, name)) for name in SOURCES}
    provenance = provenance_record(attempt)
    original = provenance['provenance_kind'] == 'native' and not provenance['diagnostic_fixture']
    target_matched = observed['activation_observed'] and bool(targets[suffix])
    result = {
        'case_id': config['case_id'], 'measured_values': observed,
        'target_checks': [{'target': suffix, 'requested': suffix,
                           'measured': {'signal_start_frame': observed['signal_start_frame'],
                                        'body_departure_frame': observed['first_body_departure_frame'],
                                        'gap_at_departure_m': observed['gap_at_departure_m'],
                                        'controller_check_action': observed['controller_check_action'],
                                        'controller_decision_to_depart': observed['controller_decision_to_depart']},
                           'method': 'original same-tick Native lane, indicator, front/rear actor and independent controller-check sources',
                           'tolerance': 'event order only; 12 m controller engineering rule is not a legal cutoff',
                           'matched': target_matched, 'physical_cause_confirmed': False,
                           'cause_evidence': list(SOURCES)}],
        'setup_confirmed': original and observed['same_direction_marked_lane_count'] >= 2,
        'behavior_attempted': original,
        'maneuver_completed': original and target_matched,
        'termination_reason': '600 same-tick source frames retained',
        'physical_failure_flags': [] if target_matched else ['requested_case_not_observed'],
        'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': channel_evidence,
        'realized_observables': {
            'target_lane_gap_m': {'value': observed['gap_at_departure_m'], 'unit': 'm',
                                   'method': 'front/rear longitudinal body clearance',
                                   'time_window': 'body departure frame', 'statistic': 'minimum',
                                   'reference': 'native-ego-frames.jsonl'}},
        'provenance_kind': provenance['provenance_kind'],
        'diagnostic_fixture': provenance['diagnostic_fixture'],
        'accepted': False, 'legal_verdict_claimed': False,
    }
    if observed['signal_lead_s'] is not None:
        result['realized_observables']['signal_lead_s'] = {
            'value': observed['signal_lead_s'], 'unit': 's',
            'method': 'observed indicator onset to body departure',
            'time_window': '600 frames', 'statistic': 'first-event difference',
            'reference': 'native-ego-frames.jsonl'}
    write_result(attempt, result)
    report = {'format': 'c245490-lane-change-analysis-v1',
              'case_id': config['case_id'], 'analysis_complete': True,
              'measured_values': observed,
              'measurements': {
                  'lane_activation': {'method': 'finalize',
                                      'value': {'same_direction_marked_lane_count': observed['same_direction_marked_lane_count'],
                                                'first_body_departure_frame': observed['first_body_departure_frame']},
                                      'sources': dict(hashes)},
                  'signal_order': {'method': 'finalize',
                                   'value': {'observed_onset': observed['signal_start_frame'],
                                             'requested_onset': observed['signal_request_start_frame'],
                                             'precedes_departure': observed['signal_precedes_departure']},
                                   'sources': dict(hashes)},
                  'independent_check': {'method': 'finalize',
                                        'value': {'action': observed['controller_check_action'],
                                                  'decision': observed['controller_decision_to_depart'],
                                                  'frame': observed['controller_check_frame']},
                                        'sources': dict(hashes)},
                  'target_lane_gap': {'method': 'finalize',
                                      'value': {'gap_at_departure_m': observed['gap_at_departure_m'],
                                                'ttc_at_departure_s': observed['ttc_at_departure_s']},
                                      'sources': dict(hashes)}},
              'source_hashes': hashes, 'provenance': provenance,
              'legal_verdict_claimed': False, 'physical_acceptance_claimed': False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
