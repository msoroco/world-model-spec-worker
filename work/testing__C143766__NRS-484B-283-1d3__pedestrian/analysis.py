"""Finalize saved original crossing sources; never classify legal compliance."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from crossing_measurement import measure

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def analyze(attempt: Path, output: Path) -> dict:
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    config = json.loads(required(attempt, 'config.json').read_text())
    case_id = config['selected_case_id']
    source = required(attempt, 'original-crossing-observations.json')
    receipt = json.loads(required(attempt, 'original-crossing-receipt.json').read_text())
    packet = json.loads(source.read_text())
    if (packet.get('case_id') != case_id or receipt.get('case_id') != case_id or
            receipt.get('source_sha256') != sha(source) or receipt.get('fps') != 20):
        raise ValueError('original crossing source receipt identity or hash differs')
    measured = measure(source)
    spec = json.loads(required(attempt, 'case-spec.json').read_text())
    if (measured['entry_phase'] != spec['entry_phase'] or
            measured['arrival_phase'] != spec['arrival_phase'] or
            measured['destination'] != spec['destination'] or
            measured['countdown_during_flashing'] != spec['countdown']):
        raise ValueError('original crossing observations differ from selected case')
    frame_map = rows(required(attempt, 'video_frames.jsonl'))
    trace = rows(required(attempt, 'trace.jsonl'))
    frames = packet['frames']
    if (receipt.get('frame_count') != len(frames) or
            len(frame_map) != len(frames) or len(trace) != len(frames)):
        raise ValueError('original crossing frame stream lengths differ')
    if packet.get('diagnostic_fixture') is False and packet.get('original_trace_id') != 'Native:' + sha(attempt / 'trace.jsonl'):
        raise ValueError('original crossing trace source differs')
    for index, (frame, mapped, native) in enumerate(zip(frames, frame_map, trace)):
        if (mapped.get('video_frame') != index or mapped.get('carla_frame') != frame['frame'] or
                mapped.get('native_frame') != frame['frame'] or native.get('frame') != frame['frame'] or
                abs(mapped.get('time_s', -1) - frame['time_s']) > 1e-4 or
                abs(native.get('time_s', -1) - frame['time_s']) > 1e-4):
            raise ValueError('original crossing frame/time join differs')
    for camera in CAMERAS:
        required(attempt, camera + '.mkv')
    description = config['case']['recording_description']
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    functions = {
        'signal_phase': lambda f: {'phase': f['signal_phase'], 'countdown': f['countdown_visible']},
        'pedestrian_route': lambda f: {'in_highway': f['in_highway'], 'at_destination': f['at_destination'], 'position_m': f['position_m']},
        'safety_destination': lambda f: {'destination': measured['destination'], 'source_sha256': packet['destination_source_sha256']},
        'exception_context': lambda f: f['exception_context'],
    }
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in functions:
            raise ValueError('unimplemented crossing channel: ' + name)
        reference = 'channels/' + name + '.jsonl'
        with (attempt / reference).open('x') as stream:
            for frame in frames:
                stream.write(json.dumps({'time_s': frame['time_s'], 'value': functions[name](frame)}, separators=(',', ':')) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': reference})
    context = 'channels/reviewed_crossing_site.json'
    (attempt / context).write_text(json.dumps({'site_source_sha256': packet['site_source_sha256'],
        'signal_source_sha256': packet['signal_source_sha256'],
        'destination_source_sha256': packet['destination_source_sha256'],
        'legal_review': 'pending'}) + '\n')
    evidence.append({'name': 'reviewed_crossing_site', 'unit': 'source', 'reference': context})
    native = {'case_id': case_id, 'measured_values': {'crossing_timing': measured},
        'target_checks': [{'target': 'original signal and pedestrian route timing',
            'requested': True, 'measured': True, 'method': 'measure_original_crossing',
            'tolerance': 0, 'matched': True, 'physical_cause_confirmed': False,
            'cause_evidence': ['original-crossing-observations.json']}],
        'setup_confirmed': False, 'behavior_attempted': False, 'maneuver_completed': False,
        'termination_reason': 'Saved original source measurement; physical/legal review pending',
        'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
        'video_references': [camera + '.mkv' for camera in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': description, 'recording_evidence': evidence,
        'realized_observables': {}}
    (attempt / 'result.json').write_text(json.dumps(native, indent=2, allow_nan=False) + '\n')
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
        'measurements': {'crossing_timing': {'method': 'measure_original_crossing',
            'sources': {'original-crossing-observations.json': sha(source),
                'original-crossing-receipt.json': sha(attempt / 'original-crossing-receipt.json')},
            'value': measured}},
        'limitations': ['Physical destination quality, actual camera pixels, prior lawful entry and statutory exceptions remain independent review.']}
    output.mkdir(parents=True, exist_ok=True)
    (output / 'analysis.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.attempt, args.output), sort_keys=True))


if __name__ == '__main__':
    main()
