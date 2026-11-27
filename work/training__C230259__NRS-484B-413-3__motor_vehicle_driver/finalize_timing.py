"""Recorded-only rear-signal timing; raw ordering without a legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_timing import measure

VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')
SOURCES = ('actor-sources.jsonl', 'camera-frames.jsonl', 'video_frames.jsonl',
           'rear-signal-context.json')
TERMS = ('drv.stopped', 'drv.hard_deceleration', 'kin.accel_longitudinal',
         'sig.brake_lamp', 'sig.hand_signal', 'drv.following',
         'rel.ahead_behind_in_lane', 'rel.surface_gap')


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_stop(observed, context):
    return {'first_stop_frame': observed['first_observed_stop_frame'],
            'signal_precedes_stop': observed['signal_precedes_stop'],
            'public_highway_reviewed': context['public_highway_reviewed']}


def measure_decrease(observed, context):
    return {'first_diagnostic_deceleration_frame':
                observed['first_diagnostic_3mps2_deceleration_frame'],
            'signal_precedes_diagnostic_deceleration':
                observed['signal_precedes_diagnostic_deceleration'],
            'diagnostic_bound_is_statutory': False,
            'legal_suddenness_reviewed': context['legal_suddenness_reviewed']}


def measure_signal(observed, context):
    return {'first_observed_brake_lamp_frame': observed['first_observed_brake_lamp_frame'],
            'first_observed_hand_signal_frame': observed['first_observed_hand_signal_frame'],
            'first_observed_signal_frame': observed['first_observed_signal_frame'],
            'signal_precedes_stop': observed['signal_precedes_stop'],
            'signal_precedes_diagnostic_deceleration':
                observed['signal_precedes_diagnostic_deceleration'],
            'appropriateness_reviewed': context['signal_appropriateness_reviewed']}


def measure_rear(observed, context):
    return {'rear_same_lane_all_frames': observed['rear_same_lane_all_frames'],
            'min_rear_surface_gap_m': observed['min_rear_surface_gap_m'],
            'immediate_rear_reviewed': context['immediate_rear_reviewed']}


def measure_appropriateness(observed, context):
    return {'first_observed_brake_lamp_frame': observed['first_observed_brake_lamp_frame'],
            'first_observed_hand_signal_frame': observed['first_observed_hand_signal_frame'],
            'appropriateness_reviewed': context['signal_appropriateness_reviewed'],
            'legal_verdict_claimed': False}


METHODS = (('stop_timing', 'measure_stop', measure_stop),
           ('decrease_timing', 'measure_decrease', measure_decrease),
           ('signal_order', 'measure_signal', measure_signal),
           ('rear_recipient', 'measure_rear', measure_rear),
           ('signal_appropriateness', 'measure_appropriateness', measure_appropriateness))


def finalize(attempt, output):
    from worker_exchange.native_output import provenance_record, write_result

    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Use fresh recorded-only analysis output')
    config = json.loads(required(attempt, 'config.json').read_text())
    context = json.loads(required(attempt, 'rear-signal-context.json').read_text())
    observed = measure(attempt, config['case_id'],
                       source_kind=context['source_kind'])
    actors = [json.loads(line) for line in
              required(attempt, 'actor-sources.jsonl').read_text().splitlines()]
    by_term = {term: [] for term in TERMS}
    for row in actors:
        values = {
            'drv.stopped': row['ego_speed_mps'] <= .1,
            'drv.hard_deceleration': row['ego_accel_longitudinal_mps2'] <= -3,
            'kin.accel_longitudinal': row['ego_accel_longitudinal_mps2'],
            'sig.brake_lamp': row['brake_lamp_observed'],
            'sig.hand_signal': row['hand_signal'],
            'drv.following': {'rear_actor_id': row['rear']['actor_id']},
            'rel.ahead_behind_in_lane': {'same_lane': row['rear_lane_id'] ==
                row['ego_lane_id'], 'rear_is_behind': row['rear_is_behind']},
            'rel.surface_gap': row['surface_gap_m'],
        }
        for term, value in values.items():
            by_term[term].append({'time_s': row['time_s'], 'value': value})
    observation_dir = attempt / 'observations'
    observation_dir.mkdir(exist_ok=False)
    for term, rows in by_term.items():
        (observation_dir / (term + '.jsonl')).write_text(''.join(
            json.dumps(row, allow_nan=False) + '\n' for row in rows))
    (attempt / 'observation-context.json').write_text(json.dumps(
        {'rear_signal_context': context}, allow_nan=False) + '\n')
    source_hashes = {name: sha(required(attempt, name)) for name in SOURCES}
    provenance = provenance_record(attempt)
    original = provenance['provenance_kind'] == 'native' and not provenance['diagnostic_fixture']
    action = 'stop' if config['case_suffix'] in ('stop_early', 'stop_late') else 'decrease'
    signal = observed['first_observed_signal_frame']
    action_frame = (observed['first_observed_stop_frame'] if action == 'stop' else
                    observed['first_diagnostic_3mps2_deceleration_frame'])
    target_early = config['case_suffix'] in ('stop_early', 'probe_1')
    target_matched = signal is not None and action_frame is not None and (
        (signal < action_frame) == target_early)
    result = {
        'case_id': config['case_id'], 'measured_values': observed,
        'target_checks': [{'target': config['case_suffix'],
                           'requested': config['target'],
                           'measured': {'signal_frame': signal,
                                        'action_frame': action_frame},
                           'method': 'same-tick observed lamp/arm and Native kinematics',
                           'tolerance': 'raw ordering only; no statutory lead or suddenness cutoff',
                           'matched': target_matched,
                           'physical_cause_confirmed': False,
                           'cause_evidence': list(SOURCES)}],
        'setup_confirmed': original and context['public_highway_reviewed'] and
                           context['immediate_rear_reviewed'],
        'behavior_attempted': original,
        'maneuver_completed': original and target_matched,
        'termination_reason': '600 same-tick source frames retained',
        'physical_failure_flags': [] if target_matched else ['requested_timing_not_observed'],
        'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [{'name': term, 'unit': 'structured',
                                'reference': 'observations/' + term + '.jsonl'}
                               for term in TERMS] +
                              [{'name': 'rear_signal_context', 'unit': 'structured',
                                'reference': 'observation-context.json'}],
        'realized_observables': {'signal_lead_frames': {
            'value': None if signal is None or action_frame is None else action_frame - signal,
            'unit': 'frames', 'method': 'observed signal minus observed action',
            'time_window': '600 frames', 'statistic': 'first-event difference',
            'reference': 'actor-sources.jsonl'}},
        'provenance_kind': provenance['provenance_kind'],
        'diagnostic_fixture': provenance['diagnostic_fixture'],
        'accepted': False, 'legal_verdict_claimed': False}
    write_result(attempt, result)
    measurements = {key: {'method': method, 'value': function(observed, context),
                           'sources': dict(source_hashes)}
                    for key, method, function in METHODS}
    report = {'format': 'c230259-rear-signal-analysis-v1',
              'case_id': config['case_id'], 'analysis_complete': True,
              'measurements': measurements, 'source_hashes': source_hashes,
              'provenance': provenance, 'legal_verdict_claimed': False,
              'physical_acceptance_claimed': False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
