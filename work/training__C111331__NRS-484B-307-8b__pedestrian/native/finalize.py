"""Recorded-only red-entry measurement from original source identities.

Physical governance and legal permission are deliberately left for review.
"""

import argparse
import hashlib
import json
from pathlib import Path

from native_red import CAMERAS, check_plan
from source_join import audit_attempt, join_capture, join_original, rows


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def measure_red_signal(samples, config):
    return {'requested_state': config['requested_traffic'],
            'observed_states': sorted({row['traffic']['state'] for row in samples}),
            'head_id': config['traffic_head_id'],
            'original_pixels_interpreted': False}


def measure_entry(joined, config):
    return {'requested_entry': config['requested_entry'],
            'first_roadway_footprint_frame': joined['first_roadway_footprint_frame'],
            'other_device_request': config['requested_other_device'],
            'physical_permission_verified': False}


def measure_scope(joined, config):
    return {'case_id': config['case_id'], 'frames': joined['frames'],
            'original_source_join_passed': joined['original_source_join_passed'],
            'trace_evidence_join_passed': joined['trace_evidence_join_passed']}


def channel_value(name, sample, telemetry, config):
    if name == 'dev.traffic_signal':
        return sample['traffic']
    if name == 'dev.pedestrian_signal':
        return {'other': sample['other'], 'display_program': sample['display_program']}
    if name == 'dev.governs':
        return {'head_id': config['traffic_head_id'],
                'pedestrian_facing_review_pending': True}
    if name in ('kin.position', 'ru.pedestrian', 'ru.subject'):
        return {'walker_id': sample['walker_id'],
                'position_m': telemetry['position_m']}
    if name == 'kin.heading':
        return telemetry['heading_deg']
    if name == 'rel.occupies':
        return {'footprint_xy_m': sample['footprint_xy_m']}
    if name == 'camera_frame_join':
        return sample['source_rgb_sha256']
    return {'footprint_xy_m': sample['footprint_xy_m'],
            'roadway_y_abs_max_m': config['roadway_y_abs_max_m']}


def write_recording_channels(attempt, config, samples):
    """Write trace-derived observation views without altering acquisition."""
    trace = rows(Path(attempt) / 'trace.jsonl')
    folder = Path(attempt) / 'channels'
    folder.mkdir(exist_ok=True)
    evidence = []
    description = config['recording_description']
    for channel in description['channels']:
        name = channel['name']
        path = folder / (name + '.jsonl')
        with path.open('w') as output:
            for sample, telemetry in zip(samples, trace):
                value = channel_value(name, sample, telemetry, config)
                output.write(json.dumps({'time_s': sample['time_s'], 'value': value}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + path.name})
    context = folder / 'native_red_intersection.json'
    context.write_text(json.dumps({'native_red_intersection': {
        'map': config['map'], 'traffic_head_id': config['traffic_head_id'],
        'other_device_id': config['other_device_id'],
        'physical_governance_verified': False}}) + '\n')
    evidence.append({'name': 'native_red_intersection', 'unit': 'structured',
                     'reference': 'channels/' + context.name})
    return evidence


def measure(root):
    root = Path(root)
    config = json.loads(required(root, 'config.json').read_text())
    check_plan(config)
    sources = ['red-entry-original.jsonl', 'video_frames.jsonl',
               'camera-sources.jsonl', 'trace.jsonl', 'capture/evidence.jsonl']
    for name in sources:
        required(root, name)
    for name, _, _, _ in CAMERAS:
        required(root, name + '.mkv')
    samples = rows(root / sources[0])
    joined = join_original(samples, rows(root / sources[1]),
                           rows(root / sources[2]), config)
    capture_join = join_capture(samples, rows(root / sources[3]),
                                rows(root / sources[4]))
    joined.update(capture_join)
    sealed = (root / 'capture-seal.json').is_file()
    original_audit = audit_attempt(root, config) if sealed else None
    return {'config': config, 'join': joined, 'samples': samples,
            'sealed_native_audit': original_audit,
            'source_hashes': {name: sha(root / name) for name in sources},
            'original_native_source': sealed}


def finalize(attempt, output):
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    report_source = measure(attempt)
    config = report_source['config']
    joined = report_source['join']
    recording_evidence = write_recording_channels(attempt, config, report_source['samples'])
    original = report_source['original_native_source']
    videos = [name + '.mkv' for name, _, _, _ in CAMERAS]
    result = {'case_id': config['case_id'],
              'measured_values': {'red_entry_observation': joined},
              'target_checks': [{'target': 'requested_highway_entry',
                                 'requested': config['requested_entry'],
                                 'measured': joined['first_roadway_footprint_frame'] is not None,
                                 'method': 'original joined walker footprint and authored road boundary',
                                 'tolerance': 0,
                                 'matched': (joined['first_roadway_footprint_frame'] is not None) == config['requested_entry'],
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': ['red-entry-original.jsonl', 'video_frames.jsonl']}],
              'setup_confirmed': original,
              'behavior_attempted': original,
              'maneuver_completed': original and (joined['first_roadway_footprint_frame'] is not None) == config['requested_entry'],
              'termination_reason': 'full original source window' if original else 'synthetic diagnostic window',
              'physical_failure_flags': ['governing_head_and_display_pixels_unreviewed'],
              'trace_reference': 'trace.jsonl', 'video_references': videos,
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config.get('recording_description',
                  'Steady-red pedestrian highway entry and other-device contrast'),
              'recording_evidence': recording_evidence,
              'realized_observables': {'roadway_footprint_frames': {
                  'value': sum(any(abs(point[1]) <= config['roadway_y_abs_max_m']
                                   for point in row['footprint_xy_m'])
                               for row in report_source['samples']), 'unit': 'count',
                  'method': 'original walker footprint/FrameMap join',
                  'time_window': '30 s source window', 'statistic': 'frame_count',
                  'reference': 'red-entry-original.jsonl'}},
              'provenance_kind': 'native' if original else 'synthetic_cpu',
              'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    if (attempt / 'result.json').exists():
        raise ValueError('Saved processing must not overwrite prior Native result')
    report = {'format': 'c111331-red-entry-saved-analysis-v1',
              'case_id': config['case_id'],
              'measurements': {
                  'steady_red_source': {
                      'method': 'measure_red_signal',
                      'value': measure_red_signal(report_source['samples'], config),
                      'sources': {name: report_source['source_hashes'][name]
                                  for name in ('red-entry-original.jsonl', 'video_frames.jsonl')}},
                  'entry_and_other_device_source': {
                      'method': 'measure_entry', 'value': measure_entry(joined, config),
                      'sources': {name: report_source['source_hashes'][name]
                                  for name in ('red-entry-original.jsonl', 'camera-sources.jsonl')}},
                  'intersection_entry_scope': {
                      'method': 'measure_scope', 'value': measure_scope(joined, config),
                      'sources': {name: report_source['source_hashes'][name]
                                  for name in ('red-entry-original.jsonl', 'capture/evidence.jsonl')}},
              },
              'original_native_source': original,
              'original_source_audit': report_source['sealed_native_audit'],
              'display_pixels_reviewed': False,
              'governing_device_verified': False,
              'legal_verdict': None}
    output.write_text(json.dumps(report, indent=2) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))


if __name__ == '__main__':
    main()
