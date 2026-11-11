"""Saved-only flashing-yellow measurements from retained original Native samples.

Native light-state readback is kept separate from appearance in original pixels
and from the legal judgment about caution.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def _source(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(attempt, write_channels=True):
    root = Path(attempt)
    paths = {}
    hashes = {}
    for name in ('config.json', 'signal_context.json', 'signal_state.jsonl',
                 'participant_state.jsonl', 'video_frames.jsonl', 'trace.jsonl'):
        paths[name], hashes[name] = _source(root, name)
    config = json.loads(paths['config.json'].read_text())
    context = json.loads(paths['signal_context.json'].read_text())
    case_id = config.get('selected_case_id', '')
    branch = config.get('case_branch')
    from flashing_yellow import CASES
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-310-2', 'C111273', 'motor_vehicle_driver') or branch not in CASES or not case_id.endswith('__' + branch):
        raise ValueError('Wrong exact flashing-yellow identity')
    case = CASES[branch]
    if not context.get('official_control_source') or context.get('selected_direction') != case.direction:
        raise ValueError('Official-control source or governed direction absent')
    if not context.get('opendrive_id'):
        raise ValueError('Governed OpenDRIVE identity absent')
    signal = _rows(paths['signal_state.jsonl'])
    participants = _rows(paths['participant_state.jsonl'])
    frames = _rows(paths['video_frames.jsonl'])
    trace = _rows(paths['trace.jsonl'])
    if len(frames) < 2 or len({len(frames), len(signal), len(participants), len(trace)}) != 1:
        raise ValueError('Original signal source/frame-map length differs')
    observations = []
    last_time = None
    ego_id = None
    crossing_id = None
    light_id = None
    for index, (fm, light, party, motion) in enumerate(zip(frames, signal, participants, trace)):
        frame, time_s = fm.get('carla_frame'), fm.get('time_s')
        if fm.get('video_frame') != index or type(frame) is not int or not isinstance(time_s, (int, float)) or not math.isfinite(time_s):
            raise ValueError('Invalid original frame identity')
        if last_time is not None and (frame <= frames[index-1]['carla_frame'] or abs(time_s-last_time-.05) > .005):
            raise ValueError('Original samples are not consecutive 20 Hz')
        last_time = time_s
        if any(row.get('frame') != frame or row.get('time_s') != time_s for row in (light, party, motion)):
            raise ValueError('Original signal source/frame-map join failed')
        if light_id is None: light_id = light.get('light_actor_id')
        if type(light_id) is not int or light.get('opendrive_id') != context['opendrive_id'] or light.get('light_actor_id') != light_id or light_id != context.get('light_actor_id', light_id):
            raise ValueError('Signal head identity changed')
        native_state = light.get('native_light_state')
        if isinstance(native_state, str) and native_state.startswith('TrafficLightState.'):
            native_state = native_state.removeprefix('TrafficLightState.')
        if type(light.get('yellow_commanded')) is not bool or native_state not in ('Yellow', 'Off'):
            raise ValueError('Missing Native yellow/off readback')
        if (native_state == 'Yellow') != light['yellow_commanded']:
            raise ValueError('Native lamp readback differs from command')
        ego = party.get('ego')
        crossing = party.get('crossing')
        if not isinstance(ego, dict) or type(ego.get('actor_id')) is not int:
            raise ValueError('Missing original ego state')
        if (crossing is not None) != case.crossing_vehicle:
            raise ValueError('Crossing participant differs from exact case')
        if ego_id is None: ego_id = ego['actor_id']
        if ego['actor_id'] != ego_id: raise ValueError('Ego identity changed')
        if crossing is not None:
            if type(crossing.get('actor_id')) is not int: raise ValueError('Missing crossing identity')
            if crossing_id is None: crossing_id = crossing['actor_id']
            if crossing['actor_id'] != crossing_id: raise ValueError('Crossing identity changed')
        for actor in (ego, crossing):
            if actor is None: continue
            xy = actor.get('center_xy')
            speed = actor.get('speed_mps')
            if not isinstance(xy, list) or len(xy) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in xy) or type(speed) not in (int, float) or not math.isfinite(speed):
                raise ValueError('Invalid original participant motion')
        observations.append({'frame': frame, 'time_s': time_s,
                             'native_yellow_on': native_state == 'Yellow',
                             'lens_pixel_visible': light.get('lens_pixel_visible'),
                             'ego_speed_mps': ego['speed_mps'],
                             'ego_center_xy': ego['center_xy'],
                             'crossing_center_xy': crossing['center_xy'] if crossing else None})
    states = {r['native_yellow_on'] for r in observations}
    if states != {True, False}:
        raise ValueError('No Native Yellow/Off transition observed')
    channels = {
        'native_yellow_on': [r['native_yellow_on'] for r in observations],
        'ego_speed_mps': [r['ego_speed_mps'] for r in observations],
        'ego_center_xy': [r['ego_center_xy'] for r in observations],
        'crossing_center_xy': [r['crossing_center_xy'] for r in observations],
        'lens_pixel_visible': [r['lens_pixel_visible'] for r in observations],
    }
    if write_channels:
        for name, values in channels.items():
            dest = root / (name + '.jsonl')
            if dest.exists(): raise ValueError('Retain prior derived signal channel: ' + name)
            dest.write_text(''.join(json.dumps({'frame': r['frame'], 'time_s': r['time_s'], 'value': value}, allow_nan=False)+'\n'
                                    for r, value in zip(observations, values)))
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'measurements': {'flashing_yellow': {'source_hashes': hashes,
                'native_transitions': sum(a['native_yellow_on'] != b['native_yellow_on'] for a, b in zip(observations, observations[1:])),
                'ego_speed_samples_mps': channels['ego_speed_mps'],
                'crossing_present': case.crossing_vehicle,
                'lens_pixel_visibility': 'unverified',
                'legal_caution_judgment': 'unresolved'}},
            'limitations': ['Native Yellow/Off readback does not establish illuminated lens pixels, rapid legal flashing, official authority or caution.'],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root/'config.json').read_text())
    description = config.get('case', {}).get('recording_description')
    if not isinstance(description, dict) or not isinstance(description.get('channels'), list):
        raise ValueError('Selected recording description missing')
    evidence = []
    for item in description['channels']:
        name = item['name']
        path, digest = _source(root, name+'.jsonl')
        evidence.append({'name': name, 'unit': item['unit'], 'reference': path.name,
                         'sha256': digest})
    measured = report['measurements']['flashing_yellow']
    return {'case_id': report['case_id'],
            'measured_values': {'flashing_yellow': measured},
            'target_checks': [{'target': 'original Native Yellow/Off transition',
                'requested': 'retained intermittent yellow readback',
                'measured': measured['native_transitions'],
                'method': 'count transitions in frame-joined Native light readbacks',
                'tolerance': None, 'matched': measured['native_transitions'] > 0,
                'physical_cause_confirmed': False,
                'cause_evidence': 'Native state only; original lens pixels and official authority require independent review'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved signal measurement complete; physical outcome unverified',
            'physical_failure_flags': {'pixel_visibility_unverified': True,
                                       'legal_caution_unresolved': True},
            'trace_reference': 'trace.jsonl',
            'video_references': ['overview.mkv', 'approach.mkv',
                                 'reference_corner.mkv', 'driver_reference.mkv'],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description, 'recording_evidence': evidence,
            'realized_observables': {'native_yellow_on': {
                'value': measured['native_transitions'], 'unit': 'transitions',
                'method': 'count transitions in original 20 Hz Native readback',
                'time_window': 'all original frames', 'statistic': 'transition_count',
                'reference': 'native_yellow_on.jsonl'}},
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists(): raise ValueError('Retain prior signal analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__': main()
