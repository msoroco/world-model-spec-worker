"""Saved-only one-way travel analysis; no physical or legal verdict is inferred."""
import argparse
import json
from pathlib import Path

from one_way_saved_measure import CAMERAS, SOURCES, measure


def measure_one_way_travel(metric):
    return {key: metric[key] for key in (
        'movement_direction_measured', 'signed_displacement_m',
        'on_governed_extent_frames', 'opposite_velocity_frames',
        'roadway_designation_sourced', 'sign_official_sourced',
        'sign_erected_sourced', 'sign_governs_road_sourced',
        'physical_sign_pixels_verified')}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain previous analysis; use a fresh attempt')
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case_id = config['case_id']
    if case_id != construction['case_id'] or not case_id.endswith(
            '__' + config['requested_direction']):
        raise ValueError('Selected one-way case identity differs')
    metric = measure(attempt, config['requested_direction'])
    value = measure_one_way_travel(metric)
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': {}, 'diagnostic_fixture':
              json.loads((attempt / 'road-review.json').read_text()).get('synthetic_diagnostic', False),
              'physical_or_legal_acceptance': False}
    for row in json.loads((attempt / 'measurement-contract.json').read_text())['requirements']:
        report['measurements'][row['output_key']] = {
            'method': row['method'], 'value': value,
            'sources': {name: metric['source_hashes'][name] for name in row['inputs']}}
    poses = [json.loads(row) for row in (attempt / 'vehicle-pose.jsonl').read_text().splitlines()]
    mapped = [json.loads(row) for row in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    channels = attempt / 'channels'
    channels.mkdir()
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for frame, pose in zip(mapped, poses):
                stream.write(json.dumps({'time_s': frame['time_s'], 'value': {
                    'native_frame': frame['native_frame'],
                    'footprint_corners_xy_m': pose['footprint_corners_xy_m'],
                    'yaw_deg': pose['yaw_deg'],
                    'movement_direction_measured': value['movement_direction_measured'],
                    'source_hashes': metric['source_hashes']}}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + path.name})
    result = {'case_id': case_id, 'measured_values': value,
              'target_checks': [{'target': 'one-way travel relative to sign',
                                 'requested': config['requested_direction'],
                                 'measured': value['movement_direction_measured'],
                                 'method': 'original Native motion, map and independent sign review',
                                 'tolerance': 0, 'matched':
                                 value['movement_direction_measured'] == config['requested_direction'],
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(SOURCES)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': '600-frame saved diagnostic; original sign pixels and authority require review',
              'physical_failure_flags': ['Original legal designation, sign authority and pixels pending'],
              'trace_reference': 'trace.jsonl',
              'video_references': [camera + '.mkv' for camera in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': ('synthetic_local_diagnostic' if report['diagnostic_fixture']
                                  else 'original_native'), 'accepted': False}
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
