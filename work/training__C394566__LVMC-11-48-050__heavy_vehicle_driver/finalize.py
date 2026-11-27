"""Finalize sealed restriction source facts without asserting legal or physical acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

from route_measurement import evaluate

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_activation(facts):
    return {'vehicle_over_8000_lb': facts['vehicle_over_8000_lb'],
            'residence_district': facts['residence_district'],
            'non_truck_route': facts['non_truck_route']}


def measure_night_window(facts):
    return {'night_window': facts['night_window'],
            'clock_endpoint_unresolved': facts['night_window'] == 'endpoint_unresolved'}


def measure_night_exit(facts):
    return {'night_window': facts['night_window'],
            'six_am_endpoint_unresolved': facts['night_window'] == 'endpoint_unresolved'}


def measure_movement(facts):
    return {'observed_movement': facts['observed_movement']}


def measure_permit(facts):
    return {'written_permit_status': facts['written_permit_status'],
            'permit_scope_and_conditions_verified': False}


def measure_reviewed_scope(facts):
    return {'restricted_street_source_required': True,
            'residence_district': facts['residence_district'],
            'non_truck_route': facts['non_truck_route'],
            'observed_movement': facts['observed_movement']}


def write_channel(path, frame_map, rows, name, facts):
    with path.open('x') as stream:
        for frame, row in zip(frame_map, rows):
            value = ({'road_id': row['road_id'], 'x_m': row.get('ego_x_m'),
                      'y_m': row.get('ego_y_m'), 'speed_mps': row['ego_speed_mps']}
                     if name == 'ego_pose' else
                     {'road_id': row['road_id'], 'speed_mps': row['ego_speed_mps'],
                      'vehicle_over_8000_lb': facts['vehicle_over_8000_lb'],
                      'night_window': facts['night_window'],
                      'residence_district': facts['residence_district'],
                      'non_truck_route': facts['non_truck_route'],
                      'written_permit_status': facts['written_permit_status'],
                      'permit_scope_and_conditions_verified': False})
            stream.write(json.dumps({'time_s': frame['time_s'], 'value': value}, allow_nan=False)+'\n')


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    config = json.loads((attempt/'config.json').read_text())
    case_id = config['case_id']
    joined = evaluate(attempt, case_id)
    facts = joined['factual_measurements']
    for name in ('trace.jsonl', *[x+'.mkv' for x in CAMERAS]):
        sha(attempt/name)
    mapping = [json.loads(line) for line in (attempt/'video_frames.jsonl').read_text().splitlines()]
    channel_dir = attempt/'channels'; channel_dir.mkdir(exist_ok=True)
    evidence = []
    for channel in config['recording_description']['channels']:
        name = channel['name'];reference = 'channels/'+name+'.jsonl'
        write_channel(attempt/reference, mapping, joined['rows'], name, facts)
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': reference})
    for item in config['recording_description'].get('context_inputs', []):
        evidence.append({'name': item['name'], 'unit': item['unit'],
                         'reference': 'authority-context.json'})
    requested = config.get('requested_motion') != 'stationary'
    motion = facts['observed_movement']
    target = {'target': 'observed original vehicle movement in requested phase',
              'requested': requested, 'measured': motion,
              'method': 'sealed original Native speed/frame source join',
              'tolerance': 0, 'matched': requested == motion,
              'physical_cause_confirmed': False,
              'cause_evidence': ['original-route-rows.jsonl', 'video_frames.jsonl']}
    result = {'case_id': case_id, 'measured_values': {'restriction_facts': facts},
              'target_checks': [target], 'setup_confirmed': False,
              'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'Source-joined facts measured; original authority and physical review pending',
              'physical_failure_flags': ['original_authority_and_physical_review_pending'],
              'trace_reference': 'trace.jsonl',
              'video_references': [x+'.mkv' for x in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import physical_result, write_result
    write_result(attempt, physical_result(attempt, result))
    sources = {'authority-context.json': sha(attempt/'authority-context.json'),
               'original-route-rows.jsonl': sha(attempt/'original-route-rows.jsonl'),
               'video_frames.jsonl': sha(attempt/'video_frames.jsonl'),
               'capture-seal.json': sha(attempt/'capture-seal.json')}
    for key, ref in joined['context']['authority_refs'].items():
        sources[ref['path']] = sha(attempt/ref['path'])
    measurements = {}
    for key, method in (('activation_facts', measure_activation),
                        ('night_window_facts', measure_night_window),
                        ('night_exit_facts', measure_night_exit),
                        ('movement_facts', measure_movement),
                        ('permit_facts', measure_permit),
                        ('reviewed_scope_facts', measure_reviewed_scope)):
        measurements[key] = {'value': method(facts), 'method': method.__name__,
                             'sources': sources}
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': measurements, 'source_complete': True,
              'diagnostic_fixture': joined['source_kind'] == 'synthetic_native_sample',
              'original_authority_reviewed': False,
              'physical_or_legal_acceptance': False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output),sort_keys=True,allow_nan=False))
