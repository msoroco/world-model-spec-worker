"""Source-bound school-crossing-zone finalization from saved frames only."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from measure_saved import CAMERAS, COUNT, measure


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def school_zone_observation(attempt):
    config = json.loads(required(attempt, 'config.json').read_text())
    for name in ('school_zone_context.json', 'native_motion.jsonl', 'video_frames.jsonl',
                 'trace.jsonl', 'capture/evidence.jsonl', 'capture/native/frames.jsonl'):
        required(attempt, name)
    for name in CAMERAS:
        required(attempt, name + '.mkv')
    return measure(attempt, config['case_id'])


def school_day_observation(context):
    return {'school_session_day': context['school_session_day'],
            'calendar_source': context['calendar_source'],
            'civil_start_iso': context['civil_start_iso']}


def half_hour_observation(context):
    return {'half_hour_window_exception': context['half_hour_window_exception'],
            'school_hours_source': context['school_hours_source'],
            'half_hour_window_source': context['half_hour_window_source'],
            'civil_start_iso': context['civil_start_iso']}


def beacon_exception_observation(context):
    return {'beacon_operational': context['beacon_operational'],
            'pupils_in_class': context['pupils_in_class'],
            'beacon_flashing': context['beacon_flashing'],
            'beacon_phase_source': context['beacon_phase_source']}


def nonbeacon_sign_observation(context):
    return {'beacon_operational': context['beacon_operational'],
            'nonbeacon_sign_in_effect': context['nonbeacon_sign_in_effect'],
            'nonbeacon_sign_schedule_source': context['nonbeacon_sign_schedule_source']}


def beacon_definition_observation(context):
    return {'beacon_sign_present': context['beacon_sign_present'],
            'beacon_yellow_light_count': context['beacon_yellow_light_count'],
            'beacon_alternating_yellow': context['beacon_alternating_yellow'],
            'beacon_lights_source': context['beacon_lights_source']}


def motor_bus_scope_observation(context, observed):
    return {'ego_is_motor_bus': context['ego_is_motor_bus'],
            'vehicle_class_source': context['vehicle_class_source'],
            'zone_frame_count': observed['zone_frame_count'],
            'children_source': context['children_source']}


def finalize(attempt, output):
    from worker_exchange.native_output import provenance_record, write_result
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Choose a fresh recorded-only attempt')
    config = json.loads(required(attempt, 'config.json').read_text())
    if config.get('rate_hz') != 20 or config.get('frames') != COUNT:
        raise ValueError('School-zone capture profile differs')
    observed = school_zone_observation(attempt)
    context = json.loads((attempt / 'school_zone_context.json').read_text())
    provenance = provenance_record(attempt)
    original = observed['review_kind'] == 'original_source_review'
    if original != (provenance['provenance_kind'] == 'native' and not provenance['diagnostic_fixture']):
        raise ValueError('School-zone source and acquisition provenance disagree')
    names = ('school_zone_context.json', 'native_motion.jsonl', 'children_context.jsonl',
             'video_frames.jsonl',
             'trace.jsonl', 'capture/evidence.jsonl', 'capture/native/frames.jsonl',
             'road.xodr') + tuple(name + '.mkv' for name in CAMERAS)
    hashes = {name: sha(required(attempt, name)) for name in names}
    mapping = rows(attempt / 'video_frames.jsonl')
    motion = rows(attempt / 'native_motion.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    native_frames = rows(attempt / 'capture/native/frames.jsonl')
    if any(len(value) != COUNT for value in (mapping, motion, trace, evidence, native_frames)):
        raise ValueError('Incomplete original school-crossing-zone/Core frame join')
    for index, (frame, sample, core, sensor, native) in enumerate(zip(mapping, motion, trace, evidence, native_frames)):
        source_frame = frame.get('native_frame')
        speed = math.sqrt(sum(sample[key] ** 2 for key in ('velocity_x_mps', 'velocity_y_mps', 'velocity_z_mps')))
        if (frame.get('video_frame') != index or sample.get('video_frame') != index or
                sample.get('native_frame') != source_frame or core.get('frame') != source_frame or
                sensor.get('original_frame') != source_frame or native.get('frame') != source_frame or
                abs(core.get('time_s', -10) - frame['time_s']) > 1e-5 or
                abs(sensor.get('recording_time_s', -10) - frame['time_s']) > 1e-5 or
                abs(native.get('time_s', -10) - frame['time_s']) > 1e-5 or
                abs(core['position']['x'] - sample['ego_x_m']) > 1e-4 or
                abs(core['position']['y'] - sample['ego_y_m']) > 1e-4 or
                abs(sensor['ego']['position_m'][0] - sample['ego_x_m']) > 1e-4 or
                abs(sensor['ego']['position_m'][1] - sample['ego_y_m']) > 1e-4 or
                abs(core['speed_mps'] - speed) > 1e-4 or
                abs(sensor['ego']['speed_mps'] - speed) > 1e-4):
            raise ValueError('School-zone original motion/Core source join differs')
    channel = attempt / 'channels/school_crossing_observation.jsonl'
    channel.parent.mkdir(exist_ok=True)
    channel.write_text(''.join(json.dumps({'time_s': frame['time_s'],
            'value': {'speed_mps': math.sqrt(sum(sample[key] ** 2 for key in
                       ('velocity_x_mps', 'velocity_y_mps', 'velocity_z_mps'))),
                      'road_id': sample['road_id'],
                      'travel_direction_id': sample['travel_direction_id'],
                      'ego_xy_m': [sample['ego_x_m'], sample['ego_y_m']]}}) + '\n'
            for frame, sample in zip(mapping, motion)))
    context_channel = attempt / 'channels/school_zone_context.json'
    context_channel.write_text(json.dumps({'school_zone_context': json.loads(
        (attempt / 'school_zone_context.json').read_text())}, indent=2) + '\n')
    speed = observed['maximum_observed_mph_in_zone']
    result = {'case_id': config['case_id'], 'measured_values': observed,
              'target_checks': [{'target': 'school_crossing_observed_speed_mph', 'requested': config['target_mph'],
                                 'measured': speed, 'method': 'original velocity magnitude inside reviewed zone',
                                 'tolerance': 0.5, 'matched': abs(speed - config['target_mph']) <= 0.5,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': ['native_motion.jsonl', 'school_zone_context.json']}],
              'setup_confirmed': original and observed['zone_frame_count'] > 0,
              'behavior_attempted': original and observed['zone_frame_count'] > 0,
              'maneuver_completed': original and observed['zone_frame_count'] > 0,
              'termination_reason': '600 original source frames retained',
              'physical_failure_flags': ['independent_school_authority_and_pixels_require_review'],
              'trace_reference': 'trace.jsonl', 'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': [{'name': 'school_crossing_observation', 'unit': 'structured',
                                      'reference': 'channels/school_crossing_observation.jsonl'},
                                     {'name': 'school_zone_context', 'unit': 'structured',
                                      'reference': 'channels/school_zone_context.json'}],
              'realized_observables': {'school_zone_speed': {'value': speed, 'unit': 'mph',
                    'method': 'source-bound velocity magnitude inside reviewed zone',
                    'time_window': '600 frames', 'statistic': 'maximum',
                    'reference': 'native_motion.jsonl'}},
              'provenance_kind': provenance['provenance_kind'],
              'diagnostic_fixture': provenance['diagnostic_fixture'],
              'accepted': False, 'legal_verdict_claimed': False}
    write_result(attempt, result)
    inputs = {
        'source_topic_0': ('school_zone_observation', observed,
                           ('school_zone_context.json', 'native_motion.jsonl', 'video_frames.jsonl')),
        'source_topic_1': ('school_day_observation', school_day_observation(context),
                           ('school_zone_context.json',)),
        'source_topic_2': ('half_hour_observation', half_hour_observation(context),
                           ('school_zone_context.json',)),
        'source_topic_3': ('beacon_exception_observation', beacon_exception_observation(context),
                           ('school_zone_context.json', 'overview.mkv', 'approach.mkv')),
        'source_topic_4': ('nonbeacon_sign_observation', nonbeacon_sign_observation(context),
                           ('school_zone_context.json', 'reference_corner.mkv')),
        'source_topic_5': ('beacon_definition_observation', beacon_definition_observation(context),
                           ('school_zone_context.json', 'overview.mkv', 'approach.mkv')),
        'source_topic_6': ('motor_bus_scope_observation', motor_bus_scope_observation(context, observed),
                           ('school_zone_context.json', 'children_context.jsonl', 'native_motion.jsonl')),
    }
    report = {'format': 'c255451-school-zone-analysis-v1', 'case_id': config['case_id'],
              'analysis_complete': True, 'legal_verdict_claimed': False,
              'measurements': {key: {'method': method, 'value': value,
                                     'sources': {name: hashes[name] for name in required}}
                               for key, (method, value, required) in inputs.items()},
              'source_hashes': hashes, 'provenance': provenance,
              'limitations': ['Diagnostic fixture does not establish original Native pixels, school authority or physical acceptance.']}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
