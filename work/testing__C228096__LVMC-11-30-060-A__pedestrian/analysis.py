"""Finalize saved crossing entry observations without deciding statutory exceptions."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from outside_crossoutside_entry import measure

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def measure_outside_entry(source: Path) -> dict:
    return measure(source)


def analyze(attempt: Path, output: Path) -> dict:
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    config = json.loads(required(attempt, 'config.json').read_text())
    case_id = config['selected_case_id']
    source = required(attempt, 'original-crossing-observations.json')
    receipt = json.loads(required(attempt, 'original-crossing-receipt.json').read_text())
    packet = json.loads(source.read_text())
    if (receipt.get('case_id') != case_id or receipt.get('source_sha256') != sha(source)
            or receipt.get('fps') != 20 or packet.get('case_id') != case_id):
        raise ValueError('original crossing source receipt identity or hash differs')
    measurement = measure_outside_entry(source)
    frames = packet['frames']
    if receipt.get('frame_count') != len(frames):
        raise ValueError('original crossing receipt frame count differs')
    frame_map = rows(required(attempt, 'video_frames.jsonl'))
    trace = rows(required(attempt, 'trace.jsonl'))
    if packet.get('diagnostic_fixture') is False and packet.get('original_trace_id') != (
            'Native:' + sha(attempt / 'trace.jsonl')):
        raise ValueError('original crossing packet trace source differs')
    if len(frames) != len(frame_map) or len(frames) != len(trace):
        raise ValueError('original crossing frame streams differ')
    for index, (frame, mapped, row) in enumerate(zip(frames, frame_map, trace)):
        if (mapped.get('video_frame') != index or frame.get('frame') != mapped.get('carla_frame')
                or frame['frame'] != mapped.get('native_frame') or row.get('frame') != frame['frame']
                or abs(frame['time_s'] - mapped.get('time_s', -1)) > 1e-4
                or abs(frame['time_s'] - row.get('time_s', -1)) > 1e-4):
            raise ValueError('original crossing frame/time join differs')
    for camera in CAMERAS:
        required(attempt, camera + '.mkv')
    description = config['case']['recording_description']
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    value = {
        'crossing_signal_state': lambda frame: {'signal_indication': frame['signal_indication'],
            'pedestrian_signal_id': packet['pedestrian_signal_id']},
        'pedestrian_crosscrossing_motion': lambda frame: {
            'pedestrian_in_crosscrossing': frame['pedestrian_in_crosscrossing'],
            'pedestrian_facing_signal': frame['pedestrian_facing_signal'],
            'crossing_direction_matches_signal': frame['crossing_direction_matches_signal']},
        'driver_yield_trajectory': lambda frame: {
            'driver_actor_ids': frame['driver_actor_ids'],
            'driver_yield_observed': frame['driver_yield_observed']},
        'exception_context': lambda frame: frame['exception_context']}
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in value:
            raise ValueError('unimplemented crossing channel: ' + name)
        ref = 'channels/' + name + '.jsonl'
        with (attempt / ref).open('x') as stream:
            for frame in frames:
                stream.write(json.dumps({'time_s': frame['time_s'],
                    'value': value[name](frame)}, separators=(',', ':')) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': ref})
    context = 'channels/reviewed_crossing_site.json'
    (attempt / context).write_text(json.dumps({'reviewed_crossing_site': {
        'site_source_sha256': packet['site_source_sha256'],
        'exception_source_sha256': packet['exception_source_sha256'],
        'statutory_exceptions': 'independent review pending'}}) + '\n')
    evidence.append({'name': 'reviewed_crossing_site', 'unit': 'source', 'reference': context})
    native = {'case_id': case_id, 'measured_values': {'outside_entry': measurement},
        'target_checks': [{'target': 'source-bound original crossing crosscrossing entry',
            'requested': True, 'measured': True, 'method': 'measure_outside_entry',
            'tolerance': 0, 'matched': True, 'physical_cause_confirmed': False,
            'cause_evidence': ['original-crossing-observations.json']}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Saved source measurement; physical and legal review pending',
        'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
        'video_references': [camera + '.mkv' for camera in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': description, 'recording_evidence': evidence,
        'realized_observables': {}}
    (attempt / 'result.json').write_text(json.dumps(native, indent=2, allow_nan=False) + '\n')
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
        'measurements': {'outside_entry': {'method': 'measure_outside_entry',
            'sources': {'original-crossing-observations.json': sha(source),
                'original-crossing-receipt.json': sha(attempt / 'original-crossing-receipt.json')},
            'value': measurement}},
        'limitations': ['Actual signal pixels, physical crossing, driver duty and statutory exceptions require original review.']}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    analyze(args.attempt, args.output)


if __name__ == '__main__':
    main()
