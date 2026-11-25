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
    joined = join_original(rows(root / sources[0]), rows(root / sources[1]),
                           rows(root / sources[2]), config)
    capture_join = join_capture(rows(root / sources[0]), rows(root / sources[3]),
                                rows(root / sources[4]))
    joined.update(capture_join)
    sealed = (root / 'capture-seal.json').is_file()
    original_audit = audit_attempt(root, config) if sealed else None
    return {'config': config, 'join': joined, 'sealed_native_audit': original_audit,
            'source_hashes': {name: sha(root / name) for name in sources},
            'original_native_source': sealed}


def finalize(attempt, output):
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    report_source = measure(attempt)
    config = report_source['config']
    joined = report_source['join']
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
              'recording_evidence': [{'name': 'red_entry_observation', 'unit': 'structured',
                                      'reference': 'red-entry-original.jsonl'}],
              'realized_observables': {'first_roadway_footprint_frame': {
                  'value': joined['first_roadway_footprint_frame'], 'unit': 'frame',
                  'method': 'original walker footprint/FrameMap join',
                  'time_window': '30 s source window', 'statistic': 'first_entry',
                  'reference': 'red-entry-original.jsonl'}},
              'provenance_kind': 'native' if original else 'synthetic_cpu',
              'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    if (attempt / 'result.json').exists():
        raise ValueError('Saved processing must not overwrite prior Native result')
    report = {'format': 'c111331-red-entry-saved-analysis-v1',
              'case_id': config['case_id'],
              'measurements': {'red_entry_observation': {
                  'method': 'measure', 'value': joined,
                  'sources': report_source['source_hashes']}},
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
