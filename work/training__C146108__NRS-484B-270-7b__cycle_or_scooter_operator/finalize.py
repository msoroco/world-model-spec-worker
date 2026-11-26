"""Saved-only full-pass finalizer; preserves original sources and legal uncertainty."""
import argparse
import hashlib
import json
from pathlib import Path

from pass_measure import measure

SOURCES = ('participant-poses.jsonl', 'pass-context.json', 'trace.jsonl',
           'video_frames.jsonl', 'capture/evidence.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv', 'raw.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def full_pass(attempt):
    return measure(attempt)


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior saved result; use a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'config.json', 'construction.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case = config['selected_case_id']
    if (case != config['case_id'] or case != construction['case_id'] or
            case not in config['supported_case_ids']):
        raise ValueError('Saved pass case identity differs')
    context = json.loads((attempt / 'pass-context.json').read_text())
    if context.get('case_id') not in (None, case):
        raise ValueError('Passed participant context binds another case')
    if context['rider_class'] != config['rider_class']:
        raise ValueError('Rider statutory subject differs from exact construction')
    poses, trace, mapping, captures = [rows(attempt / name) for name in
                                      (SOURCES[0], SOURCES[2], SOURCES[3], SOURCES[4])]
    if not all(len(part) == 600 for part in (poses, trace, mapping, captures)):
        raise ValueError('Full 600-frame original source join required')
    for index, (pose, state, mapped, capture) in enumerate(zip(poses, trace, mapping, captures)):
        native_frame = pose['native_frame']
        if (pose['video_frame'] != index or mapped['video_frame'] != index or
                mapped['carla_frame'] != native_frame or state['frame'] != native_frame or
                capture['original_frame'] != native_frame or
                capture['actor_id'] != pose['rider_actor_id'] or
                abs(pose['time_s'] - mapped['time_s']) > 1e-4 or
                abs(state['time_s'] - mapped['time_s']) > 1e-4 or
                abs(capture['recording_time_s'] - mapped['time_s']) > 1e-4):
            raise ValueError('Original rider/frame/capture join differs')
        if set(mapped.get('camera_native_frames', {})) != {
                'overview', 'approach', 'reference_corner', 'driver_reference'}:
            raise ValueError('Four original camera identities incomplete')
        if any(value != native_frame for value in mapped['camera_native_frames'].values()):
            raise ValueError('Original camera frame join differs')
    measured = full_pass(attempt)
    if measured['first_behind_frame'] != 0 or measured['pass_clear_frame'] >= 600:
        raise ValueError('Full pass interval incomplete')
    source_hashes = {name: sha(attempt / name) for name in SOURCES}
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    recording_evidence = []
    values = {
        'drv.overtaking': {'first_behind': measured['first_behind_frame'],
                           'alongside': measured['pass_start_frame'],
                           'clear_ahead': measured['pass_clear_frame']},
        'ru.motor_vehicle': {'class': context['passed_class'],
                             'actor_id': poses[0]['motor_actor_id']},
        'rel.surface_gap': measured['minimum_surface_gap_m'],
        'drv.time_to_conflict': measured['initial_time_to_rear_overlap_s'],
        'drv.passing_side': measured['passing_side'],
        'kin.speed': measured['initial_longitudinal_closing_speed_mps'],
        'ru.occupant_count': measured['motor_occupant_count_sourced']}
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        if name not in (*values, 'rider_pose', 'motor_pose'):
            raise ValueError('Unknown selected observation channel: ' + name)
        target = channels / (name + '.jsonl')
        with target.open('x') as stream:
            for pose in poses:
                value = (pose['rider_xy_m'] if name == 'rider_pose' else
                         pose['motor_xy_m'] if name == 'motor_pose' else values[name])
                stream.write(json.dumps({'time_s': pose['time_s'], 'value': value}) + '\n')
        recording_evidence.append({'name': name, 'unit': channel['unit'],
                                   'reference': 'channels/' + target.name})
    for channel in construction['recording_description'].get('context_inputs', []):
        if channel['name'] != 'motor_occupants':
            raise ValueError('Unknown saved context input')
        target = channels / 'motor_occupants.json'
        target.write_text(json.dumps({'motor_occupants': context['motor_occupant_count']}) + '\n')
        recording_evidence.append({'name': channel['name'], 'unit': channel['unit'],
                                   'reference': 'channels/' + target.name})
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {'full_pass': {'method': 'full_pass',
                  'value': measured, 'sources': source_hashes}},
              'source_complete': True, 'physical_or_legal_acceptance': False}
    result = {'case_id': case, 'measured_values': measured,
              'target_checks': [{'target': 'full behind-to-clear-ahead pass',
                  'requested': True, 'measured': True,
                  'method': 'pass_measure', 'tolerance': 'exact event order',
                  'matched': True, 'physical_cause_confirmed': False,
                  'cause_evidence': source_hashes}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved pass measured; physical and legal review pending',
              'physical_failure_flags': ['Native motor, pedals, occupants and camera visibility unverified'],
              'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': recording_evidence, 'realized_observables': {},
              'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    arguments = parser.parse_args()
    finalize(arguments.attempt, arguments.output)
