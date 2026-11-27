"""Saved-only school-zone overtake measurements; no legal classification."""

import argparse
import hashlib
import json
from pathlib import Path

from measure_pass import CAMERAS, measure


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def zone_designation(facts):
    return {'zone_kind': facts['zone_kind'],
            'pass_inside_signed_zone': facts['whole_pass_in_signed_zone']}


def school_day(facts):
    return {'school_in_session': facts['school_in_session'],
            'pupils_in_class': facts['pupils_in_class']}


def time_window(facts):
    return {'minutes_after_operation_end': facts['minutes_after_operation_end_at_cross'],
            'minutes_before_next_operation': facts['minutes_before_next_operation_at_cross'],
            'at_least_half_hour_after_end': facts['at_least_half_hour_after_end_observed'],
            'at_least_half_hour_before_next': facts['at_least_half_hour_before_next_observed']}


def beacon_exception(facts):
    return {'operational_beacon': facts['beacon_operational'],
            'source_observed_yellow_alternation': facts['beacon_yellow_alternating'],
            'pupils_in_class': facts['pupils_in_class']}


def nonbeacon_exception(facts):
    return {'operational_beacon': facts['beacon_operational'],
            'source_reviewed_sign_says_limit_in_effect': facts['sign_says_limit_in_effect']}


def beacon_definition(facts):
    return {'installed_yellow_lights': facts['beacon_yellow_lights'],
            'source_observed_yellow_alternation': facts['beacon_yellow_alternating']}


def same_direction_pass(facts):
    return {'crossing_video_frame': facts['pass_crossing_video_frame'],
            'lane_departure_frame': facts['lane_departure_video_frame'],
            'lane_return_frame': facts['lane_return_video_frame'],
            'whole_pass_inside_zone': facts['whole_pass_in_signed_zone']}


def build_original_context(attempt):
    """Derive saved context from a separately sourced original operator review."""
    path = attempt / 'school_zone_context.json'
    if path.exists():
        return
    survey_path = attempt / 'context-survey.json'
    if not survey_path.is_file():
        raise ValueError('Missing original context-survey.json')
    survey = json.loads(survey_path.read_text())
    from scene import validate_survey
    validate_survey(survey)
    if not survey.get('route_direction_id'):
        raise ValueError('Missing original route direction identity')
    review = survey.get('original_source_review')
    if not isinstance(review, dict) or not review.get('reviewer'):
        raise ValueError('Missing independent original school-zone source review')
    for key in ('school_in_session', 'pupils_in_class', 'beacon_operational',
                'sign_says_limit_in_effect'):
        if type(review.get(key)) is not bool:
            raise ValueError('Missing source-reviewed original condition: ' + key)
    for key in ('civil_time_unix_s', 'operation_end_unix_s',
                'next_operation_start_unix_s'):
        if type(review.get(key)) not in (int, float):
            raise ValueError('Missing source-reviewed original clock: ' + key)
    if review['beacon_operational'] != bool(survey.get('beacon')):
        raise ValueError('Reviewed beacon state differs from installed device source')
    def source(name):
        item = survey.get(name)
        if not isinstance(item, dict) or not item.get('path') or not item.get('sha256'):
            raise ValueError('Missing reviewed original source receipt: ' + name)
        return item['path'] + '#sha256=' + item['sha256']
    names = ('overview', 'approach', 'reference_corner', 'driver_reference')
    context = {
        'assignment_id': survey['assignment_id'], 'review_kind': 'original_source_review',
        'context_survey_sha256': hashlib.sha256(survey_path.read_bytes()).hexdigest(),
        'reviewer': review['reviewer'], 'zone_kind': survey['zone_kind'],
        'zone_station_m': survey['zone_station_bounds_m'],
        'route_direction_id': survey['route_direction_id'],
        'zone_sign_source': source('installed_sign_source'),
        'zone_boundary_source': source('zone_boundary_source'),
        'route_direction_source': source('pass_route_source'),
        'school_calendar_source': source('calendar_source'),
        'operation_hours_source': source('operation_hours_source'),
        'civil_time_source': source('civil_time_source'),
        'beacon_or_sign_source': source('beacon_controller_source') if review['beacon_operational'] else source('installed_sign_source'),
        'school_in_session': review['school_in_session'],
        'pupils_in_class': review['pupils_in_class'],
        'beacon_operational': review['beacon_operational'],
        'beacon_with_sign': review['beacon_operational'],
        'beacon_yellow_lights': len(survey['beacon']['yellow_lights']) if review['beacon_operational'] else None,
        'sign_says_limit_in_effect': review['sign_says_limit_in_effect'],
        'civil_time_unix_s': review['civil_time_unix_s'],
        'operation_end_unix_s': review['operation_end_unix_s'],
        'next_operation_start_unix_s': review['next_operation_start_unix_s'],
        'camera_sha256': {name: hashlib.sha256((attempt / (name + '.mkv')).read_bytes()).hexdigest()
                          for name in names}}
    if review['beacon_operational']:
        lamp_path = attempt / 'beacon_lamps.jsonl'
        if not lamp_path.is_file():
            raise ValueError('Missing original beacon_lamps.jsonl')
        context['beacon_lamp_actor_ids'] = [x['actor_id'] for x in survey['beacon']['yellow_lights']]
        context['beacon_lamps_sha256'] = hashlib.sha256(lamp_path.read_bytes()).hexdigest()
    path.write_text(json.dumps(context, indent=2) + '\n')


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain original attempt; use a fresh saved result')
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case = config.get('case_id')
    if case != construction.get('case_id'):
        raise ValueError('Saved selected case identity differs')
    build_original_context(attempt)
    facts = measure(attempt)
    context = json.loads((attempt / 'school_zone_context.json').read_text())
    trace = rows(attempt / 'pass_trace.jsonl')
    lamps = rows(attempt / 'beacon_lamps.jsonl') if context['beacon_operational'] else None
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    evidence = []
    names = [x['name'] for x in config['recording_description']['channels']]
    if names != ['original_ego_other_pose', 'original_beacon_lamp_state']:
        raise ValueError('Saved channels differ from selected recording plan')
    for name in names:
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for i, row in enumerate(trace):
                value = ({'ego_station_m': row['ego_station_m'],
                          'other_station_m': row['other_station_m'],
                          'ego_lateral_m': row['ego_lateral_m'],
                          'other_lateral_m': row['other_lateral_m']}
                         if name == 'original_ego_other_pose' else
                         (lamps[i]['yellow_lit'] if lamps is not None else []))
                stream.write(json.dumps({'time_s': i / 20, 'value': value}) + '\n')
        evidence.append({'name': name, 'unit': 'structured',
                         'reference': 'channels/' + path.name})
    review_path = channels / 'source_review.json'
    review_path.write_text(json.dumps({
        'four_source_cameras': list(CAMERAS),
        'original_school_designation': context['zone_kind'],
        'original_school_calendar': {'school_in_session': context['school_in_session'],
                                     'pupils_in_class': context['pupils_in_class']},
        'original_civil_time': context['civil_time_unix_s'],
        'original_sign_beacon': {'operational': context['beacon_operational'],
                                 'effective': context['sign_says_limit_in_effect']},
        'original_route': context['route_direction_id'],
        'original_sources': facts['sources'],
        'school_calendar_and_designation_confirmed': False,
        'beacon_yellow_pixels_confirmed': False,
        'physical_pass_and_zone_confirmed': False,
        'legal_verdict': None}) + '\n')
    for item in config['recording_description']['context_inputs']:
        evidence.append({'name': item['name'], 'unit': item['unit'],
                         'reference': 'channels/source_review.json'})
    from worker_exchange.native_output import physical_result, write_result
    result = {
        'case_id': case, 'measured_values': facts,
        'target_checks': [{
            'target': 'same-direction overtake inside the sourced designated zone',
            'requested': config['requested_context'],
            'measured': {'pass_crossing_frame': facts['pass_crossing_video_frame'],
                         'whole_pass_in_signed_zone': facts['whole_pass_in_signed_zone'],
                         'beacon_yellow_alternating': facts['beacon_yellow_alternating']},
            'method': 'saved source-joined Native pose, lamp-state and camera measurements',
            'tolerance': '20 Hz samples; original sign pixels, school status and legal effect require review',
            'matched': False, 'physical_cause_confirmed': False,
            'cause_evidence': list(facts['sources'])}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False, 'accepted': False,
        'termination_reason': 'Saved measurements complete; original source and physical review pending',
        'physical_failure_flags': ['school_source_review_pending',
                                   'beacon_pixels_review_pending',
                                   'physical_pass_review_pending'],
        'trace_reference': 'trace.jsonl',
        'video_references': [x + '.mkv' for x in (*CAMERAS, 'raw')],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': evidence, 'realized_observables': {},
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    write_result(attempt, physical_result(attempt, result))
    contract = json.loads((attempt / 'measurement_contract.json').read_text())
    methods = {name: globals()[name] for name in
               ('zone_designation', 'school_day', 'time_window', 'beacon_exception',
                'nonbeacon_exception', 'beacon_definition', 'same_direction_pass')}
    measurements = {}
    for requirement in contract['requirements']:
        method = requirement['method']
        if method not in methods:
            raise ValueError('Unknown selected school-zone measurement')
        measurements[requirement['output_key']] = {
            'method': method, 'value': methods[method](facts),
            'sources': {name: facts['sources'][name] for name in requirement['inputs']}}
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': measurements,
              'source_complete': True, 'physical_or_legal_acceptance': False}
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
