"""Saved-only original-source indicator and turn-clearance measurement."""
import argparse
from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path

from turn_signal_measurement import measure as measure_sources

CASE = 'heldout__C111610__NRS-484B-413-1__motor_vehicle_driver__pedestrian_horn_before_turn'
SOURCES = ('ego_turn_motion.jsonl', 'ego_signal_audio.jsonl',
           'affected_participants.json', 'participant_bodies.jsonl',
           'listener_audio_original.jsonl', 'horn_actuation.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path, sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_turn_indicator(root):
    return measure_sources(*(required(root, name)[0] for name in SOURCES[:4]))


def measure_listener_offset(root, measurement):
    """Measure listener cross-track distance from original pre-turn positions."""
    motion = rows(required(root, 'ego_turn_motion.jsonl')[0])
    bodies = rows(required(root, 'participant_bodies.jsonl')[0])
    audio = rows(required(root, 'listener_audio_original.jsonl')[0])
    context = json.loads(required(root, 'affected_participants.json')[0].read_text())
    route = json.loads(required(root, 'turn_scene_context.json')[0].read_text())
    heading = route['approach_heading_xy']
    length = hypot(*heading)
    if not isfinite(length) or length < 1e-9:
        raise ValueError('Original approach heading is invalid')
    hx, hy = (heading[0] / length, heading[1] / length)
    onset = measurement['turn_onset_frame']
    listener = context['listener_id']
    if not len(motion) == len(bodies) == len(audio):
        raise ValueError('Original listener, body and ego inventories differ')
    x0, y0 = motion[0]['x_m'], motion[0]['y_m']
    offsets = []
    for ego, body, sound in zip(motion, bodies, audio):
        frame = ego['frame']
        if body['frame'] != frame or sound['frame'] != frame or sound['listener_id'] != listener:
            raise ValueError('Original listener/body/ego frame join differs')
        if frame >= onset:
            break
        if not isinstance(sound.get('samples'), list) or not sound['samples']:
            raise ValueError('Independent listener PCM missing before turn')
        point = body['bodies'][listener]
        offset = abs(hx * (point['y_m'] - y0) - hy * (point['x_m'] - x0))
        if not isfinite(offset):
            raise ValueError('Original listener offset is not finite')
        offsets.append(offset)
    if not offsets:
        raise ValueError('No original pre-turn listener offset samples')
    return max(offsets)


def analyze(attempt, *, write_channel=True):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json')[0].read_text())
    if (config.get('selected_case_id'), config.get('law_id'), config.get('cell_id'),
            config.get('actor')) != (CASE, 'NRS-484B-413-1', 'C111610', 'motor_vehicle_driver'):
        raise ValueError('Wrong exact vehicle-indicator analysis identity')
    measurement = measure_turn_indicator(root)
    listener_offset = measure_listener_offset(root, measurement)
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
        (root / 'listener_route_lateral_offset_m.json').write_text(json.dumps({
            'listener_route_lateral_offset_m': listener_offset,
            'source_frames_before_turn': measurement['turn_onset_frame'],
            'source_sha256': {name: required(root, name)[1] for name in
                              ('ego_turn_motion.jsonl', 'participant_bodies.jsonl',
                               'listener_audio_original.jsonl', 'turn_scene_context.json')}
        }, allow_nan=False) + '\n')
    sources = {name: required(root, name)[1] for name in
               (*SOURCES, 'video_frames.jsonl', 'trace.jsonl', *VIDEOS)}
    return {'format': 'worker-analysis-report', 'case_id': CASE,
            'measurements': {'turn_signal_observation': {'method': 'measure_turn_indicator',
                                                        'value': measurement,
                                                        'sources': sources},
                             'listener_route_lateral_offset_m': {'value': listener_offset,
                                                                 'method': 'source-joined independent listener PCM, participant bodies and ego turn motion'}},
            'limitations': ['Synthetic diagnostic listener samples and relay acknowledgement do not prove actual horn sound, pedestrian effect or legal audibility.'],
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
    evidence.append({'name': 'listener_route_lateral_offset_m', 'unit': 'm',
                     'reference': 'listener_route_lateral_offset_m.json',
                     'sha256': required(root, 'listener_route_lateral_offset_m.json')[1]})
    listener_offset = report['measurements']['listener_route_lateral_offset_m']['value']
    return {'case_id': CASE,
            'measured_values': {'turn_signal_observation': value},
            'target_checks': [{'target': 'left turn with relay-requested horn and a pedestrian potentially affected',
                               'requested': 'source-observed listener PCM and participant clearance',
                               'measured': value['max_pre_turn_listener_audio_rms'],
                               'method': 'original listener PCM, Native indicator readback and participant bounds',
                               'tolerance': None, 'matched': False,
                               'physical_cause_confirmed': False,
                               'cause_evidence': 'Originals joined; real microphone timing, physical horn sound and legal audibility pending'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved turn signals measured; physical and legal outcomes unverified',
            'physical_failure_flags': {'visibility_validated': False},
            'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description,
            'recording_evidence': evidence,
            'realized_observables': {'listener_route_lateral_offset_m': {
                'unit': 'm', 'method': 'source-joined independent listener PCM, participant bodies and ego turn motion',
                'time_window': 'original frames before measured turn onset', 'statistic': 'max',
                'reference': 'listener_route_lateral_offset_m.json', 'value': listener_offset},
                'turn_signal_observation': {
                'unit': 'structured', 'method': 'original frame-joined turn/indicator observation',
                'time_window': 'all 8 s original frames', 'statistic': 'maximum pre-turn listener PCM RMS',
                'reference': 'turn_signal_observation.jsonl',
                'value': value['max_pre_turn_listener_audio_rms'],
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
