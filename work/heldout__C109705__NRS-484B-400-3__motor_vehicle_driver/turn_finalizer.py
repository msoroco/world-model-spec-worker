"""Saved-only C109705 original-source turn finalization; no legal verdict."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from turn_source_measurement import measure


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def measure_turn(root, case):
    for name in ('turn_road_geometry.json', 'body_footprints.jsonl',
                 'video_frames.jsonl'):
        if not (root / name).is_file():
            raise ValueError('Missing required source: ' + name)
    return measure(root, case)


def analyze(attempt):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    from turn_native import check_config
    check_config(config)
    case = config['selected_case_id']
    observed = measure_turn(root, case)
    return {'format': 'worker-analysis-report', 'case_id': case,
            'measurements': {'turn_original_position': {'method': 'measure_turn',
                'value': observed, 'sources': observed['source_sha256']}},
            'limitations': ['Source geometry and body position do not decide nearest practicable placement or legal compliance.',
                            'Actual camera visibility requires independent source-pixel review.'],
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    observed = report['measurements']['turn_original_position']['value']
    rows = observed['observations']
    channel = root / 'turn_centerline_offset.jsonl'
    if channel.exists():raise ValueError('Retain prior derived turn channel')
    channel.write_text(''.join(json.dumps({'frame': row['frame'],
        'time_s': row['time_s'], 'value': row['approach_signed_corner_offsets_m']}) + '\n'
        for row in rows))
    evidence = [{'name': 'turn_centerline_offset', 'unit': 'm',
                 'reference': channel.name, 'sha256': digest(channel)}]
    result = {'case_id': config['selected_case_id'],
        'measured_values': {'turn_original_position': observed},
        'target_checks': [{'target': 'original approach and departure body position',
            'requested': 'retained full-body left turn',
            'measured': observed['departure_min_original_corner_to_left_curb_m'],
            'method': 'original body-corner distance to surveyed left curb',
            'tolerance': None, 'matched': False,
            'physical_cause_confirmed': False,
            'cause_evidence': 'Native motion and map review pending'}],
        'setup_confirmed': False, 'behavior_attempted': True,
        'maneuver_completed': False,
        'termination_reason': 'Saved source measurement complete; physical turn and practicability unverified',
        'physical_failure_flags': {'detection_validated': False},
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['case']['recording_description'],
        'recording_evidence': evidence,
        'realized_observables': {'approach_nearest_corner_offset_m': {
            'unit': 'm', 'method': 'original body/centerline geometry',
            'time_window': 'approach', 'statistic': 'min',
            'reference': channel.name,
            'value': observed['approach_nearest_corner_offset_m'],
            'sample_window_s': [rows[0]['time_s'], rows[-1]['time_s']]}},
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
    from worker_exchange.native_output import physical_result
    return physical_result(root, result)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True); args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():raise ValueError('Retain prior turn analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':main()
