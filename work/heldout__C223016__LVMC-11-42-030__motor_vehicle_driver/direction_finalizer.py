"""Saved-only direction analysis for original reversible-lane source rows.

The source stream must come from a completed Native capture. This module never
constructs device authority or substitutes a diagnostic fixture for it.
"""

import argparse
import hashlib
import json
from pathlib import Path

from reversible_direction import measure_direction


SOURCE_FILES = ('config.json', 'direction_state.jsonl', 'video_frames.jsonl',
                'trace.jsonl')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _load(root, name):
    path = root / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing original source: ' + name)
    return path.read_bytes(), hashlib.sha256(path.read_bytes()).hexdigest()


def _json_lines(data, name):
    try:
        rows = [json.loads(line) for line in data.decode().splitlines() if line.strip()]
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid original source: ' + name) from error
    if not rows:
        raise ValueError('Empty original source: ' + name)
    return rows


def analyze(attempt, *, write_channels=False):
    root = Path(attempt)
    loaded = {name: _load(root, name) for name in SOURCE_FILES}
    hashes = {name: digest for name, (_, digest) in loaded.items()}
    config = json.loads(loaded['config.json'][0])
    case_id = config.get('selected_case_id', '')
    prefix = 'heldout__C223016__LVMC-11-42-030__motor_vehicle_driver__'
    if (config.get('cell_id'), config.get('law_id'), config.get('actor')) != (
            'C223016', 'LVMC-11-42-030', 'motor_vehicle_driver') or not case_id.startswith(prefix):
        raise ValueError('Wrong exact reversible-lane identity')
    suffix = case_id[len(prefix):]
    rows = _json_lines(loaded['direction_state.jsonl'][0], 'direction_state.jsonl')
    frame_map = _json_lines(loaded['video_frames.jsonl'][0], 'video_frames.jsonl')
    trace = _json_lines(loaded['trace.jsonl'][0], 'trace.jsonl')
    if len(rows) != len(frame_map) or len(rows) != len(trace):
        raise ValueError('Original direction/frame/trace lengths differ')
    for index, (row, mapping, traced) in enumerate(zip(rows, frame_map, trace)):
        if mapping.get('video_frame') != index or mapping.get('carla_frame') != row.get('frame'):
            raise ValueError('Original video frame mapping differs')
        if mapping.get('time_s') != row.get('time_s') or traced.get('frame') != row.get('frame') or traced.get('time_s') != row.get('time_s'):
            raise ValueError('Original source frame/time join differs')
    observations = measure_direction(rows, case_suffix=suffix, lane_id=config.get('governed_lane_id'))
    expected = 'against_designation' if suffix.endswith('_against') else 'with_designation'
    if any(row['observed_direction'] != expected for row in observations):
        raise ValueError('Source direction differs from exact case target')
    channel = 'observed_direction'
    channel_path = root / (channel + '.jsonl')
    if write_channels:
        if channel_path.exists():
            raise ValueError('Retain prior derived direction channel')
        channel_path.write_text(''.join(json.dumps({
            'frame': row['frame'], 'time_s': row['time_s'],
            'value': row['observed_direction']}) + '\n' for row in observations))
    return {
        'format': 'worker-analysis-report', 'case_id': case_id,
        'measurements': {'reversible_direction': {
            'method': 'analyze', 'sources': hashes,
            'value': {'frames': len(observations), 'lane_id': config['governed_lane_id'],
                      'period_id': observations[0]['period_id'],
                      'device_source_id': observations[0]['device_source_id'],
                      'device_kind': observations[0]['device_kind'],
                      'direction': expected,
                      'minimum_absolute_alignment': min(abs(x['travel_alignment']) for x in observations),
                      'first_civil_time': observations[0]['civil_time'],
                      'last_civil_time': observations[-1]['civil_time'],
                      'legal_judgment': None}}},
        'limitations': ['Device source observation does not establish City Traffic Engineer authorization, public legibility, or a legal violation.'],
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    channel = root / 'observed_direction.jsonl'
    if not channel.is_file():
        raise ValueError('Saved direction channel absent')
    measured = report['measurements']['reversible_direction']['value']
    config = json.loads((root / 'config.json').read_text())
    return {
        'case_id': report['case_id'], 'measured_values': {'reversible_direction': measured},
        'target_checks': [{'target': 'source-observed travel versus effective lane designation',
                           'requested': measured['direction'], 'measured': measured['direction'],
                           'method': 'continuous original same-frame lane/device/velocity join',
                           'tolerance': None, 'matched': True,
                           'physical_cause_confirmed': False,
                           'cause_evidence': 'Original source readback only; authority and legibility unresolved'}],
        'setup_confirmed': False, 'behavior_attempted': True,
        'maneuver_completed': False,
        'termination_reason': 'Saved direction measurement complete; physical outcome unverified',
        'physical_failure_flags': {'authority_unverified': True, 'visual_legibility_unverified': True},
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config.get('case', {}).get('recording_description', {}),
        'recording_evidence': [{'name': 'observed_direction', 'unit': 'category',
                                'reference': channel.name,
                                'sha256': hashlib.sha256(channel.read_bytes()).hexdigest()}],
        'realized_observables': {'observed_direction': {
            'value': measured['direction'], 'unit': 'category',
            'method': 'same-frame source designation versus velocity',
            'time_window': 'all original frames', 'statistic': 'per-frame agreement',
            'reference': channel.name}},
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt, write_channels=True)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior direction report')
    output.write_text(json.dumps(report, indent=2) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
