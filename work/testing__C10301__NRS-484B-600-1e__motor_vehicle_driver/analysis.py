"""Selected C10301 measurements from original sealed Native sources.

The sampled speed relation and source-bound operation context are observations,
not a legal finding or a claim about peaks between 20 Hz samples.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from delivery_audit import audit_decoded_media
from speed_boundary import measure


def _source(attempt: Path, name: str) -> tuple[dict, str]:
    path = Path(attempt) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def measure_operation(attempt: Path, case_id: str) -> dict:
    setup, _ = _source(attempt, 'authored-setup.json')
    site, site_sha = _source(attempt, 'native-site-source.json')
    motion, _ = _source(attempt, 'native-motion-receipt.json')
    if (setup.get('case_id') != case_id or site.get('case_id') != case_id or
            motion.get('case_id') != case_id or
            setup.get('actor') != 'motor_vehicle_driver' or
            site.get('actor') != setup['actor'] or
            setup.get('native_site_sha256') != site_sha or
            motion.get('sample_count') != 900):
        raise ValueError('original vehicle operation source identity differs')
    kinematic_path = Path(attempt) / 'native-kinematics.jsonl'
    if not kinematic_path.is_file():
        raise ValueError('Missing required source: native-kinematics.jsonl')
    raw = kinematic_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != motion.get('kinematics_source_sha256'):
        raise ValueError('original Native kinematics source hash differs')
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    descriptor, _ = _source(attempt, 'speed-source.json')
    origin = descriptor['source_frame_origin']
    if len(rows) != 900 or any(row.get('frame') != origin + i or
                               row.get('time_s') != i / 20 for i, row in enumerate(rows)):
        raise ValueError('original Native kinematics frame join differs')
    for row in rows:
        point, velocity = row.get('position_m'), row.get('velocity_mps')
        if (not isinstance(point, list) or len(point) != 3 or
                not isinstance(velocity, list) or len(velocity) != 3 or
                not all(type(value) in (int, float) and math.isfinite(value)
                        for value in point + velocity)):
            raise ValueError('original Native kinematics position or velocity invalid')
    return {'actor': setup['actor'], 'vehicle_blueprint_id': site['vehicle_blueprint_id'],
            'observed_motion_samples': motion['sample_count'],
            'original_kinematics_sha256': motion['kinematics_source_sha256'],
            'travel_m': motion['travel_m'],
            'territorial_applicability': 'unresolved'}


def measure_rate(attempt: Path, case_id: str) -> dict:
    observed = measure(attempt, case_id)
    return {'peak_sample_mph': observed['peak_sample_mph'],
            'sampled_relation': observed['sampled_relation'],
            'peak_uncertainty_mph': observed['peak_uncertainty_mph'],
            'between_sample_peaks': observed['between_sample_peaks'],
            'sample_count': observed['sample_count']}


def project_trace(attempt: Path, case_id: str) -> list[dict]:
    """Join captured position vectors to the sealed speed and camera clock."""
    attempt = Path(attempt)
    measure_operation(attempt, case_id)
    measure_rate(attempt, case_id)
    descriptor, _ = _source(attempt, 'speed-source.json')
    frame_map, _ = _source(attempt, 'frame-map.json')
    speed_rows = [json.loads(line) for line in
                  (attempt / 'original-speed.jsonl').read_text().splitlines()]
    kinematic_rows = [json.loads(line) for line in
                      (attempt / 'native-kinematics.jsonl').read_text().splitlines()]
    camera_rows = frame_map.get('frames')
    if (frame_map.get('case_id') != case_id or
            not isinstance(camera_rows, list) or
            not (len(camera_rows) == len(speed_rows) ==
                 len(kinematic_rows) == 900)):
        raise ValueError('original Native trace frame count differs')
    projected = []
    for index, (speed, motion, camera) in enumerate(zip(speed_rows,
                                                       kinematic_rows,
                                                       camera_rows)):
        frame = descriptor['source_frame_origin'] + index
        time_s = index / 20
        if (speed['frame'] != frame or motion['frame'] != frame or
                camera.get('frame') != frame or
                speed['time_s'] != time_s or motion['time_s'] != time_s):
            raise ValueError('original Native speed, motion and camera frame join differs')
        velocity = motion['velocity_mps']
        if abs(math.sqrt(sum(value * value for value in velocity)) -
               speed['speed_mps']) > 1e-6:
            raise ValueError('original Native velocity and speed differ')
        projected.append({'frame': frame, 'time_s': time_s,
                          'position_m': motion['position_m'],
                          'position': dict(zip(('x', 'y', 'z'), motion['position_m'])),
                          'velocity_mps': velocity, 'speed_mps': speed['speed_mps'],
                          'speed_mph': speed['speed_mps'] * 2.2369362920544,
                          'heading_deg': math.degrees(math.atan2(velocity[1], velocity[0]))
                          if velocity[0] or velocity[1] else 0.0,
                          'control': motion['control'],
                          'camera_frames': camera['camera_frames']})
    return projected


def finalize(attempt: Path, case_id: str, *, allow_diagnostic: bool = False) -> dict:
    attempt = Path(attempt)
    media = audit_decoded_media(attempt, case_id,
                                allow_diagnostic=allow_diagnostic)
    requirements = (
        ('vehicle_operation', measure_operation,
         ('authored-setup.json', 'native-site-source.json',
          'native-motion-receipt.json', 'native-kinematics.jsonl')),
        ('sampled_rate_boundary', measure_rate,
         ('original-speed.jsonl', 'speed-source.json')),
    )
    measurements = {}
    for key, method, sources in requirements:
        value = method(attempt, case_id)
        hashes = {}
        for name in sources:
            path = attempt / name
            if not path.is_file():
                raise ValueError('Missing required source: ' + name)
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        measurements[key] = {'method': method.__name__, 'value': value,
                             'sources': hashes}
    return {'case_id': case_id, 'measurements': measurements,
            'full_video_decode': media['full_video_decode'],
            'physical_acceptance_claimed': False,
            'legal_judgment': 'unresolved'}


def write_native_result(attempt: Path, report: dict) -> dict:
    """Publish derived Native traces and channels from sealed original rows."""
    attempt = Path(attempt)
    if any((attempt / name).exists() for name in
           ('result.json', 'trace.jsonl', 'video_frames.jsonl', 'channels')):
        raise ValueError('refusing to overwrite derived Native result')
    construction, _ = _source(attempt, 'construction.json')
    setup, setup_sha = _source(attempt, 'authored-setup.json')
    capture_index, _ = _source(attempt, 'capture-index.json')
    case_id = report['case_id']
    if (construction.get('case_id') != case_id or
            setup.get('case_id') != case_id or capture_index.get('case_id') != case_id):
        raise ValueError('derived Native case identity differs')
    trace = project_trace(attempt, case_id)
    description = construction['recording_description']
    channels = description['channels']
    names = [channel['name'] for channel in channels]
    expected = ['sampled_speed_mps', 'ego_position_m',
                'route_readback', 'camera_frame_sources']
    if names != expected:
        raise ValueError('Native recording description differs')
    route, _ = _source(attempt, 'route-frame-readback.json')
    route_rows = route.get('frames')
    if not isinstance(route_rows, list) or len(route_rows) != len(trace):
        raise ValueError('original route readback frame count differs')
    values = {name: [] for name in names}
    mapping = []
    for index, (point, route_row) in enumerate(zip(trace, route_rows)):
        if route_row.get('frame') != point['frame']:
            raise ValueError('original route/trace frame join differs')
        time_s = point['time_s']
        mapping.append({'video_frame': index, 'carla_frame': point['frame'],
                        'native_frame': point['frame'], 'time_s': time_s,
                        'camera_frames': point['camera_frames']})
        for name, value in zip(names, (point['speed_mps'], point['position_m'],
                                       route_row, point['camera_frames'])):
            values[name].append({'time_s': time_s, 'value': value})
    def write_rows(path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as stream:
            for row in rows:
                stream.write(json.dumps(row, allow_nan=False) + '\n')
    write_rows(attempt / 'trace.jsonl', trace)
    write_rows(attempt / 'video_frames.jsonl', mapping)
    evidence = []
    for channel in channels:
        name = channel['name']
        relative = 'channels/' + name + '.jsonl'
        write_rows(attempt / relative, values[name])
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': relative})
    requested = setup['requested_speed_mph']
    measured = report['measurements']['sampled_rate_boundary']['value']['peak_sample_mph']
    tolerance = 1.0
    check = {'target': 'authored sampled speed probe', 'requested': requested,
             'measured': measured, 'method': 'sealed 20 Hz original actor velocity',
             'tolerance': tolerance, 'matched': abs(requested - measured) <= tolerance,
             'physical_cause_confirmed': False,
             'cause_evidence': {'authored-setup.json': setup_sha,
                                'original-speed.jsonl': report['measurements']['sampled_rate_boundary']['sources']['original-speed.jsonl']}}
    result = {'case_id': case_id, 'measured_values': report['measurements'],
              'target_checks': [check], 'setup_confirmed': False,
              'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'Saved original source projection; physical completion unverified',
              'physical_failure_flags': {'physical_completion_unverified': True},
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in
                                   ('overview', 'approach', 'reference_corner',
                                    'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description,
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': 'synthetic_fixture' if capture_index['diagnostic_fixture'] else 'native',
              'diagnostic_fixture': capture_index['diagnostic_fixture'],
              'physical_acceptance_claimed': False}
    (attempt / 'result.json').write_text(json.dumps(result, indent=2,
                                                  allow_nan=False) + '\n')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-diagnostic', action='store_true')
    args = parser.parse_args()
    config, _ = _source(args.attempt, 'config.json')
    index, _ = _source(args.attempt, 'capture-index.json')
    report = finalize(args.attempt, config['selected_case_id'],
                      allow_diagnostic=args.allow_diagnostic or index.get('diagnostic_fixture') is True)
    write_native_result(args.attempt, report)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
