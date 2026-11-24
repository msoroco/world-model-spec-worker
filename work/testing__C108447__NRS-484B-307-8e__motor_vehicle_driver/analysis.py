"""Saved-source property-route measurements for exact diagnostic cases.

These measurements identify original observation fields and source joins. They
do not turn a synthetic fixture into an authoritative parcel or legal finding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from case_observation import audit_case
from property_route import analyze


def required(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources(root, names):
    return {name: sha(required(root, name)) for name in names}


def measure_approach(packet, trace, observation, case_audit):
    return {'device_id': trace['approach_signal']['device_id'],
            'red_alone_through_entry': observation['approach_red_alone_facing_ego'],
            'movement_frame_window': case_audit['approach_state_window']}


def measure_property(packet, trace, observation, case_audit):
    return {'traversed_ids': observation['traversed_property_ids'],
            'statuses': observation['traversed_property_statuses'],
            'route_class': 'roadway' if case_audit['planned_case'] == 'ordinary_crossing' else 'property'}


def measure_destination(packet, trace, observation, case_audit):
    return {'street_id': trace['destination_street_id'],
            'device_id': trace['destination_signal']['device_id'],
            'state_at_entry': case_audit['destination_state_at_entry'],
            'not_facing_red': observation['destination_traffic_not_facing_red']}


def measure_purpose(packet, trace, observation, case_audit):
    return {'separate_source': trace['purpose']['source'],
            'observed_value': case_audit['purpose_value'],
            'avoidance_context': observation['avoidance_purpose_observed_separately']}


def measure_vehicle(packet, trace, observation, case_audit):
    return {'class': trace['actor_class'], 'actor_source': trace['actor_source'],
            'body_frames': len(trace['ego']),
            'destination_entry_frame': trace['destination_entry_frame']}


def canonical_trace_rows(ego):
    return [{'frame': body['frame'], 'time_s': body['time_s'],
             'position': {'x': body['x'], 'y': body['y'], 'z': body.get('z', 0)},
             'position_m': [body['x'], body['y'], body.get('z', 0)],
             'heading_deg': body['yaw_rad'] * 180 / 3.141592653589793,
             'speed_mps': body['speed_mps'],
             'speed_mph': body['speed_mps'] / 0.44704,
             'velocity_mps': body['velocity_mps'],
             'control': body.get('control', {})} for body in ego]


ROWS = (
    ('property_approach_signal', 'measure_approach', ('map-packet.json', 'trace.json')),
    ('property_route_class', 'measure_property', ('road.xodr', 'authority.json', 'map-packet.json', 'trace.json')),
    ('property_destination_signal', 'measure_destination', ('map-packet.json', 'trace.json')),
    ('property_avoidance_purpose', 'measure_purpose', ('trace.json',)),
    ('property_vehicle_route', 'measure_vehicle', ('trace.json',)),
)


def build_report(root):
    root = Path(root).resolve()
    config = json.loads(required(root, 'config.json').read_text())
    case_id = config['selected_case_id']
    if not case_id.startswith('testing__C108447__NRS-484B-307-8e__motor_vehicle_driver__'):
        raise ValueError('Foreign exact property case')
    packet = json.loads(required(root, 'map-packet.json').read_text())
    trace = json.loads(required(root, 'trace.json').read_text())
    authority = required(root, 'authority.json')
    xodr = required(root, 'road.xodr')
    if packet['source']['sha256'] != sha(authority) or packet['native_map']['sha256'] != sha(xodr):
        raise ValueError('Original property/map source seal differs')
    if json.loads(authority.read_text())['opendrive_sha256'] != sha(xodr):
        raise ValueError('Authority/OpenDRIVE source seal differs')
    if trace['case_id'] != case_id:
        raise ValueError('Diagnostic trace case differs')
    observation = analyze(packet, trace, {'case_id': case_id})
    case_audit = audit_case(observation, trace, {'case_id': case_id})
    values = {}
    for key, method, names in ROWS:
        value = globals()[method](packet, trace, observation, case_audit)
        values[key] = {'method': method, 'value': value,
                       'sources': sources(root, names)}
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'analysis_complete': True, 'measurements': values,
            'provenance_kind': 'synthetic_fixture' if packet.get('diagnostic_fixture') else 'original_saved_source',
            'diagnostic_fixture': bool(packet.get('diagnostic_fixture')),
            'legal_verdict_claimed': False, 'physical_acceptance_claimed': False,
            'limitations': ['Parcel authority, purpose and physical movement require independent review.']}


def build_result(root, report):
    """Write only measurements derived from retained source bytes."""
    from worker_exchange.native_output import write_result

    root = Path(root).resolve()
    config = json.loads(required(root, 'config.json').read_text())
    packet = json.loads(required(root, 'map-packet.json').read_text())
    trace = json.loads(required(root, 'trace.json').read_text())
    mapping = [json.loads(line) for line in required(root, 'video_frames.jsonl').read_text().splitlines()]
    ego = trace['ego']
    if len(ego) != len(mapping) or not ego:
        raise ValueError('Original ego/frame map length differs')
    for index, (body, frame) in enumerate(zip(ego, mapping)):
        if (body['frame'] != frame['carla_frame'] or
                abs(body['time_s'] - frame['time_s']) > 1e-6 or
                frame['video_frame'] != index):
            raise ValueError('Original ego/frame map identity differs')
    rows = canonical_trace_rows(ego)
    trace_text = ''.join(json.dumps(row) + '\n' for row in rows)
    trace_path = root / 'trace.jsonl'
    if trace_path.exists():
        if trace_path.read_text() != trace_text:
            raise ValueError('Original converter trace differs from saved ego source')
    else:
        trace_path.write_text(trace_text)
    histories = (trace['approach_signal_history'], trace['destination_signal_history'])
    if any(len(history) != len(ego) for history in histories):
        raise ValueError('Original signal histories differ from ego frames')
    channels = config['case']['recording_description']['channels']
    values = (
        lambda i: {'class': trace['actor_class'], 'source': trace['actor_source']},
        lambda i: histories[0][i],
        lambda i: packet['properties'],
        lambda i: ego[i],
        lambda i: histories[1][i],
        lambda i: trace['purpose'],
        lambda i: mapping[i],
    )
    if len(channels) != len(values):
        raise ValueError('Original recording channel inventory differs')
    evidence = []
    for index, (channel, value) in enumerate(zip(channels, values)):
        name = f'recording-channel-{index}.jsonl'
        stream = [{'time_s': body['time_s'], 'value': value(i)}
                  for i, body in enumerate(ego)]
        (root / name).write_text(''.join(json.dumps(row) + '\n' for row in stream))
        evidence.append({'name': channel['name'], 'unit': channel['unit'],
                         'reference': name})
    context = config['case']['recording_description']['context_inputs'][0]
    context_name = 'recording-map-context.json'
    (root / context_name).write_text(json.dumps({context['name']: {
        'packet_sha256': sha(required(root, 'map-packet.json')),
        'authority_sha256': sha(required(root, 'authority.json')),
        'opendrive_sha256': sha(required(root, 'road.xodr'))}}, indent=2) + '\n')
    evidence.append({'name': context['name'], 'unit': context['unit'],
                     'reference': context_name})
    result = {'case_id': report['case_id'],
              'measured_values': {key: value['value'] for key, value in report['measurements'].items()},
              'target_checks': [{'target': 'source_observation_complete', 'requested': True,
                                 'measured': True, 'method': 'five retained source-bound measurements',
                                 'tolerance': 0, 'matched': True,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': 'physical movement and source authority require review'}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'diagnostic source processing; physical completion unverified',
              'physical_failure_flags': ['physical_completion_unverified'],
              'trace_reference': 'trace.jsonl',
              'video_references': [camera['name'] + '.mkv' for camera in config['cameras']],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['case']['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': report['provenance_kind'],
              'diagnostic_fixture': report['diagnostic_fixture'],
              'legal_verdict_claimed': False, 'physical_acceptance_claimed': False}
    write_result(root, result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = build_report(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Analysis output already exists')
    output.write_text(json.dumps(report, indent=2) + '\n')
    build_result(args.attempt, report)
    print(json.dumps({'case_id': report['case_id'], 'measurements': len(report['measurements'])}))


if __name__ == '__main__':
    main()
