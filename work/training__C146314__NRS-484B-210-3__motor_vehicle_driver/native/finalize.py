"""Saved-only exact right-pass measurement; no legal or physical acceptance claim."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_original import measure

SOURCES = ('native_motion.jsonl', 'video_frames.jsonl', 'trace.jsonl',
           'capture/evidence.jsonl', 'road.xodr')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')
CHANNELS = ('right_pass', 'paved_footprint', 'paved_clearance',
            'ego_pose', 'lead_pose', 'road_surface')


def measure_original_body_and_paved_corridor(motion, frame_map, road_sha):
    return measure(motion, frame_map, road_sha)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior saved result; use a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'config.json', 'construction.json',
                 'acquisition-provenance.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case = config.get('selected_case_id')
    assignment = config.get('assignment_id')
    if case != construction.get('case_id') or case not in {
            assignment + '__probe_a', assignment + '__probe_b'}:
        raise ValueError('Saved exact-case identity differs')
    provenance = json.loads((attempt / 'acquisition-provenance.json').read_text())
    diagnostic = provenance.get('diagnostic_fixture') is True
    motion, frame_map, trace = (rows(attempt / name) for name in
                                 ('native_motion.jsonl', 'video_frames.jsonl', 'trace.jsonl'))
    road_sha = sha(attempt / 'road.xodr')
    measured = measure_original_body_and_paved_corridor(motion, frame_map, road_sha)
    if measured['source_kind'] != ('synthetic_cpu_pass' if diagnostic else 'original_native_pass'):
        raise ValueError('Saved pass provenance differs')
    if len(trace) != 600 or len(rows(attempt / 'capture/evidence.jsonl')) != 600:
        raise ValueError('Full trace and capture source required')
    names = {camera['name'] for camera in config['cameras']}
    if names != {'overview', 'approach', 'reference_corner', 'driver_reference'}:
        raise ValueError('Four exact camera sources differ')
    for i, (native, frame, position) in enumerate(zip(motion, frame_map, trace)):
        if position.get('frame') != native['native_frame'] or position.get('time_s') != native['time_s']:
            raise ValueError('Saved trace frame/time join differs')
        if frame.get('camera_native_frames') != {name: native['native_frame'] for name in names}:
            raise ValueError('Four source camera frame join differs')
        if position.get('position_m') != native['ego']['center_xyz_m']:
            raise ValueError('Original ego trace position differs')
    if not measured['pass_complete']:
        raise ValueError('Source does not complete behind/right-overlap/ahead pass')
    hashes = {name: sha(attempt / name) for name in SOURCES}
    channel_dir = attempt / 'channels'
    channel_dir.mkdir(exist_ok=False)
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        if name not in CHANNELS:
            raise ValueError('Unknown right-pass recording channel')
        path = channel_dir / (name + '.jsonl')
        with path.open('x') as stream:
            for native in motion:
                value = {'ego': native['ego'], 'lead': native['lead'],
                         'paved_right_edge_y_m': native['paved_right_edge_y_m'],
                         'measurement': measured}
                stream.write(json.dumps({'time_s': native['time_s'], 'value': value}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + path.name})
    camera_path = channel_dir / 'four_source_cameras.json'
    camera_path.write_text(json.dumps({'four_source_cameras':
        {name: sha(attempt / (name + '.mkv')) for name in names}}) + '\n')
    evidence.append({'name': 'four_source_cameras', 'unit': 'video',
                     'reference': 'channels/' + camera_path.name})
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {'right_pass_paved_surface': {
                  'method': 'measure_original_body_and_paved_corridor',
                  'value': measured, 'sources': hashes}},
              'source_complete': True, 'diagnostic_fixture': diagnostic,
              'physical_or_legal_acceptance': False}
    result = {'case_id': case, 'measured_values': measured,
              'target_checks': [{'target': 'source-joined right pass and paved clearance captured',
                                 'requested': True, 'measured': measured['pass_complete'],
                                 'method': 'measure_original_body_and_paved_corridor',
                                 'tolerance': 0, 'matched': measured['pass_complete'],
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(SOURCES)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved source pass measured; physical and legal review pending',
              'physical_failure_flags': ['Original shoulder material, dimensions and necessity unreviewed'],
              'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic' if diagnostic else 'original_source_review',
              'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
