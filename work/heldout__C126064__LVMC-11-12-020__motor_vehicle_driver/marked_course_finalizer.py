"""Finalize an original-source marked-turn attempt without a legal finding."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from marked_course_measurement import measure

ASSIGNMENT = 'heldout__C126064__LVMC-11-12-020__motor_vehicle_driver'
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')
SOURCES = ('marked_intersection.json', 'authority_source_original.json',
           'turn_body.jsonl', 'video_frames.jsonl', 'trace.jsonl', *CAMERAS)


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_marked_course(root, case):
    return measure(root, case)


def analyze(attempt, *, write_channel=True):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text())
    case = config.get('selected_case_id')
    if (case not in (ASSIGNMENT + '__indicated_course', ASSIGNMENT + '__divergent_course')
            or config.get('law_id') != 'LVMC-11-12-020'
            or config.get('cell_id') != 'C126064'
            or config.get('actor') != 'motor_vehicle_driver'):
        raise ValueError('Wrong exact marked-turn analysis identity')
    paths = {name: required(root, name) for name in SOURCES}
    observation = measure_marked_course(root, case)
    mapping = rows(paths['video_frames.jsonl'])
    trace = rows(paths['trace.jsonl'])
    body = rows(paths['turn_body.jsonl'])
    if not len(mapping) == len(trace) == len(body) == observation['frame_count']:
        raise ValueError('Original marked turn, trace and frame inventories differ')
    for index, (frame, point, sample) in enumerate(zip(mapping, trace, body)):
        identity = frame['carla_frame'], frame['time_s']
        if (frame['video_frame'] != index or
                (point.get('frame'), point.get('time_s')) != identity or
                (sample.get('frame'), sample.get('time_s')) != identity):
            raise ValueError('Original marked turn and trace join differs')
    if write_channel:
        channel = root / 'original_marked_turn_course.jsonl'
        if channel.exists():
            raise ValueError('Derived marked-turn channel already exists')
        channel.write_text(''.join(json.dumps({'frame': row['frame'], 'time_s': row['time_s'],
                                              'value': row}, allow_nan=False) + '\n'
                                   for row in observation['observations']))
    source_hashes = {name: sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}
    return {'format': 'worker-analysis-report', 'case_id': case,
            'measurements': {'original_marked_turn_course': {
                'method': 'measure_marked_course', 'value': observation, 'sources': source_hashes}},
            'limitations': ['Original municipal authority and marker visibility need independent review; sampled course distances are not legal cutoffs.'],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    description = config['case']['recording_description']
    observation = report['measurements']['original_marked_turn_course']['value']
    channel = required(root, 'original_marked_turn_course.jsonl')
    evidence = [{'name': 'original_marked_turn_course', 'unit': 'structured',
                 'reference': channel.name, 'sha256': sha256(channel.read_bytes()).hexdigest()}]
    return {'case_id': report['case_id'],
            'measured_values': {'original_marked_turn_course': observation},
            'target_checks': [{'target': 'marked municipal turning course',
                'requested': 'original full-body course relative to sourced physical markers',
                'measured': observation['frame_count'],
                'method': 'source-hashed intersection, physical marker and frame-joined body measurement',
                'tolerance': None, 'matched': False, 'physical_cause_confirmed': False,
                'cause_evidence': 'Original source join measured; authority, pixels and legal course conformance pending'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved turn course measured; physical and legal outcomes unverified',
            'physical_failure_flags': {'visibility_validated': False},
            'trace_reference': 'trace.jsonl', 'video_references': list(CAMERAS),
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description, 'recording_evidence': evidence,
            'realized_observables': {'original_marked_turn_course': {
                'unit': 'structured', 'method': 'source-joined original full-body course',
                'time_window': 'all recorded original frames',
                'statistic': 'sample count', 'reference': channel.name,
                'value': observation['frame_count'],
                'sample_window_s': [observation['observations'][0]['time_s'],
                                    observation['observations'][-1]['time_s']]}},
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior marked-turn analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
