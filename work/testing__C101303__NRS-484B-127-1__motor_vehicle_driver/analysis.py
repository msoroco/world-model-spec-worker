"""Saved-only finalization for observed following before a lane change."""
import argparse
import hashlib
import json
from pathlib import Path

from following import measure


def _original(attempt, acquisition, name):
    path = attempt/name
    record = acquisition.get(name, {})
    if not path.is_file() or record.get('kind') != 'original_native':
        raise ValueError('Missing required source: '+name)
    if hashlib.sha256(path.read_bytes()).hexdigest() != record.get('sha256'):
        raise ValueError('stale original Native source: '+name)
    return path


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _diagnostic(attempt):
    path = attempt/'fixture-provenance.json'
    if not path.is_file():
        return False
    value = json.loads(path.read_text())
    if value.get('diagnostic_fixture') is not True or value.get('physical_acceptance_claimed') is not False:
        raise ValueError('untrusted diagnostic fixture provenance')
    return True


def build_report(attempt):
    attempt = Path(attempt)
    config = json.loads((attempt/'config.json').read_text())
    case_id = config['selected_case_id']
    value = measure(attempt, case_id, diagnostic=_diagnostic(attempt))
    return {'format': 'worker-analysis-report',
            'measurements': {
                'following_spacing_measurement': {'value': value,
                    'method': 'measure', 'sources': value['sources']},
                'following_speed_traffic_condition_measurement': {'value': {
                    'ego_speed_mps': value['mean_ego_speed_mps'],
                    'leader_speed_mps': value['mean_leader_speed_mps'],
                    'relative_speed_mps': value['mean_relative_speed_mps'],
                    'traffic_count': value['mean_surrounding_vehicle_count'],
                    'precipitation_percent': value['mean_native_precipitation_strength'],
                    'fog_percent': value['mean_native_fog_density'],
                    'tire_friction': value['mean_observed_tire_friction'],
                    'hill_crest_station_m': value['hill_crest_station_m']},
                    'method': 'measure', 'sources': value['sources']}},
            'limitations': ['Reasonable and prudent following distance remains a legal judgment.',
                            'Physical motion, public-highway status and pixels need independent review.'],
            'analysis_complete': True, 'legal_verdict_claimed': False}


def saved_result(attempt, report):
    from worker_exchange.native_output import physical_result, validate_result
    attempt = Path(attempt)
    config = json.loads((attempt/'config.json').read_text())
    construction = json.loads((attempt/'construction.json').read_text())
    planned = construction['recording_description']
    acquisition = json.loads((attempt/'acquisition.json').read_text())
    history = _rows(_original(attempt, acquisition, 'following-history.jsonl'))
    frame_map = _rows(_original(attempt, acquisition, 'video_frames.jsonl'))
    if len(history) != len(frame_map) or any(
            (row['frame'], row['time_s']) != (frame['carla_frame'], frame['time_s'])
            for row, frame in zip(history, frame_map)):
        raise ValueError('original camera/following frame join changed')
    context = json.loads(_original(attempt, acquisition, 'following-context.json').read_text())
    output = attempt/'channels'
    output.mkdir(exist_ok=True)
    streams = {
        'ego_leader_body_speed_history': [(row['time_s'],
            {'ego': row['ego'], 'leader': row['leader']}) for row in history],
        'traffic_condition_history': [(row['time_s'],
            {'traffic_actor_ids': row.get('traffic_actor_ids'),
             'surrounding_vehicle_count': row['surrounding_vehicle_count'],
             'highway_condition': row['highway_condition']}) for row in history],
        'following_lane_history': [(row['time_s'], row['lane_change']) for row in history],
        'camera_frame_map': [(row['time_s'], frame)
                             for row, frame in zip(history, frame_map)]}
    evidence = []
    for channel in planned['channels']:
        name = channel['name']
        if name not in streams:
            raise ValueError('unsupported declared channel: '+name)
        path = output/(name+'.jsonl')
        with path.open('x') as stream:
            for time_s, value in streams[name]:
                stream.write(json.dumps({'time_s': time_s, 'value': value},
                                        allow_nan=False)+'\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': str(path.relative_to(attempt))})
    context_path = output/'context.json'
    with context_path.open('x') as stream:
        stream.write(json.dumps({'following_context': context,
            'highway_status': 'unresolved_requires_independent_review'},
            allow_nan=False)+'\n')
    for item in planned['context_inputs']:
        evidence.append({'name': item['name'], 'unit': item['unit'],
                         'reference': str(context_path.relative_to(attempt))})
    value = report['measurements']['following_spacing_measurement']['value']
    target = value['steady_frame_count'] >= 3 and value['lane_change_first_frame'] is not None
    result = {'case_id': config['selected_case_id'], 'measured_values': value,
        'target_checks': [{'target': 'source-grounded moving following across hill crest before lane change',
            'requested': True, 'measured': target, 'method': 'measure',
            'tolerance': 0, 'matched': target, 'physical_cause_confirmed': False,
            'cause_evidence': value['sources']}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Saved source assessment pending physical review',
        'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
        'video_references': ['overview.mkv', 'approach.mkv',
                             'reference_corner.mkv', 'driver_reference.mkv'],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': planned, 'recording_evidence': evidence,
        'realized_observables': {}}
    result = physical_result(attempt, result)
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = build_report(args.attempt)
    result = saved_result(args.attempt, report)
    report['physical_checks'] = result['physical_checks']
    report['realized_observables'] = result['realized_observables']
    with (Path(args.attempt)/'result.json').open('x') as stream:
        stream.write(json.dumps(result, indent=2)+'\n')
    with Path(args.output).open('x') as stream:
        stream.write(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
