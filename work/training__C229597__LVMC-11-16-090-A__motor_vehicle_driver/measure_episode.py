"""Source-derived C229597 motion measurement; no legal exhibition verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
HZ = 20
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()
            if line.strip()]


def derive(trace, mapping):
    if len(trace) != FRAMES or len(mapping) != FRAMES:
        raise ValueError('Incomplete original 600-frame interval')
    speeds = []
    accelerations = []
    previous_native = -1
    for index, (motion, frame) in enumerate(zip(trace, mapping)):
        if (frame.get('video_frame') != index
                or type(frame.get('carla_frame')) is not int
                or frame['carla_frame'] <= previous_native
                or motion.get('frame') != frame['carla_frame']
                or motion.get('video_frame') != index
                or abs(motion.get('time_s', -1) - frame.get('time_s', -2)) > 1e-6
                or abs(frame['time_s'] - index / HZ) > 1e-6):
            raise ValueError('Original source frame/timestamp join differs at ' + str(index))
        previous_native = frame['carla_frame']
        velocity = motion.get('velocity_mps')
        acceleration = motion.get('acceleration_mps2')
        position = motion.get('position_m')
        if any(not isinstance(v, list) or len(v) != 3
               or any(type(x) not in (int, float) or not math.isfinite(x) for x in v)
               for v in (velocity, acceleration, position)):
            raise ValueError('Missing finite original motion vector at ' + str(index))
        speeds.append(math.sqrt(sum(v*v for v in velocity)))
        accelerations.append(math.sqrt(sum(a*a for a in acceleration)))
    return {'frames': FRAMES, 'first_time_s': 0.0,
            'last_time_s': (FRAMES - 1) / HZ,
            'maximum_speed_mps': max(speeds),
            'maximum_acceleration_mps2': max(accelerations),
            'mean_speed_mps': sum(speeds) / FRAMES,
            'speed_increase_mps': max(speeds[160:440]) - min(speeds[:160]),
            'speed_series_mps': speeds,
            'acceleration_series_mps2': accelerations}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists() or (attempt / 'channels').exists():
        raise ValueError('Use a fresh saved attempt')
    config_path = attempt / 'config.json'
    trace_path = attempt / 'trace.jsonl'
    map_path = attempt / 'video_frames.jsonl'
    provenance_path = attempt / 'acquisition-provenance.json'
    for path in (config_path, trace_path, map_path, provenance_path):
        if not path.is_file():
            raise ValueError('Missing required original source: ' + path.name)
    config = json.loads(config_path.read_text())
    if (config.get('case_id') != config.get('selected_case_id')
            or config.get('duration_s') != 30 or config.get('rate_hz') != HZ
            or not isinstance(config.get('case'), dict)
            or config['case'].get('case_id') != config.get('case_id')
            or config['case'].get('name') not in ('reference', 'contrast')):
        raise ValueError('Exact saved case differs')
    provenance = json.loads(provenance_path.read_text())
    synthetic = provenance.get('provenance_kind') == 'synthetic_fixture'
    if (provenance.get('case_id') != config['case_id']
            or provenance.get('diagnostic_fixture') is not synthetic
            or provenance.get('provenance_kind') not in ('synthetic_fixture', 'native')):
        raise ValueError('Original acquisition provenance differs')
    videos = [name + '.mkv' for name in VIEWS]
    for video in videos:
        if not (attempt / video).is_file():
            raise ValueError('Missing required original camera: ' + video)
    measurement = derive(rows(trace_path), rows(map_path))
    sources = {'acquisition-provenance.json': sha(provenance_path),
               'trace.jsonl': sha(trace_path),
               'video_frames.jsonl': sha(map_path),
               **{video: sha(attempt / video) for video in videos}}
    channel_dir = attempt / 'channels'
    channel_dir.mkdir()
    channel = channel_dir / 'speed_mps.jsonl'
    channel.write_text(''.join(json.dumps({'time_s': i / HZ, 'value': speed}) + '\n'
                               for i, speed in enumerate(measurement['speed_series_mps'])))
    acceleration_channel = channel_dir / 'acceleration_mps2.jsonl'
    acceleration_channel.write_text(''.join(json.dumps({'time_s': i / HZ, 'value': value}) + '\n'
                                            for i, value in enumerate(measurement['acceleration_series_mps2'])))
    summary = {key: value for key, value in measurement.items()
               if not key.endswith('_series_mps') and not key.endswith('_series_mps2')}
    report = {'format': 'c229597-source-motion-analysis-v1',
              'case_id': config['case_id'],
              'measurements': {
                  'text_0_motion': {'method': 'derive', 'value': summary,
                                    'sources': sources},
                  'reviewed_scope_0_motion': {'method': 'derive', 'value': summary,
                                              'sources': sources}},
              'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    result = {
        'case_id': config['case_id'],
        'measured_values': summary,
        'target_checks': [{'target': 'source_recorded_acceleration_episode',
                           'requested': '30-second source review',
                           'measured': summary['speed_increase_mps'],
                           'method': 'original Native velocity vector joined to frame map',
                           'tolerance': 0.0, 'matched': False,
                           'physical_cause_confirmed': False,
                           'cause_evidence': sorted(sources)}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': '600 saved frames analyzed; physical review pending',
        'physical_failure_flags': ['highway, jurisdiction, route and exhibition require Native review'],
        'trace_reference': 'trace.jsonl',
        'video_references': videos,
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': json.loads((attempt / 'construction.json').read_text())['recording_description'],
        'recording_evidence': [{'name': 'ego_speed', 'unit': 'm/s',
                                'reference': 'channels/speed_mps.jsonl'},
                               {'name': 'ego_acceleration', 'unit': 'm/s2',
                                'reference': 'channels/acceleration_mps2.jsonl'}],
        'realized_observables': {},
        'provenance_kind': 'synthetic_local_diagnostic' if synthetic else 'source_review_unverified',
        'accepted': False, 'legal_verdict_claimed': False,
    }
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2,
                                                    allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
