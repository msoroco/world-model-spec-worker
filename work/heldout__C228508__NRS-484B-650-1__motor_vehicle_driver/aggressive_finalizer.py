"""Saved-only, source-bound measurement for NRS 484B.650(1).

Event annotations are hypotheses that require independent review under each
cross-referenced law. This finalizer only joins them to original frames and
measures the candidate one-mile window.
"""

import argparse
from hashlib import sha256
import json
from math import hypot
from pathlib import Path

from aggressive_window_measurement import measure


ASSIGNMENT = 'heldout__C228508__NRS-484B-650-1__motor_vehicle_driver'
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')


def _required(root, name):
    path = root / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path, sha256(path.read_bytes()).hexdigest()


def _rows(path):
    try:
        return [json.loads(line) for line in path.read_text().splitlines()
                if line.strip()]
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid original frame source: ' + path.name) from error


def measure_aggressive_window(trace_path, event_path, source_root):
    return measure(trace_path, event_path, source_root)


def analyze(attempt):
    root = Path(attempt)
    config_path, _ = _required(root, 'config.json')
    config = json.loads(config_path.read_text())
    case_id = config.get('selected_case_id')
    if (not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + '__')
            or (config.get('law_id'), config.get('cell_id'), config.get('actor'))
            != ('NRS-484B-650-1', 'C228508', 'motor_vehicle_driver')):
        raise ValueError('Wrong exact aggressive-driving case identity')
    map_path, map_sha = _required(root, 'video_frames.jsonl')
    trace_path, trace_sha = _required(root, 'driving_trace.jsonl')
    event_path, event_sha = _required(root, 'event_annotations.json')
    mapping, trace = _rows(map_path), _rows(trace_path)
    if len(mapping) != len(trace) or len(trace) < 3:
        raise ValueError('Original driving trace and frame map length differ')
    for index, (video, motion) in enumerate(zip(mapping, trace)):
        if (video.get('video_frame') != index or
                (video.get('carla_frame'), video.get('time_s')) !=
                (motion.get('frame'), motion.get('time_s'))):
            raise ValueError('Original driving trace/frame-map join failed')
    observed = measure_aggressive_window(trace_path, event_path, root)
    if observed['original_frame_count'] != len(mapping):
        raise ValueError('Window measurement frame count differs')
    return {
        'format': 'worker-analysis-report', 'case_id': case_id,
        'measurements': {'aggressive_window_observation': {
            'method': 'measure_aggressive_window', 'value': observed,
            'sources': {'video_frames.jsonl': map_sha,
                        'driving_trace.jsonl': trace_sha,
                        'event_annotations.json': event_sha,
                        **observed['sources']}}},
        'limitations': [
            'Event labels are reviewed hypotheses, not established predicate violations.',
            'A candidate window does not establish an immediate-hazard or aggressive-driving legal judgment.',
        ],
        'physical_acceptance_claimed': False,
        'legal_acceptance_claimed': False,
    }


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    description = config.get('case', {}).get('recording_description')
    if not isinstance(description, dict):
        raise ValueError('Selected recording description missing')
    trace = _rows(root / 'driving_trace.jsonl')
    channel = root / 'path_length_m.jsonl'
    if channel.exists():
        raise ValueError('Retain prior derived path-length channel')
    distance = 0.0
    output = []
    previous = None
    for row in trace:
        if previous is not None:
            distance += hypot(row['x_m'] - previous['x_m'],
                              row['y_m'] - previous['y_m'])
        output.append({'frame': row['frame'], 'time_s': row['time_s'],
                       'value': distance})
        previous = row
    channel.write_text(''.join(json.dumps(row, allow_nan=False) + '\n'
                               for row in output))
    actor_source, actor_sha = _required(root, 'following_sources.jsonl')
    actor_context = root / 'original_actor_and_road_context.json'
    if actor_context.exists():
        raise ValueError('Retain prior actor and road context')
    actor_context.write_text(json.dumps({'original_actor_and_road_context': {
        'frame_count': len(trace),
        'frame_map_sha256': sha256((root / 'video_frames.jsonl').read_bytes()).hexdigest(),
        'actor_source': actor_source.name, 'actor_source_sha256': actor_sha,
        'road_source': 'road.xodr' if (root / 'road.xodr').is_file() else None,
        'road_source_sha256': sha256((root / 'road.xodr').read_bytes()).hexdigest()
        if (root / 'road.xodr').is_file() else None,
        'scope': 'original-source pointers; physical and legal review pending'
    }}, indent=2) + '\n')
    legal_context = root / 'governing_cross_referenced_rule.json'
    if legal_context.exists():
        raise ValueError('Retain prior cited-rule context')
    legal_context.write_text(json.dumps({'governing_cross_referenced_rule': {
        'source': 'frozen NRS 484B.650(1) assignment and its cited predicate provisions',
        'status': 'independent review pending', 'legal_judgment': None
    }}, indent=2) + '\n')
    observed = report['measurements']['aggressive_window_observation']['value']
    window = observed['candidate_window']
    return {
        'case_id': report['case_id'],
        'measured_values': {'aggressive_window_observation': observed},
        'target_checks': [{
            'target': 'candidate events within one continuous mile',
            'requested': 'speed, two listed acts and immediate hazard hypothesis',
            'measured': {'candidate_window': window,
                         'total_driving_path_m': observed['total_driving_path_m']},
            'method': 'source-cited original 20 Hz path and event frame join',
            'tolerance': None, 'matched': False,
            'physical_cause_confirmed': False,
            'cause_evidence': 'Original predicate and hazard sources need independent review',
        }],
        'setup_confirmed': False, 'behavior_attempted': True,
        'maneuver_completed': False,
        'termination_reason': 'Saved window measured; physical and legal findings pending',
        'physical_failure_flags': {'detection_validated': False},
        'trace_reference': 'trace.jsonl',
        'video_references': list(CAMERAS),
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': description,
        'recording_evidence': [{
            'name': 'path_length_m', 'unit': 'm',
            'reference': 'path_length_m.jsonl',
            'sha256': sha256(channel.read_bytes()).hexdigest()},
            {'name': 'original_actor_and_road_context', 'unit': 'source packet',
             'reference': actor_context.name,
             'sha256': sha256(actor_context.read_bytes()).hexdigest()},
            {'name': 'governing_cross_referenced_rule', 'unit': 'sourced legal context',
             'reference': legal_context.name,
             'sha256': sha256(legal_context.read_bytes()).hexdigest()}],
        'realized_observables': {
            'path_length_m': {'unit': 'm', 'method': 'original frame path integration',
                              'time_window': 'full original driving trace',
                              'statistic': 'last', 'reference': 'path_length_m.jsonl',
                              'value': distance,
                              'sample_window_s': [trace[0]['time_s'], trace[-1]['time_s']]},
        },
        'physical_acceptance_claimed': False,
        'legal_acceptance_claimed': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior aggressive-driving analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
