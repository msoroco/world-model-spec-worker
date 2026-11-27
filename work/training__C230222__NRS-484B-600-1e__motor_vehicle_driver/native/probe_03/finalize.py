"""Saved-only source validation and Native result for the absolute-speed sweep."""
import argparse
import hashlib
import json
from pathlib import Path

from speed_measure import measure

SOURCES = ('native_motion.jsonl', 'road_context.json', 'video_frames.jsonl',
           'trace.jsonl', 'capture/evidence.jsonl', 'road.xodr')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_speed(attempt):
    return measure(attempt)


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior saved result; use a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'config.json', 'construction.json'):
        if not (attempt/name).is_file():
            raise ValueError('Missing required source: '+name)
    config = json.loads((attempt/'config.json').read_text())
    construction = json.loads((attempt/'construction.json').read_text())
    case = config.get('selected_case_id')
    if case != construction.get('case_id') or case not in {config['assignment_id']+'__probe_'+suffix for suffix in ('01', '02', '03')}:
        raise ValueError('Saved finalizer exact-case identity differs')
    observed = measure_speed(attempt)
    frames = [json.loads(line) for line in (attempt/'video_frames.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in (attempt/'trace.jsonl').read_text().splitlines()]
    if len(frames) != 600 or len(trace) != 600:
        raise ValueError('Requires full original trace/frame join')
    for index, (frame, row) in enumerate(zip(frames, trace)):
        if (frame['video_frame'] != index or row['frame'] != frame['carla_frame'] or
                abs(frame['time_s']-row['time_s']) > 1e-6):
            raise ValueError('Trace and original camera frame join differs')
    channels = attempt/'channels'
    channels.mkdir(exist_ok=False)
    evidence = []
    motion = [json.loads(line) for line in (attempt/'native_motion.jsonl').read_text().splitlines()]
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels/(name+'.jsonl')
        with path.open('x') as stream:
            for row in motion:
                value = ([row['velocity_x_mps'], row['velocity_y_mps'], row['velocity_z_mps']]
                         if name == 'kin.velocity' else
                         (row['velocity_x_mps']**2+row['velocity_y_mps']**2+row['velocity_z_mps']**2)**.5/.44704
                         if name == 'kin.speed' else row['ego_actor_id'])
                stream.write(json.dumps({'time_s': row['time_s'], 'value': value})+'\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': 'channels/'+path.name})
    values = {'speed_observation': {'method': 'measure_speed', 'value': observed,
                                     'sources': {name: sha(attempt/name) for name in SOURCES}},
              'unconditional_speed_context': {'method': 'measure_speed',
                                               'value': {'posted_limit_required': False,
                                                         'subject_source': observed['sources']['road_context.json']},
                                               'sources': {name: sha(attempt/name) for name in SOURCES}}}
    values['subject_context'] = {'method': 'measure_speed', 'value': {'subject_source': observed['sources']['road_context.json'], 'vehicle_identity_requires_review': True}, 'sources': {name: sha(attempt/name) for name in SOURCES}}
    values['speed_boundary_context'] = {'method': 'measure_speed', 'value': observed, 'sources': {name: sha(attempt/name) for name in SOURCES}}
    diagnostic = observed['review_kind'] == 'synthetic_diagnostic'
    report = {'format': 'worker-analysis-report', 'case_id': case, 'measurements': values,
              'source_complete': True, 'diagnostic_fixture': diagnostic,
              'physical_or_legal_acceptance': False}
    target = float(config['requested_speed_mph'])
    actual = observed['maximum_observed_mph_while_driving']
    matched = abs(actual-target) <= 1e-9 if diagnostic else False
    result = {'case_id': case, 'measured_values': observed,
              'target_checks': [{'target': 'observed speed near requested diagnostic target',
                                 'requested': target, 'measured': actual, 'method': 'measure_speed',
                                 'tolerance': 1e-9 if diagnostic else 0,
                                 'matched': matched, 'physical_cause_confirmed': False,
                                 'cause_evidence': list(SOURCES)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved source processed; physical completion requires original Native audit',
              'physical_failure_flags': ['Physical speed, camera pixels and route completion unverified'],
              'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic' if diagnostic else 'original_source_review',
              'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
