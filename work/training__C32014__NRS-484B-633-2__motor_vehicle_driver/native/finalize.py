"""Saved-only bridge source finalization; physical and Department review remain open."""
import argparse
import hashlib
import json
from pathlib import Path

from measure import measure

SOURCES = ('bridge-speed-history.jsonl', 'bridge-context.json',
           'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl', 'road.xodr')
VIDEOS = ('bridge_overview.mkv', 'near_posting.mkv',
          'far_posting.mkv', 'subject_chase.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior saved result; use a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'config.json', 'construction.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case = config.get('selected_case_id')
    if case != construction.get('case_id') or case not in config.get('supported_case_ids', []):
        raise ValueError('Saved bridge finalizer exact-case identity differs')
    observed = measure(attempt / SOURCES[0], attempt / SOURCES[1])
    frame_map = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in (attempt / 'trace.jsonl').read_text().splitlines()]
    history = [json.loads(line) for line in (attempt / SOURCES[0]).read_text().splitlines()]
    if len(frame_map) != 600 or len(trace) != 600 or len(history) != 600:
        raise ValueError('Requires full original bridge trace/frame/history join')
    for index, (frame, row, motion) in enumerate(zip(frame_map, trace, history)):
        if (frame.get('video_frame') != index or
                row.get('frame') != frame.get('carla_frame') or
                motion.get('native_frame') != frame.get('native_frame') or
                abs(frame['time_s'] - row['time_s']) > 1e-6 or
                abs(frame['time_s'] - motion['time_s']) > 1e-6):
            raise ValueError('Original bridge trace and camera frame join differs')
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    evidence = []
    bridge_context = json.loads((attempt / 'bridge-context.json').read_text())
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        target = channels / (name + '.jsonl')
        with target.open('x') as stream:
            for row in history:
                value = ({'position_xyz_m': row['position_xyz_m'],
                          'velocity_xyz_mps': row['velocity_xyz_mps'],
                          'subject_id': row['subject_id']}
                         if name == 'original_velocity_position' else
                         bridge_context)
                stream.write(json.dumps({'time_s': row['time_s'], 'value': value}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + target.name})
    source_hashes = {name: sha(attempt / name) for name in SOURCES}
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {'bridge_speed_observation': {
                  'method': 'measure', 'value': observed, 'sources': source_hashes}},
              'source_complete': True, 'diagnostic_fixture': bool(config.get('diagnostic_fixture')),
              'physical_or_legal_acceptance': False}
    measured = observed['maximum_on_structure_mph']
    requested = config['requested_speed_mps'] * 2.2369362921
    result = {'case_id': case, 'measured_values': observed,
              'target_checks': [{'target': 'original on-deck speed near requested diagnostic target',
                                 'requested': requested, 'measured': measured,
                                 'method': 'measure', 'tolerance': 0,
                                 'matched': False, 'physical_cause_confirmed': False,
                                 'cause_evidence': list(SOURCES)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved original source processed; physical bridge and posting review pending',
              'physical_failure_flags': ['Department declaration, structure and sign pixels unverified'],
              'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic' if config.get('diagnostic_fixture') else 'original_source_review',
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
