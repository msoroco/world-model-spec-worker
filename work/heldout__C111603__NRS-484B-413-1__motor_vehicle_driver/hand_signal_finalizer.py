"""Saved-only original-source indicator and turn-clearance measurement."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from turn_signal_measurement import measure as measure_sources
from turn_hand_signal import measure as measure_hand

CASE = 'heldout__C111603__NRS-484B-413-1__motor_vehicle_driver__vehicle_hand_signal'
SOURCES = ('ego_turn_motion.jsonl', 'ego_signal_audio.jsonl',
           'affected_participants.json', 'participant_bodies.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path, sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_turn_indicator(root):
    return measure_sources(*(required(root, name)[0] for name in SOURCES))


def analyze(attempt, *, write_channel=True):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json')[0].read_text())
    if (config.get('selected_case_id'), config.get('law_id'), config.get('cell_id'),
            config.get('actor')) != (CASE, 'NRS-484B-413-1', 'C111603', 'motor_vehicle_driver'):
        raise ValueError('Wrong exact vehicle-indicator analysis identity')
    measurement = measure_turn_indicator(root)
    hand_source, hand_sha = required(root, 'hand_signal_original.jsonl')
    hand_measurement = measure_hand(hand_source, root / 'ego_turn_motion.jsonl')
    motion = rows(root / 'ego_turn_motion.jsonl')
    mapping = rows(required(root, 'video_frames.jsonl')[0])
    trace = rows(required(root, 'trace.jsonl')[0])
    if not len(mapping) == len(trace) == len(motion):
        raise ValueError('Original turn, trace and video frame inventories differ')
    for index, (map_row, trace_row, ego_row) in enumerate(zip(mapping, trace, motion)):
        identity = map_row.get('carla_frame'), map_row.get('time_s')
        if (map_row.get('video_frame') != index or
                (trace_row.get('frame'), trace_row.get('time_s')) != identity or
                (ego_row.get('frame'), ego_row.get('time_s')) != identity):
            raise ValueError('Original turn/video frame join differs')
    for name in VIDEOS:
        required(root, name)
    if write_channel:
        channel = root / 'turn_signal_observation.jsonl'
        if channel.exists():
            raise ValueError('Derived turn channel already exists')
        channel.write_text(''.join(json.dumps({'frame': row['frame'], 'time_s': row['time_s'],
                                               'value': {'yaw_change_deg': row['yaw_change_deg'],
                                                         'indicator_readback': row['indicator_readback'],
                                                         'listener_audio_rms': row['listener_audio_rms']}},
                                              allow_nan=False) + '\n'
                                   for row in measurement['observations']))
        hand_channel = root / 'hand_signal_observation.jsonl'
        if hand_channel.exists():
            raise ValueError('Derived hand channel already exists')
        hand_channel.write_text(''.join(json.dumps(row, allow_nan=False) + '\n'
                                        for row in hand_measurement['observations']))
    sources = {name: required(root, name)[1] for name in
               (*SOURCES, 'video_frames.jsonl', 'trace.jsonl', *VIDEOS)}
    return {'format': 'worker-analysis-report', 'case_id': CASE,
            'measurements': {'hand_signal_observation': {'method': 'measure_hand',
                                                       'value': hand_measurement,
                                                       'sources': {'hand_signal_original.jsonl': hand_sha,
                                                                   'ego_turn_motion.jsonl': sources['ego_turn_motion.jsonl']}},
                             'turn_signal_observation': {'method': 'measure_turn_indicator',
                                                        'value': measurement,
                                                        'sources': sources}},
            'limitations': ['Native bone readback and synthetic diagnostic video do not prove visible hand pixels, actual affected status or legal signal adequacy.'],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    description = config['case']['recording_description']
    value = report['measurements']['turn_signal_observation']['value']
    evidence = [{'name': item['name'], 'unit': item['unit'],
                 'reference': item['name'] + '.jsonl',
                 'sha256': required(root, item['name'] + '.jsonl')[1]}
                for item in description['channels']]
    return {'case_id': CASE,
            'measured_values': {'turn_signal_observation': value,
                                'hand_signal_observation': report['measurements']['hand_signal_observation']['value']},
            'target_checks': [{'target': 'left turn without indicator readback with another vehicle potentially affected',
                               'requested': 'source-observed pre-turn indicator and participant clearance',
                               'measured': len(value['pre_turn_indicator_frames']),
                               'method': 'original Native indicator readback and participant bounds',
                               'tolerance': None, 'matched': False,
                               'physical_cause_confirmed': False,
                               'cause_evidence': 'Originals joined; lamp pixels and legal appropriateness pending'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved turn signals measured; physical and legal outcomes unverified',
            'physical_failure_flags': {'visibility_validated': False},
            'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description,
            'recording_evidence': evidence,
            'realized_observables': {'hand_signal_observation': {
                'unit': 'structured', 'method': 'original Native avatar bone world readback',
                'time_window': 'all 8 s original frames', 'statistic': 'frame-joined left hand position',
                'reference': 'hand_signal_observation.jsonl',
                'value': report['measurements']['hand_signal_observation']['value']['frame_count'],
                'sample_window_s': [value['observations'][0]['time_s'], value['observations'][-1]['time_s']]},
                                     'turn_signal_observation': {
                'unit': 'structured', 'method': 'original frame-joined turn/indicator observation',
                'time_window': 'all 8 s original frames', 'statistic': 'pre-turn indicator frame count',
                'reference': 'turn_signal_observation.jsonl',
                'value': len(value['pre_turn_indicator_frames']),
                'sample_window_s': [value['observations'][0]['time_s'], value['observations'][-1]['time_s']]}},
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior turn analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
