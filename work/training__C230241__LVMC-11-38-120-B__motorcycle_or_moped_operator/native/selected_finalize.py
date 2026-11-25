"""Saved-only lighting observations for the two exact C230241 cases.

This finalizer preserves original acquisition. Synthetic compatibility returns
source-bound measurements and explicitly leaves physical/legal review open.
"""
import argparse
import hashlib
import json
from pathlib import Path

from selected_source_analysis import SOURCES, required, selected_lighting_measurement


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def equipment_observations(measurement):
    return {
        'headlamp_count': measurement['headlamp_count'],
        'tail_lamp_rear_mounted': measurement['tail_lamp_rear_mounted'],
        'front_below_300ft_frames': measurement['counts']['front_below_300ft_frames'],
        'rear_below_500ft_frames': measurement['counts']['rear_below_500ft_frames'],
        'headlamp_nonwhite_frames': measurement['counts']['headlamp_nonwhite_frames'],
        'tail_lamp_nonred_frames': measurement['counts']['tail_lamp_nonred_frames'],
        'statutory_front_ft': measurement['statutory_front_ft'],
        'statutory_rear_ft': measurement['statutory_rear_ft'],
        'physical_visibility_verified': False,
    }


def burning_observations(measurement):
    return {
        'motion_frames': measurement['counts']['motion_frames'],
        'activation_frames': measurement['counts']['activation_frames'],
        'required_burning_frames': measurement['counts']['required_burning_frames'],
        'headlamp_dark_frames': measurement['counts']['headlamp_dark_frames'],
        'tail_lamp_dark_frames': measurement['counts']['tail_lamp_dark_frames'],
        'night_window_frames': measurement['counts']['night_window_frames'],
        'low_visibility_frames': measurement['counts']['low_visibility_frames'],
        'sunset_offset_s': measurement['sunset_offset_s'],
        'sunrise_offset_s': measurement['sunrise_offset_s'],
        'legal_verdict_claimed': False,
    }


def scope_observations(measurement):
    return {
        'frames': measurement['frames'],
        'source_hashes': measurement['source_hashes'],
        'diagnostic_only': measurement['diagnostic_only'],
        'original_lamp_and_range_review_pending': True,
    }


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior finalization; choose a fresh attempt')
    config = json.loads(required(attempt, 'config.json').read_text())
    case_id = config['case_id']
    if case_id not in config.get('supported_case_ids', []):
        raise ValueError('Unselected case identity')
    for name in SOURCES:
        required(attempt, name)
    measurement = selected_lighting_measurement(attempt, attempt / 'derived-lighting')
    source_hashes = {name: sha(attempt / name) for name in SOURCES}
    sets = {
        'equipment_observations': (equipment_observations(measurement),
                                   ('lighting-review.jsonl', 'lighting-measure-context.json')),
        'burning_observations': (burning_observations(measurement),
                                ('native-lighting-frames.jsonl', 'lighting-review.jsonl',
                                 'lighting-measure-context.json')),
        'scope_observations': (scope_observations(measurement),
                               ('lighting-review-context.json', 'video_frames.jsonl')),
    }
    report = {'format': 'c230241-selected-saved-analysis-v1',
              'case_id': case_id,
              'measurements': {key: {'method': key,
                                     'value': value,
                                     'sources': {name: source_hashes[name] for name in inputs}}
                               for key, (value, inputs) in sets.items()},
              'source_kind': 'diagnostic' if measurement['diagnostic_only'] else 'original_review_pending',
              'physical_visibility_verified': False,
              'legal_verdict_claimed': False}
    evidence = [{'name': channel['name'], 'unit': channel['unit'],
                 'reference': 'native-lighting-frames.jsonl' if channel['name'] in
                 ('speed_mps', 'ego_pose', 'native_lighting_frames') else
                 'lighting-review.jsonl'}
                for channel in config['recording_description']['channels']]
    result = {
        'case_id': case_id,
        'measured_values': measurement['counts'],
        'target_checks': [{'target': 'source-observed motorcycle lighting and motion',
                           'requested': config['requested_light_state'],
                           'measured': measurement['counts'],
                           'method': 'saved same-frame original source and independent review join',
                           'tolerance': '50 ms source frame; exact statutory distances retained',
                           'matched': False,
                           'physical_cause_confirmed': False,
                           'cause_evidence': list(SOURCES)}],
        'setup_confirmed': False,
        'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'source-complete saved diagnostic; physical review pending',
        'physical_failure_flags': ['original_lamp_distance_and_discernibility_review_pending'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in
                             ('overview', 'approach', 'reference_corner', 'driver_reference')],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': evidence,
        'realized_observables': {'saved_source_frame_count': {
            'value': measurement['frames'], 'unit': 'frames',
            'method': 'source-bound saved review join', 'time_window': '30 seconds',
            'statistic': 'count', 'reference': 'video_frames.jsonl'}},
        'provenance_kind': 'synthetic_local_diagnostic' if measurement['diagnostic_only'] else 'native',
        'accepted': False,
        'legal_verdict_claimed': False,
    }
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
