"""Recorded-only NRS 484B.497 measurement and Native result finalizer."""
import argparse
import hashlib
import json
from pathlib import Path

from parking_saved_measure import ASSIGNMENT, CAMERAS, measure
from source_review import join

SOURCES = ('road.xodr', 'road-context.json', 'road-review.json',
           'vehicle-pose.jsonl', 'video_frames.jsonl', 'trace.jsonl',
           'capture/evidence.jsonl', 'source_context/one_way_designation.txt',
           'source_context/street_boundary.txt', 'source_context/device_inventory.txt')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_one_way_parking(metric):
    return {'fully_left_rest_candidate_frames': metric['fully_left_rest_candidate_frames'],
            'other_rest_candidate_frames': metric['other_rest_candidate_frames'],
            'permission_device_sourced': metric['permission_device_sourced'],
            'device_id': metric['device_id'], 'legal_result': None}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain previous analysis; use a fresh attempt')
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case_id = config['case_id']
    if case_id != construction['case_id'] or not case_id.startswith(ASSIGNMENT + '__'):
        raise ValueError('Selected NRS case differs')
    permission = config['permission_device_requested']
    required = list(SOURCES)
    if permission:
        required += ['source_context/' + name + '.txt' for name in
                     ('device_authority', 'device_content', 'device_erection', 'device_governance')]
    for name in (*required, *(camera + '.mkv' for camera in CAMERAS)):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    context = join(attempt, case_id, permission)
    poses = [json.loads(row) for row in (attempt / 'vehicle-pose.jsonl').read_text().splitlines()]
    mapped = [json.loads(row) for row in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    if len(poses) != len(mapped) or len(poses) != 600:
        raise ValueError('Original pose and frame-map length differs')
    for pose, frame in zip(poses, mapped):
        if any(pose.get(key) != frame.get(key) for key in
               ('video_frame', 'native_frame', 'camera_native_frames')) or abs(pose['time_s'] - frame['time_s']) > 1e-8:
            raise ValueError('Original pose and camera frame identity differs')
    packet = {'assignment_id': ASSIGNMENT, 'source_kind': context['source_kind'],
              'vehicle_id': poses[0]['vehicle_id'], 'frames': poses}
    metric = measure(json.dumps(packet, sort_keys=True).encode(),
                     json.dumps(context, sort_keys=True).encode())
    source_hashes = {name: sha(attempt / name) for name in required}
    value = measure_one_way_parking(metric)
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': {'one_way_parking': {'method': 'measure_one_way_parking',
                                                   'value': value, 'sources': source_hashes}},
              'diagnostic_fixture': context['source_kind'] == 'synthetic_native_sample',
              'physical_or_legal_acceptance': False}
    channels = attempt / 'channels'
    channels.mkdir()
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for frame in mapped:
                stream.write(json.dumps({'time_s': frame['time_s'], 'value': value}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': 'channels/' + path.name})
    result = {'case_id': case_id, 'measured_values': value,
              'target_checks': [{'target': 'full vehicle footprint at rest on left side',
                                 'requested': True,
                                 'measured': bool(metric['fully_left_rest_candidate_frames']),
                                 'method': 'original Native footprint and speed with sourced road direction',
                                 'tolerance': 0,
                                 'matched': bool(metric['fully_left_rest_candidate_frames']),
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': required}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': '600-frame saved diagnostic; physical and legal review pending',
              'physical_failure_flags': ['Actual one-way designation, device authority and maneuver require independent review'],
              'trace_reference': 'trace.jsonl',
              'video_references': [camera + '.mkv' for camera in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': ('synthetic_local_diagnostic' if
                                  context['source_kind'] == 'synthetic_native_sample' else 'original_native'),
              'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
