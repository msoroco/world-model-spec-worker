"""Saved-only school-bus speed and trip-context analysis; no legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_speed import CAMERAS, measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def measure_school_bus_speed(speed):
    return {'maximum_observed_mph': speed['maximum_observed_mph'],
            'frames_above_55_mph': speed['frames_above_55_mph'],
            'pupils_aboard_reviewed': speed['pupils_aboard_reviewed'],
            'observed_pupil_count': speed['observed_pupil_count'],
            'legal_verdict': None}


def finalize(attempt, output):
    root = Path(attempt)
    config = json.loads(require(root, 'config.json').read_text())
    for name in ('bus_motion.jsonl', 'video_frames.jsonl', 'passenger_trip_review.json',
                 'trace.jsonl', 'capture/evidence.jsonl'):
        require(root, name)
    for camera in CAMERAS:
        require(root, camera + '.mkv')
    speed = measure(root)
    frames = [json.loads(line) for line in (root / 'video_frames.jsonl').read_text().splitlines()]
    motion = [json.loads(line) for line in (root / 'bus_motion.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in (root / 'trace.jsonl').read_text().splitlines()]
    events = [json.loads(line) for line in (root / 'capture/evidence.jsonl').read_text().splitlines()]
    if any(len(rows) != 600 for rows in (frames, motion, trace, events)):
        raise ValueError('Full 600-frame saved source required')
    for frame, state, event in zip(frames, trace, events):
        original = frame['native_frame']
        if state.get('frame') != original or event.get('original_frame') != original:
            raise ValueError('Saved bus, trace and evidence frame join differs')
    review = json.loads((root / 'passenger_trip_review.json').read_text())
    diagnostic = review['review_kind'] == 'synthetic_diagnostic'
    inputs = ('bus_motion.jsonl', 'video_frames.jsonl', 'passenger_trip_review.json')
    measurements = {'school_bus_speed': {'method': 'measure_school_bus_speed',
        'value': measure_school_bus_speed(speed),
        'sources': {name: sha(root / name) for name in inputs}}}
    channels = root / 'channels'
    channels.mkdir(exist_ok=True)
    recording = []
    for item in config['recording_description']['channels']:
        name = item['name']
        path = channels / (name.replace('/', '_') + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': frame['time_s'],
            'value': {'native_frame': frame['native_frame'],
                      'velocity_mps': row['velocity_mps'],
                      'source_kind': row['source_kind']}}, separators=(',', ':')) + '\n'
            for frame, row in zip(frames, motion)))
        recording.append({'name': name, 'unit': item['unit'],
                          'reference': 'channels/' + path.name})
    for item in config['recording_description']['context_inputs']:
        name = item['name']
        path = channels / (name + '.json')
        path.write_text(json.dumps({name: review}, separators=(',', ':')) + '\n')
        recording.append({'name': name, 'unit': item['unit'],
                          'reference': 'channels/' + path.name})
    requested = config['requested_speed_mph']
    result = {'case_id': config['case_id'],
        'measured_values': {'maximum_observed_mph': speed['maximum_observed_mph'],
                            'frames_above_55_mph': len(speed['frames_above_55_mph']),
                            'legal_result': None},
        'target_checks': [{'target': 'requested_speed_mph', 'requested': requested,
            'measured': speed['maximum_observed_mph'],
            'method': '600 source-joined original post-tick velocity samples',
            'tolerance': 0, 'matched': False, 'physical_cause_confirmed': False,
            'cause_evidence': ['bus_motion.jsonl', 'passenger_trip_review.json']}],
        'setup_confirmed': not diagnostic, 'behavior_attempted': not diagnostic,
        'maneuver_completed': not diagnostic,
        'termination_reason': 'full original source window' if not diagnostic else 'synthetic diagnostic window',
        'physical_failure_flags': ['original_school_bus_pupil_and_trip_review_pending'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': recording,
        'realized_observables': {'school_bus_speed_mph': {'value': speed['maximum_observed_mph'],
            'unit': 'mph', 'method': 'saved original velocity norm',
            'time_window': '600 frames', 'statistic': 'maximum',
            'reference': 'bus_motion.jsonl'}},
        'provenance_kind': 'synthetic_cpu' if diagnostic else 'native',
        'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    if (root / 'result.json').exists():
        raise ValueError('Saved processing cannot overwrite a prior result')
    (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    report = {'format': 'school-bus-saved-speed-analysis-v1', 'case_id': config['case_id'],
              'measurements': measurements, 'source_speed': speed,
              'original_native_source': not diagnostic, 'legal_verdict': None}
    Path(output).write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = finalize(args.attempt, args.output)
    print(json.dumps({'case_id': report['case_id'], 'source_frames': 600,
                      'legal_verdict': None}))


if __name__ == '__main__':
    main()
