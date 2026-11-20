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
CHANNELS = ('source_frame_and_civil_time', 'lane_and_subject_direction',
            'direction_device_source', 'four_camera_source', 'observed_direction')


def _load(root, name):
    path = root / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
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
    derived = {
        'source_frame_and_civil_time': [
            {'civil_time': row['civil_time'], 'source': row['civil_time_source'],
             'period_id': row['period_id']} for row in observations],
        'lane_and_subject_direction': [
            {'lane_id': row['lane_id'], 'travel_alignment': row['travel_alignment']}
            for row in observations],
        'direction_device_source': [
            {'source_id': row['device_source_id'], 'kind': row['device_kind'],
             'period_id': row['period_id']} for row in observations],
        'four_camera_source': [True for _ in observations],
        'observed_direction': [row['observed_direction'] for row in observations],
    }
    if write_channels:
        if any((root / (name + '.jsonl')).exists() for name in CHANNELS):
            raise ValueError('Retain prior derived direction channel')
        for name, values in derived.items():
            (root / (name + '.jsonl')).write_text(''.join(json.dumps({
                'frame': row['frame'], 'time_s': row['time_s'], 'value': value}) + '\n'
                for row, value in zip(observations, values)))
    source_hashes = {name: hashes[name] for name in SOURCE_FILES if name != 'config.json'}
    period_value = {'period_id': observations[0]['period_id'],
                    'first_civil_time': observations[0]['civil_time'],
                    'last_civil_time': observations[-1]['civil_time'],
                    'designated_direction': rows[0]['device']['direction_xy'],
                    'observed_direction': expected}
    return {
        'format': 'worker-analysis-report', 'case_id': case_id,
        'measurements': {'period_direction': {
            'method': 'analyze', 'sources': source_hashes, 'value': period_value},
            'reversible_direction': {
            'method': 'analyze', 'sources': source_hashes,
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
    paths = {name: root / (name + '.jsonl') for name in CHANNELS}
    if any(not path.is_file() for path in paths.values()):
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
        'recording_evidence': [{'name': item['name'], 'unit': item['unit'],
                                'reference': paths[item['name']].name,
                                'sha256': hashlib.sha256(paths[item['name']].read_bytes()).hexdigest()}
                               for item in config.get('case', {}).get('recording_description', {}).get('channels', [])],
        'realized_observables': {'minimum_absolute_alignment': {
            'value': measured['minimum_absolute_alignment'], 'unit': 'ratio',
            'method': 'same-frame source designation versus velocity',
            'time_window': 'all original frames', 'statistic': 'minimum',
            'reference': paths['lane_and_subject_direction'].name}},
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
