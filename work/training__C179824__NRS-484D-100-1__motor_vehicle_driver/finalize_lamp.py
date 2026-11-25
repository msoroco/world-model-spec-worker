"""Recorded-only source review and finalization for the selected device branch."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lamp_saved_measure import CAMERAS, measure_original


REVIEW_SOURCES = {
    'highway_source_sha256': 'highway-review.json',
    'vehicle_class_source_sha256': 'vehicle-class-review.json',
    'device_content_source_sha256': 'device-content-review.json',
    'device_authority_source_sha256': 'device-authority-review.json',
    'device_placement_source_sha256': 'device-placement-review.json',
    'device_timing_source_sha256': 'device-timing-review.json',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(root, name):
    path = root / name
    require(path.is_file(), 'Missing required original source: ' + name)
    return path.read_bytes()


def finalize(attempt, output):
    root, output = Path(attempt), Path(output)
    require(not output.exists() and not (root / 'result.json').exists(),
            'fresh saved-only finalization required')
    config = json.loads(read(root, 'config.json'))
    case_id = config.get('case_id')
    require(case_id in config.get('supported_case_ids', []) and
            case_id in (
                'training__C179824__NRS-484D-100-1__motor_vehicle_driver__controlled_1',
                'training__C179824__NRS-484D-100-1__motor_vehicle_driver__controlled_2'),
            'selected lamp case identity missing')
    poses = read(root, 'vehicle-lamps.jsonl')
    frame_map = read(root, 'video_frames.jsonl')
    road = read(root, 'road.xodr')
    context_raw = read(root, 'lamp-context.json')
    context = json.loads(context_raw)
    require(context.get('map_source_sha256') == sha(road),
            'reviewed OpenDRIVE hash differs')
    require(context.get('source_kind') in ('native_saved_sample', 'synthetic_native_sample'),
            'original or explicit diagnostic provenance missing')
    review_hashes = {}
    for field, name in REVIEW_SOURCES.items():
        raw = read(root, name)
        require(context.get(field) == sha(raw),
                'independent review source hash differs: ' + name)
        review = json.loads(raw)
        require(review.get('case_id') == case_id and review.get('review_kind') in
                ('original_source_review', 'synthetic_diagnostic'),
                'independent review identity missing: ' + name)
        require(review.get('review_kind') == (
            'original_source_review' if context['source_kind'] == 'native_saved_sample'
            else 'synthetic_diagnostic'), 'review provenance differs: ' + name)
        review_hashes[name] = sha(raw)
    for camera in CAMERAS:
        video = root / (camera + '.mkv')
        if context['source_kind'] == 'native_saved_sample':
            require(video.is_file(), 'Missing original camera video: ' + camera)
    observation = measure_original(poses, frame_map, context_raw, road)
    original_rows = [json.loads(line) for line in poses.splitlines() if line.strip()]
    trace_rows = []
    channel_rows = []
    for row in original_rows:
        xy = row.get('vehicle_xy_m')
        require(isinstance(xy, list) and len(xy) == 2 and
                all(type(value) in (int, float) for value in xy),
                'original vehicle position missing')
        trace_rows.append({'frame': row['native_frame'], 'time_s': row['time_s'],
                           'position': {'x': xy[0], 'y': xy[1], 'z': 0},
                           'position_m': [xy[0], xy[1], 0],
                           'heading_deg': 0, 'speed_mps': row['speed_mps'],
                           'speed_mph': row['speed_mps'] / 0.44704,
                           'velocity_mps': [row['speed_mps'], 0, 0],
                           'control': {}})
        channel_rows.append({'time_s':row['time_s'],
                             'value':{'headlamp_setting_on':row['headlamp_setting_on'],
                                      'position_lamp_setting_on':row['position_lamp_setting_on'],
                                      'device_active':row['device_active']}})
    (root / 'trace.jsonl').write_text(''.join(json.dumps(row, allow_nan=False) + '\n'
                                            for row in trace_rows))
    channels = root / 'channels'
    channels.mkdir(exist_ok=True)
    (channels / 'native_lamp_setting.jsonl').write_text(''.join(
        json.dumps(row, allow_nan=False) + '\n' for row in channel_rows))
    expected_on = case_id.endswith('controlled_1')
    governed = observation['governed_frames']
    both = observation['both_settings_on_frames']
    matched = bool(governed) and (set(governed) == set(both) if expected_on
                                  else not bool(both))
    source_hashes = {name: sha(read(root, name)) for name in
                     ('vehicle-lamps.jsonl', 'video_frames.jsonl', 'road.xodr',
                      'lamp-context.json')}
    source_hashes.update(review_hashes)
    analysis = {'format': 'worker-analysis-report-v1', 'case_id': case_id,
                'measurements': {'lamp_device_measurement': {
                    'method': 'original_frame_map_join_and_independent_review',
                    'value': observation, 'sources': source_hashes}},
                'legal_verdict_claimed': False}
    result = {'case_id': case_id, 'measured_values': observation,
              'target_checks': [{'target': 'device-directed lamp setting on governed frames',
                                 'requested': 'on' if expected_on else 'off',
                                 'measured': {'governed_frames': len(governed),
                                              'both_settings_on_frames': len(both)},
                                 'method': 'original Native light-state readback and independently sourced device review',
                                 'tolerance': None,
                                 'matched': matched,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(source_hashes)}],
              'setup_confirmed': False, 'behavior_attempted': True,
              'maneuver_completed': False,
              'termination_reason': 'independent original pixels and legal review pending',
              'physical_failure_flags': ['original pixel and device authority review pending'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': [{'name':'native_lamp_setting', 'unit':'boolean',
                                      'reference':'channels/native_lamp_setting.jsonl'},
                                     {'name':'lamp_context', 'unit':'structured',
                                      'reference':'lamp-context.json'}],
              'realized_observables': {},
              'provenance_kind': context['source_kind'],
              'diagnostic_fixture': context['source_kind'] == 'synthetic_native_sample',
              'accepted': False, 'legal_verdict_claimed': False}
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + '\n')
    (root / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return analysis


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
