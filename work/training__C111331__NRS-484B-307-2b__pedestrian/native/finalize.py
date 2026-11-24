"""Saved-only measurement of crossing entry; no indication-pixel or legal claim."""
import argparse
import hashlib
import json
from pathlib import Path

from saved_source_bridge import join


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def measure(root):
    config = json.loads(required(root, 'config.json').read_text())
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-307-2b', 'C111331', 'pedestrian'):
        raise ValueError('Frozen pedestrian case identity differs')
    crosswalk = {'id': 'C111331-authored-marked-crosswalk',
                 'bounds_xy': [-1.5, -3.5, 1.5, 3.5]}
    governance = {'traffic_head': config['traffic_head_id'],
                  'pedestrian_head': config['pedestrian_head_id']}
    return join(root, crosswalk, governance)


def finalize(attempt, output):
    attempt = Path(attempt).resolve()
    config = json.loads(required(attempt, 'config.json').read_text())
    result = measure(attempt)
    entry = result['measurement']
    recorded_entry = {key: value for key, value in entry.items()
                      if key != 'legal_verdict'}
    mapping = required(attempt, 'video_frames.jsonl')
    trace = required(attempt, 'trace.jsonl')
    required(attempt, 'capture/evidence.jsonl')
    videos = [name + '.mkv' for name in result['source_camera_names']]
    for name in videos:
        required(attempt, name)
    observations = attempt / 'pedestrian-entry-observations.jsonl'
    with observations.open('w') as stream:
        for line in required(attempt, 'c111331-native-samples.jsonl').read_text().splitlines():
            sample = json.loads(line)
            value = {'pedestrian_xy_m': sample['pedestrian_xy_m'],
                     'traffic_signal': sample['observed_traffic_signal'],
                     'pedestrian_signal': sample['observed_pedestrian_signal']}
            stream.write(json.dumps({'time_s': sample['time_s'], 'value': value}) + '\n')
    native_result = {
        'case_id': config['case_id'],
        'measured_values': {'pedestrian_entry_signal': recorded_entry},
        'target_checks': [{'target': 'crosswalk_entry', 'requested': True,
            'measured': entry['entry_frame'] is not None,
            'method': 'saved Native-shaped pose and signal frame join',
            'tolerance': 0, 'matched': entry['entry_frame'] is not None,
            'physical_cause_confirmed': False,
            'cause_evidence': ['c111331-native-samples.jsonl', 'video_frames.jsonl']}],
        'setup_confirmed': True, 'behavior_attempted': True,
        'maneuver_completed': True, 'termination_reason': 'full saved diagnostic duration',
        'physical_failure_flags': ['original_signal_pixels_and_governance_unverified'],
        'trace_reference': 'trace.jsonl', 'video_references': videos,
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [{'name': 'pedestrian_entry_signal', 'unit': 'structured',
            'reference': observations.name}],
        'realized_observables': {'entry_frame': {'value': entry['entry_frame'],
            'unit': 'frame', 'method': 'source-hashed saved pose/signal join',
            'time_window': '30 s diagnostic', 'statistic': 'first_entry',
            'reference': 'c111331-native-samples.jsonl'}},
        'provenance_kind': 'synthetic_cpu', 'accepted': False,
        'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(native_result)
    report = {'format': 'c111331-saved-analysis-v2', 'case_id': config['case_id'],
        'measurements': {'pedestrian_entry_signal': {'method': 'measure',
            'value': entry, 'sources': {
                'c111331-native-samples.jsonl': sha(required(attempt, 'c111331-native-samples.jsonl')),
                'video_frames.jsonl': sha(mapping)}}},
        'source_bridge': {'native_samples_sha256': result['native_samples_sha256'],
            'video_map_sha256': result['video_map_sha256'],
            'source_video_sha256': result['source_video_sha256']},
        'actual_signal_pixels_reviewed': False,
        'governing_direction_physically_verified': False,
        'legal_verdict': None}
    output.write_text(json.dumps(report, indent=2) + '\n')
    with (attempt / 'result.json').open('w') as stream:
        json.dump(native_result, stream, indent=2)
        stream.write('\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
