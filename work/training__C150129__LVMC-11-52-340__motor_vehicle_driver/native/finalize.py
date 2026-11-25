"""Saved-only municipal parking diagnostic over original Native samples."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from parking_measure import ASSIGNMENT, measure
from source_review import join


SOURCES = ('vehicle-poses.jsonl', 'parking-inventory.json', 'review.json',
           'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
           'source_context/city_street.txt',
           'source_context/council_designation.txt',
           'source_context/posting_or_marking.txt',
           'source_context/subject_vehicle_status.txt')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_municipal_street_parking(metric):
    return {'space_id': metric['space_id'],
            'occupied_frames': metric['occupied_frames'],
            'stationary_proxy_frames': metric['stationary_proxy_frames'],
            'occupied_and_stationary_proxy_frames': metric['occupied_and_stationary_proxy_frames'],
            'city_street_source_id': metric['city_street_source_id'],
            'council_designation_source_id': metric['council_designation_source_id'],
            'posting_or_marking_source_id': metric['posting_or_marking_source_id'],
            'subject_status_source_id': metric['subject_status_source_id'],
            'legal_result': None}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain previous analysis; use a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'config.json', 'construction.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case_id = config['case_id']
    if (case_id != construction['case_id'] or
            case_id not in (ASSIGNMENT + '__controlled_1', ASSIGNMENT + '__controlled_2')):
        raise ValueError('Exact municipal parking case differs')
    inventory = json.loads((attempt / 'parking-inventory.json').read_text())
    review = json.loads((attempt / 'review.json').read_text())
    if review['case_id'] != case_id:
        raise ValueError('Independent source review binds another case')
    joined = join(attempt, inventory, review)
    frames = [json.loads(line) for line in (attempt / 'vehicle-poses.jsonl').read_text().splitlines()]
    if not frames:
        raise ValueError('Missing original vehicle poses')
    packet = {'assignment_id': ASSIGNMENT, 'source_kind': inventory['source_kind'],
              'vehicle_id': frames[0]['vehicle_id'], 'frames': frames}
    metric = measure(json.dumps(packet, sort_keys=True).encode(),
                     json.dumps(joined, sort_keys=True).encode())
    sample_map = [json.loads(line) for line in
                  (attempt / 'video_frames.jsonl').read_text().splitlines()]
    if len(sample_map) != metric['frame_count'] or any(
            row.get('video_frame') != i or row.get('native_frame') != frames[i]['native_frame']
            for i, row in enumerate(sample_map)):
        raise ValueError('Original video and vehicle frame identity differs')
    source_hashes = {name: _sha(attempt / name) for name in SOURCES}
    measurement = measure_municipal_street_parking(metric)
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': {'municipal_street_parking': {
                  'method': 'measure_municipal_street_parking',
                  'value': measurement, 'sources': source_hashes}},
              'diagnostic_fixture': inventory['source_kind'] == 'synthetic_native_sample',
              'physical_or_legal_acceptance': False}
    channels = attempt / 'channels'
    channels.mkdir()
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for row in sample_map:
                stream.write(json.dumps({'time_s': row['time_s'],
                                         'value': measurement}, allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + path.name})
    target_inside = config['parking_case'] == 'inside_city_space'
    measured_inside = bool(metric['occupied_and_stationary_proxy_frames'])
    result = {
        'case_id': case_id, 'measured_values': measurement,
        'target_checks': [{'target': 'full subject footprint stationary proxy in designated space',
                           'requested': target_inside, 'measured': measured_inside,
                           'method': 'original Native pose and speed, joined to source-reviewed space polygon',
                           'tolerance': 0, 'matched': target_inside == measured_inside,
                           'physical_cause_confirmed': False,
                           'cause_evidence': list(SOURCES)}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': '600-frame saved parking diagnostic; independent physical review pending',
        'physical_failure_flags': ['Native parking maneuver and source assertions require independent review'],
        'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': construction['recording_description'],
        'recording_evidence': evidence, 'realized_observables': {},
        'provenance_kind': ('synthetic_local_diagnostic' if
                            inventory['source_kind'] == 'synthetic_native_sample' else 'original_native'),
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
