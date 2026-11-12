"""Saved original-source finalizer for the two one-way left-turn approaches."""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
from one_way_finalizer import finalize

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('video_frames.jsonl', 'native/footprints.jsonl', 'native/road_edges.jsonl')

def measure_original_one_way(root, case):
    root = Path(root)
    for name in SOURCES:
        if not (root / name).is_file():
            raise ValueError('Missing required source: ' + name)
    result = finalize(root)
    if not case.endswith(('__left_edge_reference', '__approach_shifted_right', '__departure_shifted_right')):
        raise ValueError('Wrong selected one-way left-turn case')
    return result

def analyze(attempt):
    root = Path(attempt)
    cfg = json.loads((root / 'config.json').read_text())
    if (cfg.get('law_id'), cfg.get('cell_id'), cfg.get('actor')) != (
            'NRS-484B-400-5', 'C152976', 'motor_vehicle_driver'):
        raise ValueError('Wrong exact one-way turn identity')
    case = cfg['selected_case_id']
    measured = measure_original_one_way(root, case)
    return {'format': 'worker-analysis-report', 'case_id': case,
            'measurements': {'one_way_curb_history': {
                'method': 'measure_original_one_way', 'value': measured,
                'sources': measured['source_sha256']}},
            'limitations': ['Synthetic CPU fixture does not prove Native curb identity, physical motion, camera visibility or legal practicability.'],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}

def build_result(attempt, report):
    root = Path(attempt)
    cfg = json.loads((root / 'config.json').read_text())
    measured = report['measurements']['one_way_curb_history']['value']
    channel = root / 'one_way_curb_gap_m.jsonl'
    if channel.exists():
        raise ValueError('Retain prior one-way derived channel')
    channel.write_text(''.join(json.dumps({'frame': i, 'time_s': row['time_s'],
                                           'value': row['left_body_to_curb_gap_m'],
                                           'segment': row['segment']}) + '\n'
                               for i, row in enumerate(measured['samples'])))
    evidence = [{'name': 'one_way_curb_gap_m', 'unit': 'm', 'reference': channel.name,
                 'sha256': sha256(channel.read_bytes()).hexdigest()}]
    result = {'case_id': report['case_id'], 'measured_values': {'one_way_curb_history': measured},
        'target_checks': [{'target': 'measured approach and departure body to left curb gaps',
                           'requested': 'retained full-body one-way left turn',
                           'measured': [measured['minimum_approach_gap_m'], measured['minimum_departure_gap_m']],
                           'method': 'original body corners and sourced curb lines',
                           'tolerance': None, 'matched': False, 'physical_cause_confirmed': False,
                           'cause_evidence': 'Native curb provenance and physical turn review pending'}],
        'setup_confirmed': False, 'behavior_attempted': True, 'maneuver_completed': False,
        'termination_reason': 'Saved one-way curb measurement complete; physical turn unverified',
        'physical_failure_flags': {'detection_validated': False},
        'trace_reference': 'trace.jsonl', 'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': cfg['case']['recording_description'],
        'recording_evidence': evidence,
        'realized_observables': {'one_way_curb_gap_m': {'unit': 'm',
             'method': 'original full-body left edge relative to separately sourced approach/departure curbs',
             'time_window': 'all original frames', 'statistic': 'segment minima',
             'reference': channel.name,
             'value': min(measured['minimum_approach_gap_m'],
                          measured['minimum_departure_gap_m']),
             'sample_window_s': [measured['samples'][0]['time_s'], measured['samples'][-1]['time_s']]}},
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior one-way report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))

if __name__ == '__main__':
    main()
