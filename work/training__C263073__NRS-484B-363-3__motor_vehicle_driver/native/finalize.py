"""Saved-only original school-zone measurement; legal meaning stays unresolved."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_turn import CAMERAS, FRAMES, measure
from review_context import EXCEPTIONS, EXCEPTION_TOPICS
from branch_cases import CASES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_school_turn(attempt):
    """Return physical trajectory and source-review states, without a legal verdict."""
    raw = measure(attempt)
    return {'cumulative_absolute_heading_change_deg': raw['cumulative_absolute_heading_change_deg'],
            'ego_zone_frame_count': raw['ego_zone_frame_count'],
            'other_person_zone_frame_count': raw['other_person_zone_frame_count'],
            'exception_review_states': {key: raw['independent_source_review']['exception_dispositions'][key]['status']
                                        for key in EXCEPTIONS},
            'legal_u_turn_status': 'unresolved'}


def measure_exception(attempt, context, key):
    """Expose one exact statutory exception's source review without deciding it."""
    review = context['independent_review']
    item = review['exception_dispositions'][key]
    topics = sorted(EXCEPTION_TOPICS[key])
    sources = {'school-context.json': sha(attempt / 'school-context.json')}
    for topic in topics:
        record = review['records'][topic]
        sources[record['path']] = sha(attempt / record['path'])
    return {'method': 'measure_exception',
            'value': {'status': item['status'], 'reason': item['reason'],
                      'source_topics': topics, 'legal_verdict': 'unresolved'},
            'sources': sources}


def emit(path, values):
    with Path(path).open('x') as stream:
        for index, value in enumerate(values):
            stream.write(json.dumps({'time_s': index / 20, 'value': value}, allow_nan=False) + '\n')


def run(attempt, output):
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    config = json.loads((attempt / 'config.json').read_text())
    case = config['case_id']
    if case not in config['supported_case_ids'] or case != config['selected_case_id']:
        raise ValueError('Selected original case identity changed')
    observed = measure_school_turn(attempt)
    raw = [json.loads(line) for line in (attempt / 'native-motion.jsonl').read_text().splitlines()]
    if len(raw) != FRAMES:
        raise ValueError('Original motion frame count differs')
    context = json.loads((attempt / 'school-context.json').read_text())
    review = context['independent_review']
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    zone = context['zone']
    def inside(point):
        return zone['x_min_m'] <= point[0] <= zone['x_max_m'] and zone['y_min_m'] <= point[1] <= zone['y_max_m']
    streams = {
        'dev.zone_sign': [{'source_sha256': review['records']['zone_sign']['sha256'],
                           'observation': review['records']['zone_sign']['observation']}] * FRAMES,
        'drv.within_signed_zone': [inside(row['ego']['center_xy_m']) for row in raw],
        'drv.u_turn': [{'heading_deg': row['ego']['heading_deg'],
                        'body_xy_m': row['ego'].get('body_xy_m')} for row in raw],
        'kin.heading': [row['ego']['heading_deg'] for row in raw],
        'ru.child': [{'person_xy_m': row['other_person']['center_xy_m'] if row['other_person'] is not None else None,
                      'identity_source_sha256': review['records']['child_identity']['sha256']} for row in raw],
        'dev.speed_limit_beacon': [{'configuration_source_sha256': review['records']['beacon_configuration']['sha256'],
                                    'light_source_sha256': review['records']['beacon_lights']['sha256']}] * FRAMES,
        'drv.condition_in_effect': [observed['exception_review_states']] * FRAMES,
        'env.civil_time': [{'source_sha256': review['records']['civil_time']['sha256'],
                            'observation': review['records']['civil_time']['observation']}] * FRAMES,
    }
    for name, values in streams.items():
        emit(channels / (name + '.jsonl'), values)
    description = config['case']['recording_description']
    evidence = [{'name': item['name'], 'unit': item['unit'],
                 'reference': 'channels/' + item['name'] + '.jsonl'}
                for item in description['channels']]
    requested = 180 if CASES[config['case_suffix']]['turn'] else 0
    measured = observed['cumulative_absolute_heading_change_deg']
    target_check = {'target': 'engineering heading change target', 'requested': requested,
                    'measured': measured, 'method': 'original physical vehicle trajectory',
                    'tolerance': 30, 'matched': abs(measured - requested) <= 30,
                    'physical_cause_confirmed': False,
                    'cause_evidence': ['native-motion.jsonl', 'school-context.json']}
    result = {'case_id': case, 'measured_values': observed, 'target_checks': [target_check],
              'setup_confirmed': False, 'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'Saved original-source review; physical and legal judgments pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {}}
    from worker_exchange.native_output import physical_result, validate_result
    result = physical_result(attempt, result)
    validate_result(result)
    (attempt / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    sources = {name: sha(attempt / name) for name in
               ('native-motion.jsonl', 'school-context.json', 'video_frames.jsonl')}
    measurements = {'school_zone_turn_observation': {
        'method': 'measure_school_turn', 'value': observed, 'sources': sources}}
    for key in EXCEPTIONS:
        measurements['exception_' + key] = measure_exception(attempt, context, key)
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': measurements,
              'physical_checks': result['physical_checks'],
              'realized_observables': result['realized_observables'],
              'limitations': ['No legal U-turn, child-presence or exception verdict from CPU fixtures.']}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(args.attempt, args.output)
