"""Finalize original nearest-rail parking evidence without a legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rail_proximity import measure

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


def measure_nearest_rail(source: Path) -> dict:
    return measure(source)


def analyze(attempt: Path, output: Path) -> dict:
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    config = json.loads(required(attempt, 'config.json').read_text())
    case_id = config['selected_case_id']
    source = required(attempt, 'original-rail-observations.json')
    receipt = json.loads(required(attempt, 'original-rail-receipt.json').read_text())
    packet = json.loads(source.read_text())
    if (receipt.get('case_id') != case_id or receipt.get('source_sha256') != sha(source)
            or receipt.get('fps') != 20 or packet.get('case_id') != case_id):
        raise ValueError('original rail source receipt identity or hash differs')
    measurement = measure_nearest_rail(source)
    frames = packet['frames']
    if receipt.get('frame_count') != len(frames):
        raise ValueError('original rail receipt frame count differs')
    mapping = rows(required(attempt, 'video_frames.jsonl'))
    trace = rows(required(attempt, 'trace.jsonl'))
    if packet.get('diagnostic_fixture') is False and packet.get('original_trace_id') != 'Native:' + sha(attempt / 'trace.jsonl'):
        raise ValueError('original rail packet trace source differs')
    if len(frames) != len(mapping) or len(frames) != len(trace):
        raise ValueError('original rail frame streams differ')
    for index, (frame, mapped, row) in enumerate(zip(frames, mapping, trace)):
        if (mapped.get('video_frame') != index or frame.get('frame') != mapped.get('carla_frame')
                or frame['frame'] != mapped.get('native_frame') or row.get('frame') != frame['frame']
                or abs(frame['time_s'] - mapped.get('time_s', -1)) > 1e-4
                or abs(frame['time_s'] - row.get('time_s', -1)) > 1e-4):
            raise ValueError('original rail frame/time join differs')
    for camera in CAMERAS:
        required(attempt, camera + '.mkv')
    description = config['case']['recording_description']
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    values = {
        'railroad_site': lambda frame: {'site': packet['site'], 'rail_polylines_m': packet['rail_polylines_m']},
        'vehicle_rail_distance': lambda frame: {'vehicle_footprint_m': frame['vehicle_footprint_m'], 'nearest_rail_distance_m': measurement['nearest_rail_distance_m']},
        'vehicle_parking_action': lambda frame: {'vehicle_action': frame['vehicle_action'], 'ego_xyz_m': frame['ego_xyz_m'], 'ego_speed_mps': frame['ego_speed_mps']},
        'traffic_and_exceptions': lambda frame: {'other_vehicle_actor_id': frame['other_vehicle_actor_id'], 'other_vehicle_xyz_m': frame['other_vehicle_xyz_m'], 'other_vehicle_speed_mps': frame['other_vehicle_speed_mps'], 'exception_context': packet['exception_context']}}
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in values:
            raise ValueError('unimplemented railroad channel: ' + name)
        ref = 'channels/' + name + '.jsonl'
        with (attempt / ref).open('x') as stream:
            for frame in frames:
                stream.write(json.dumps({'time_s': frame['time_s'], 'value': values[name](frame)}, separators=(',', ':')) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': ref})
    context = 'channels/reviewed_railroad_site.json'
    (attempt / context).write_text(json.dumps({'reviewed_railroad_site': {
        'site_source_sha256': packet['site_source_sha256'], 'site': packet['site']}}) + '\n')
    evidence.append({'name': 'reviewed_railroad_site', 'unit': 'source', 'reference': context})
    native = {'case_id': case_id, 'measured_values': {'nearest_rail': measurement},
        'target_checks': [{'target': 'source-bound original nearest rail distance', 'requested': config['case']['requested_nearest_vehicle_to_rail_m'],
            'measured': measurement['nearest_rail_distance_m'], 'method': 'measure_nearest_rail',
            'tolerance': .25, 'matched': abs(measurement['nearest_rail_distance_m'] - config['case']['requested_nearest_vehicle_to_rail_m']) <= .25,
            'physical_cause_confirmed': False, 'cause_evidence': ['original-rail-observations.json']}],
        'setup_confirmed': False, 'behavior_attempted': False, 'maneuver_completed': False,
        'termination_reason': 'Saved source measurement; physical and legal review pending',
        'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
        'video_references': [camera + '.mkv' for camera in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl', 'recording_description': description,
        'recording_evidence': evidence, 'realized_observables': {}}
    (attempt / 'result.json').write_text(json.dumps(native, indent=2, allow_nan=False) + '\n')
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
        'measurements': {'nearest_rail': {'method': 'measure_nearest_rail',
            'sources': {'original-rail-observations.json': sha(source),
                        'original-rail-receipt.json': sha(attempt / 'original-rail-receipt.json')},
            'value': measurement}},
        'limitations': ['Original railroad identity, all rails, parking action and four independent statutory exceptions require source review.']}
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
