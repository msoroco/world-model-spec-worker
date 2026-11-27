"""Finalize source-bound emergency-approach observations without a legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_readiness import CAMERAS, FRAMES, lines, measure
from scene import CASES, request
from audit_capture import audit as audit_capture

CHANNELS = ('ego_motion', 'emergency_motion', 'flashing_lights',
            'visible_indication', 'officer_direction', 'braking_response')


def qualifying_approach_context(observed, review):
    return {'approach_frames': observed['approaching_frame_count_after_trigger'],
            'vehicle_class': review['vehicle_class'],
            'lights_reviewed': observed['lights_meet_484A_480_3_reviewed'],
            'officer_direction_reviewed': observed['officer_direction_present_reviewed'],
            'trigger_frame': observed['trigger_frame']}


def stop_preparedness_response(observed, review):
    return {'first_brake_frame': observed['first_brake_frame'],
            'braked_approach_fraction': observed['braked_approach_fraction'],
            'observed_stop_distance_m': observed['observed_stop_distance_m'],
            'peak_observed_deceleration_mps2': observed['peak_observed_deceleration_mps2'],
            'legal_threshold_asserted': False}


def visible_indication_context(observed, review):
    return {'indication_kinds_at_trigger': observed['indication_kinds_at_trigger'],
            'visible_to_approaching_driver_reviewed': review['visible_to_approaching_driver'],
            'review_source': review['visible_motion_source']}


def visible_movement_observed(observed, review):
    return observed['emergency_motion_visible_at_trigger']


def visible_hand_signal_observed(observed, review):
    return observed['hand_signal_visible_at_trigger']


def already_moving_subject_observed(observed, review):
    return observed['emergency_moving_at_trigger']


REQUIREMENT_MEASUREMENTS = (
    ('qualifying_approach_context', qualifying_approach_context,
     ('approach_trace.jsonl', 'emergency_review.json', 'video_frames.jsonl')),
    ('stop_preparedness_response', stop_preparedness_response,
     ('approach_trace.jsonl', 'video_frames.jsonl')),
    ('visible_indication_context', visible_indication_context,
     ('approach_trace.jsonl', 'emergency_review.json', 'approach.mkv')),
    ('visible_movement_observed', visible_movement_observed,
     ('approach_trace.jsonl', 'emergency_review.json')),
    ('visible_hand_signal_observed', visible_hand_signal_observed,
     ('approach_trace.jsonl', 'emergency_review.json')),
    ('already_moving_subject_observed', already_moving_subject_observed,
     ('approach_trace.jsonl', 'video_frames.jsonl')),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists() or (attempt / 'channels').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    required = ('config.json', 'construction.json', 'native-request.json',
                'video_frames.jsonl', 'approach_trace.jsonl', 'emergency_review.json',
                'trace.jsonl', *(camera + '.mkv' for camera in CAMERAS))
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    captured_request = json.loads((attempt / 'native-request.json').read_text())
    condition = captured_request.get('requested_setting')
    if (condition not in CASES or captured_request != request(condition)
            or config.get('case_id') != captured_request['case_id']
            or construction.get('case_id') != captured_request['case_id']
            or config.get('candidate_id') not in ('primary', 'fallback1')):
        raise ValueError('Exact saved case or candidate differs')
    described = construction['recording_description']['channels']
    if {item['name'] for item in described} != set(CHANNELS):
        raise ValueError('Exact recording channel inventory differs')
    observed = measure(attempt)
    capture_audit = None
    if observed['source_kind'] != 'synthetic_diagnostic':
        capture_audit = audit_capture(attempt, condition)
    frames, trace = lines(attempt / 'video_frames.jsonl'), lines(attempt / 'approach_trace.jsonl')
    review = json.loads((attempt / 'emergency_review.json').read_text())
    if len(frames) != FRAMES or len(trace) != FRAMES:
        raise ValueError('Full saved source span required')
    values = {
        'ego_motion': lambda row: {'speed_mps': row['ego_speed_mps'], 'surface_gap_m': row['surface_gap_m']},
        'emergency_motion': lambda row: {'speed_mps': row['emergency_speed_mps']},
        'flashing_lights': lambda row: {'original_pixel_visible': row['emergency_flashing_visible'],
                                        'statutory_qualification_reviewed': review['lights_meet_484A_480_3']},
        'visible_indication': lambda row: {'movement_visible': row['emergency_motion_visible'],
                                           'hand_signal_visible': row['hand_signal_visible']},
        'officer_direction': lambda row: {'officer_direction_present_reviewed': review['officer_direction_present'],
                                          'review_source': review['officer_direction_source']},
        'braking_response': lambda row: {'ego_brake_readback': row['ego_brake'],
                                         'ego_speed_mps': row['ego_speed_mps']},
    }
    channels = attempt / 'channels'
    channels.mkdir()
    evidence = []
    for item in described:
        name = item['name']
        target = channels / (name + '.jsonl')
        with target.open('x') as stream:
            for frame, row in zip(frames, trace):
                stream.write(json.dumps({'time_s': frame['time_s'], 'value': values[name](row)},
                                        allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': item['unit'], 'reference': 'channels/' + target.name})
    measurements = {'approach_readiness': {
        'method': 'measure_readiness', 'value': observed, 'sources': observed['sources']}}
    for key, method, sources in REQUIREMENT_MEASUREMENTS:
        measurements[key] = {'method': method.__name__, 'value': method(observed, review),
                             'sources': {name: observed['sources'][name] for name in sources}}
    report = {'format': 'c405647-2c-saved-analysis-v1', 'case_id': captured_request['case_id'],
              'measurements': measurements,
              'original_capture_audit': capture_audit,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    requested_brake = int(condition == 'braking_capacity_available')
    observed_brake = int(observed['first_brake_frame'] is not None)
    result = {'case_id': captured_request['case_id'], 'measured_values': observed,
              'target_checks': [{'target': 'brake actuation observed after source-bound trigger',
                                 'requested': requested_brake, 'measured': observed_brake,
                                 'method': 'original saved brake readback and frame-bound trigger',
                                 'tolerance': 0, 'matched': requested_brake == observed_brake,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(observed['sources'])}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'full 600-frame saved diagnostic window',
              'physical_failure_flags': ['Original Native and statutory qualification need independent review'],
              'trace_reference': 'trace.jsonl',
              'video_references': [camera + '.mkv' for camera in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': ('synthetic_local_diagnostic' if observed['source_kind'] == 'synthetic_diagnostic'
                                  else 'original_native'), 'accepted': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
