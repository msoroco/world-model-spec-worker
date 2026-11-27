"""Process retained bus source into measured speed and review context."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_speed import CAMERAS, measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def measure_school_bus_speed(observation):
    return {'maximum_observed_mph': observation['maximum_observed_mph'],
            'frames_above_55_mph': observation['frames_above_55_mph'],
            'judged_driver_actor_id': observation['judged_driver_actor_id'],
            'bus_actor_id': observation['bus_actor_id'],
            'pupils_aboard_reviewed': observation['pupils_aboard_reviewed'],
            'legal_verdict': None}


def finalize(attempt, output):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text())
    construction = json.loads(required(root, 'construction.json').read_text())
    case = config.get('selected_case_id')
    if case != construction.get('case_id') or case not in {
            config['assignment_id'] + '__' + str(speed) for speed in (53, 55, 57)}:
        raise ValueError('Saved case identity differs')
    for name in ('bus_motion.jsonl', 'video_frames.jsonl', 'passenger_trip_review.json',
                 'trace.jsonl', 'capture/evidence.jsonl', 'road.xodr'):
        required(root, name)
    for name in CAMERAS:
        required(root, name + '.mkv')
    observation = measure(root)
    frames = [json.loads(x) for x in (root / 'video_frames.jsonl').read_text().splitlines()]
    motion = [json.loads(x) for x in (root / 'bus_motion.jsonl').read_text().splitlines()]
    trace = [json.loads(x) for x in (root / 'trace.jsonl').read_text().splitlines()]
    events = [json.loads(x) for x in (root / 'capture/evidence.jsonl').read_text().splitlines()]
    if any(len(rows) != 600 for rows in (frames, motion, trace, events)):
        raise ValueError('Full 600-frame saved source required')
    for frame, state, event in zip(frames, trace, events):
        native = frame['native_frame']
        if state.get('frame') != native or event.get('original_frame') != native:
            raise ValueError('Saved bus, trace and evidence frame join differs')
    review = json.loads((root / 'passenger_trip_review.json').read_text())
    diagnostic = review['review_kind'] == 'synthetic_diagnostic'
    inputs = ('bus_motion.jsonl', 'video_frames.jsonl', 'passenger_trip_review.json')
    values = measure_school_bus_speed(observation)
    measurements = {'school_bus_speed_' + str(i): {'method': 'measure_school_bus_speed',
        'value': values, 'sources': {name: sha(root / name) for name in inputs}}
        for i in range(3)}
    channels = root / 'channels'
    channels.mkdir(exist_ok=True)
    evidence = []
    for item in config['recording_description']['channels']:
        name = item['name']
        target = channels / (name + '.jsonl')
        with target.open('x') as stream:
            for frame, row, state in zip(frames, motion, trace):
                value = state['position_m'] if name == 'ego_pose' else row['velocity_mps']
                stream.write(json.dumps({'time_s': frame['time_s'], 'value': value}) + '\n')
        evidence.append({'name': name, 'unit': item['unit'],
                         'reference': 'channels/' + target.name})
    for item in config['recording_description']['context_inputs']:
        name = item['name']
        target = channels / (name + '.json')
        target.write_text(json.dumps({name: review}, sort_keys=True) + '\n')
        evidence.append({'name': name, 'unit': item['unit'],
                         'reference': 'channels/' + target.name})
    result = {'case_id': case,
        'measured_values': {'maximum_observed_mph': observation['maximum_observed_mph'],
                            'frames_above_55_mph': len(observation['frames_above_55_mph']),
                            'legal_result': None},
        'target_checks': [{'target': 'requested_speed_mph',
            'requested': config['requested_speed_mph'],
            'measured': observation['maximum_observed_mph'],
            'method': '600 joined original post-tick velocity samples',
            'tolerance': 0, 'matched': False, 'physical_cause_confirmed': False,
            'cause_evidence': list(inputs)}],
        'setup_confirmed': not diagnostic, 'behavior_attempted': not diagnostic,
        'maneuver_completed': not diagnostic,
        'termination_reason': 'synthetic diagnostic window' if diagnostic else 'full original source window',
        'physical_failure_flags': ['original_school_bus_driver_pupils_and_trip_review_pending'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': evidence,
        'realized_observables': {'school_bus_speed_mph': {'value': observation['maximum_observed_mph'],
            'unit': 'mph', 'method': 'saved velocity norm', 'time_window': '600 frames',
            'statistic': 'maximum', 'reference': 'bus_motion.jsonl'}},
        'provenance_kind': 'synthetic_cpu' if diagnostic else 'native',
        'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    if (root / 'result.json').exists():
        raise ValueError('Saved processing cannot overwrite a prior result')
    (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    report = {'format': 'school-bus-saved-speed-analysis-v1', 'case_id': case,
              'measurements': measurements, 'source_speed': observation,
              'original_native_source': not diagnostic, 'legal_verdict': None}
    Path(output).write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
