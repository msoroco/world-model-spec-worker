"""Saved-only source-joined sidewalk/roadway measurement, without legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from measure import measure

SOURCES = ('pedestrian-poses.jsonl', 'surface-geometry.json', 'trace.jsonl',
           'video_frames.jsonl', 'capture/evidence.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def surface_measurement(attempt):
    attempt = Path(attempt)
    return measure(attempt / 'pedestrian-poses.jsonl',
                   attempt / 'surface-geometry.json')


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
    if (case != construction['case_id'] or case != config['case_id'] or
            case not in {config['assignment_id'] + '__probe_01',
                         config['assignment_id'] + '__probe_02'}):
        raise ValueError('Saved walking-surface case identity differs')
    expected_surface = 'sidewalk' if case.endswith('probe_01') else 'roadway'
    if config.get('walking_surface') != expected_surface:
        raise ValueError('Saved walking surface differs from exact case')
    poses = [json.loads(line) for line in (attempt / SOURCES[0]).read_text().splitlines()]
    trace = [json.loads(line) for line in (attempt / SOURCES[2]).read_text().splitlines()]
    mapping = [json.loads(line) for line in (attempt / SOURCES[3]).read_text().splitlines()]
    evidence = [json.loads(line) for line in (attempt / SOURCES[4]).read_text().splitlines()]
    if not all(len(part) == 600 for part in (poses, trace, mapping, evidence)):
        raise ValueError('Full 600-frame original source join required')
    for index, (pose, state, mapped, capture) in enumerate(zip(poses, trace, mapping, evidence)):
        native_frame = pose['native_frame']
        if (pose['video_frame'] != index or mapped['video_frame'] != index or
                mapped['carla_frame'] != native_frame or state['frame'] != native_frame or
                capture['original_frame'] != native_frame or
                capture['actor_id'] != pose['walker_actor_id'] or
                abs(pose['time_s'] - mapped['time_s']) > 1e-4 or
                abs(state['time_s'] - mapped['time_s']) > 1e-4 or
                abs(capture['recording_time_s'] - mapped['time_s']) > 1e-4):
            raise ValueError('Original pedestrian/frame/capture join differs')
    measured = surface_measurement(attempt)
    context = json.loads((attempt / SOURCES[1]).read_text())
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    recording_evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        target = channels / (name + '.jsonl')
        with target.open('x') as stream:
            for pose, state in zip(poses, trace):
                value = (pose['walker_actor_id'] if name == 'ru.subject' else
                         context if name in ('st.sidewalk', 'st.roadway') else
                         pose['pedestrian_footprint_xy_m'] if name == 'rel.occupies' else
                         state['heading_deg'] if name == 'kin.heading' else
                         measured['path_length_m'])
                stream.write(json.dumps({'time_s': pose['time_s'], 'value': value}) + '\n')
        recording_evidence.append({'name': name, 'unit': channel['unit'],
                                   'reference': 'channels/' + target.name})
    source_hashes = {name: sha(attempt / name) for name in SOURCES[:2]}
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {'surface_measurement': {
                  'method': 'surface_measurement', 'value': measured,
                  'sources': source_hashes}},
              'source_complete': True, 'physical_or_legal_acceptance': False}
    measured_frames = measured[expected_surface + '_occupied_frames']
    result = {'case_id': case, 'measured_values': measured,
              'target_checks': [{'target': 'original pedestrian footprint on requested walking surface',
                  'requested': expected_surface, 'measured': measured_frames,
                  'method': 'surface_measurement', 'tolerance': 0,
                  'matched': measured_frames > 0, 'physical_cause_confirmed': False,
                  'cause_evidence': source_hashes}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved walking-surface sources measured; physical and legal review pending',
              'physical_failure_flags': ['Physical sidewalk provision and camera pixels unverified'],
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
    args = parser.parse_args()
    finalize(args.attempt, args.output)
