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
    lighting_name = ('derived-lighting-saved' if (attempt / 'derived-lighting').exists()
                     else 'derived-lighting')
    measurement = selected_lighting_measurement(attempt, attempt / lighting_name)
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
    # Preserve the acquisition rows and expose one source-bound, regularly
    # sampled stream per declared channel for the current recording validator.
    native_rows = [json.loads(line) for line in (attempt / 'native-lighting-frames.jsonl').read_text().splitlines()]
    review_rows = [json.loads(line) for line in (attempt / 'lighting-review.jsonl').read_text().splitlines()]
    context = json.loads((attempt / 'lighting-measure-context.json').read_text())
    recording_name = ('derived-recording-saved' if (attempt / 'derived-recording').exists()
                      else 'derived-recording')
    derived = attempt / recording_name
    derived.mkdir()
    evidence = []
    for channel in config['recording_description']['channels']:
        name = channel['name']
        records = []
        for index, (native, review) in enumerate(zip(native_rows, review_rows)):
            if name in review:
                value, source_name = review[name], 'lighting-review.jsonl'
            elif name in native:
                value, source_name = native[name], 'native-lighting-frames.jsonl'
            elif name in context:
                value, source_name = context[name], 'lighting-measure-context.json'
            elif name == 'speed_mps':
                value, source_name = native['velocity_mps'][0], 'native-lighting-frames.jsonl'
            elif name == 'ego_pose':
                value, source_name = {'velocity_mps': native['velocity_mps']}, 'native-lighting-frames.jsonl'
            elif name == 'native_lighting_frames':
                value, source_name = native, 'native-lighting-frames.jsonl'
            elif name == 'four_camera_video':
                value, source_name = {key: source_hashes[key] for key in
                                      ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')}, 'lighting-review-context.json'
            else:
                raise ValueError('Declared recording channel lacks source: ' + name)
            records.append({'time_s': index / 20, 'value': value,
                            'source': source_name, 'source_sha256': source_hashes[source_name]})
        reference = f'{recording_name}/{name}.jsonl'
        (attempt / reference).write_text(''.join(json.dumps(row) + '\n' for row in records))
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': reference})
    context_values = {
        'independent_lamp_range_review': context['range_calibration_source'],
        'sunset_sunrise': {'sunset_utc_s': context['sunset_utc_s'],
                           'next_sunrise_utc_s': context['next_sunrise_utc_s']},
    }
    for channel in config['recording_description']['context_inputs']:
        name = channel['name']
        reference = f'{recording_name}/{name}.json'
        (attempt / reference).write_text(json.dumps({name: context_values[name],
            'source': 'lighting-measure-context.json',
            'source_sha256': source_hashes['lighting-measure-context.json']}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': reference})
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
