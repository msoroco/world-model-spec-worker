"""Recorded-only sidewalk and other-traffic analysis; no legal claim."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from sidewalk_occupancy import measure_frame

FRAMES = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('vehicle-trace.jsonl', 'traffic-trace.jsonl', 'video_frames.jsonl',
           'camera-frames.jsonl', 'map-packet.json', 'authority-context.json',
           'native-road.xodr')


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(root, name):
    return [json.loads(line) for line in required(root, name).read_text().splitlines()]


def observe(attempt):
    trace = rows(attempt, 'vehicle-trace.jsonl')
    traffic = rows(attempt, 'traffic-trace.jsonl')
    mapping = rows(attempt, 'video_frames.jsonl')
    cameras = rows(attempt, 'camera-frames.jsonl')
    packet = json.loads(required(attempt, 'map-packet.json').read_text())
    authority = json.loads(required(attempt, 'authority-context.json').read_text())
    required(attempt, 'native-road.xodr')
    if (len(trace) != FRAMES or len(traffic) != FRAMES or
            len(mapping) != FRAMES or len(cameras) != 4 * FRAMES):
        raise ValueError('Incomplete original sidewalk source frames')
    if not packet.get('sidewalk_polygon_m') or not packet.get('map_acquisition'):
        raise ValueError('Missing required source: map-packet.json sidewalk geometry')
    stopped = overlap = joined = entire = 0
    first_stop = first_joined = None
    actor_id = trace[0].get('actor_id')
    other_actor_ids = set()
    for i, (row, frame) in enumerate(zip(trace, mapping)):
        if (row.get('frame') != i or frame.get('video_frame') != i or
                row.get('native_frame') != frame.get('native_frame') or
                abs(row['time_s'] - frame['time_s']) > 1e-4 or
                row.get('actor_id') != actor_id or
                set(frame.get('camera_native_frames', {})) != set(CAMERAS)):
            raise ValueError('Original sidewalk frame/time/actor join differs')
        speed = float(row['speed_mps'])
        if not math.isfinite(speed) or speed < 0:
            raise ValueError('Nonfinite original vehicle speed')
        value = measure_frame(row['vehicle_footprint_m'], packet['sidewalk_polygon_m'])
        at_rest = speed <= .05
        stopped += at_rest
        overlap += value['overlap_positive']
        joined += at_rest and value['overlap_positive']
        entire += at_rest and value['entire_vehicle_on_sidewalk']
        if at_rest and first_stop is None:
            first_stop = i
        if at_rest and value['overlap_positive'] and first_joined is None:
            first_joined = i
        other = traffic[i]
        if (other.get('frame') != i or
                other.get('native_frame') != frame.get('native_frame') or
                abs(float(other['time_s']) - frame['time_s']) > 1e-4):
            raise ValueError('Original other-traffic frame/time join differs')
        if other.get('actor_id') is not None:
            if other['actor_id'] == actor_id:
                raise ValueError('Other traffic shares subject actor identity')
            other_actor_ids.add(other['actor_id'])
    actual_cameras = {(row.get('frame'), row.get('camera'), row.get('native_frame'))
                      for row in cameras}
    expected_cameras = {(i, name, mapping[i]['native_frame'])
                        for i in range(FRAMES) for name in CAMERAS}
    if actual_cameras != expected_cameras:
        raise ValueError('Original source camera/image join differs')
    return {'first_rest_frame': first_stop,
            'first_rest_on_sidewalk_frame': first_joined,
            'rest_frames': stopped, 'sidewalk_overlap_frames': overlap,
            'rest_and_overlap_frames': joined,
            'entire_vehicle_on_sidewalk_rest_frames': entire,
            'actor_id': actor_id,
            'other_traffic_actor_count': len(other_actor_ids),
            'other_traffic_trace_complete': True,
            'map_legal_context_complete': all(packet.get(key) for key in (
                'highway_boundary_source', 'property_boundary_source',
                'intended_pedestrian_use_source')),
            'exception_authority_complete': any(authority.get(key) for key in (
                'other_law_authority', 'officer_direction',
                'official_device_direction')),
            'legal_verdict_claimed': False}


def sidewalk_stop(observed, packet, authority):
    return {'rest_and_overlap_frames': observed['rest_and_overlap_frames'],
            'first_rest_on_sidewalk_frame': observed['first_rest_on_sidewalk_frame'],
            'entire_vehicle_on_sidewalk_rest_frames':
                observed['entire_vehicle_on_sidewalk_rest_frames'],
            'map_legal_context_complete': observed['map_legal_context_complete'],
            'exception_authority_complete': observed['exception_authority_complete'],
            'sidewalk_legal_status': packet.get('legal_sidewalk_status'),
            'traffic_conflict_requested': authority.get('traffic_conflict_requested'),
            'legal_conclusion': None}


def traffic_context(observed, packet, authority):
    return {'other_traffic_actor_count': observed['other_traffic_actor_count'],
            'traffic_conflict_requested': authority.get('traffic_conflict_requested'),
            'other_traffic_trace_complete': observed['other_traffic_trace_complete'],
            'necessity_independently_verified': False,
            'legal_conclusion': None}


METHODS = {'sidewalk_stop_occupancy': ('sidewalk_stop', sidewalk_stop),
           'traffic_conflict_context': ('traffic_context', traffic_context)}


def finalize(attempt, output):
    from worker_exchange.native_output import provenance_record, write_result

    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Use fresh recorded-only analysis output')
    config = json.loads(required(attempt, 'config.json').read_text())
    packet = json.loads(required(attempt, 'map-packet.json').read_text())
    authority = json.loads(required(attempt, 'authority-context.json').read_text())
    observed = observe(attempt)
    contract = json.loads(required(attempt, 'measurement-contract.json').read_text())
    hashes = {name: sha(required(attempt, name)) for name in SOURCES}
    measurements = {}
    for requirement in contract['requirements']:
        key = requirement['output_key']
        method, function = METHODS[key]
        if method != requirement['method']:
            raise ValueError('Selected sidewalk measurement method changed')
        measurements[key] = {'method': method,
            'value': function(observed, packet, authority),
            'sources': {name: hashes[name] for name in requirement['inputs']}}
    provenance = provenance_record(attempt)
    original = provenance['provenance_kind'] == 'native' and not provenance['diagnostic_fixture']
    target = True
    matched = (observed['rest_and_overlap_frames'] > 0) == target
    result = {
        'case_id': config['case_id'], 'measured_values': observed,
        'target_checks': [{'target': 'requested sidewalk-stop contrast',
            'requested': {'sidewalk_occupancy': target},
            'measured': {'rest_and_overlap_frames': observed['rest_and_overlap_frames']},
            'method': 'source-joined original post-tick vehicle footprint, speed and map geometry',
            'tolerance': '0.05 m/s rest threshold is diagnostic, not statutory',
            'matched': matched, 'physical_cause_confirmed': False,
            'cause_evidence': list(SOURCES)}],
        'setup_confirmed': False, 'behavior_attempted': original,
        'maneuver_completed': original and matched,
        'termination_reason': '600 original frames retained; map legal status and pixel review pending',
        'physical_failure_flags': [] if matched else ['sidewalk_stop_contrast_not_observed'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [
            {'name': channel['name'], 'unit': channel['unit'],
             'reference': 'vehicle-trace.jsonl'}
            for channel in config['recording_description']['channels']
        ] + [{'name': 'sidewalk_map_context', 'unit': 'structured',
              'reference': 'map-packet.json'},
             {'name': 'exception_authority_context', 'unit': 'structured',
              'reference': 'authority-context.json'},
             {'name': 'other_traffic_trajectory', 'unit': 'structured',
              'reference': 'traffic-trace.jsonl'}],
        'realized_observables': {'rest_and_overlap_frames': {
            'value': observed['rest_and_overlap_frames'], 'unit': 'frames',
            'method': 'source-joined original post-tick vehicle footprint and map geometry',
            'time_window': '600 original frames', 'statistic': 'count',
            'reference': 'vehicle-trace.jsonl'}},
        'provenance_kind': provenance['provenance_kind'],
        'diagnostic_fixture': provenance['diagnostic_fixture'],
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    write_result(attempt, result)
    report = {'format': 'c229977-traffic-conflict-analysis-v1',
        'case_id': config['case_id'], 'analysis_complete': True,
        'measurements': measurements, 'source_hashes': hashes,
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
