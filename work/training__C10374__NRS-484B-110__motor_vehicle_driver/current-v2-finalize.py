"""Source-only zone primary diagnostic finalizer; no designation or legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_zone_overlap(attempt):
    root = Path(attempt)
    actors = rows(root / 'native-raw-actors.jsonl')
    map_path = root / 'native-map-readback.json'
    if not map_path.is_file():
        raise ValueError('Missing required source: native-map-readback.json')
    mapping = json.loads(map_path.read_text())
    if len(actors) != 600 or len(mapping.get('native_zone_delimiters', [])) != 4:
        raise ValueError('Zone actor or delimiter source incomplete')
    bounds = mapping['zone_rectangle_xy_m']
    count = 0
    for index, row in enumerate(actors):
        ego = row['ego']
        body = ego['body_native_xyz_m']
        xs = [point[0] for point in body]
        ys = [point[1] for point in body]
        if row['frame'] != index or len(body) != 8:
            raise ValueError('Original body/frame join changed')
        if max(xs) >= bounds[0] and min(xs) <= bounds[1] and max(ys) >= bounds[2] and min(ys) <= bounds[3] and ego['speed_mps'] > 0.1:
            count += 1
    return {'value': count, 'method': 'measure_zone_overlap',
            'sources': {'native-raw-actors.jsonl': sha(root / 'native-raw-actors.jsonl'),
                        'native-map-readback.json': sha(map_path)},
            'scope': 'body versus authored rectangle; official designation unverified'}


def finalize(attempt, output):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    measurement = measure_zone_overlap(root)
    actors = rows(root / 'native-raw-actors.jsonl')
    frames = rows(root / 'video_frames.jsonl')
    trace = rows(root / 'trace.jsonl')
    evidence = rows(root / 'capture/evidence.jsonl')
    if any(len(source) != 600 for source in (actors, frames, trace, evidence)):
        raise ValueError('Original source counts differ')
    for actor, frame, motion, source in zip(actors, frames, trace, evidence):
        native = actor['native_frame']
        if any(value != native for value in (frame['native_frame'], frame['carla_frame'], motion['frame'], source['original_frame'])):
            raise ValueError('Original Native frame join differs')
        if any(abs(value - actor['time_s']) > 1e-6 for value in (frame['time_s'], motion['time_s'], source['recording_time_s'])):
            raise ValueError('Original Native time join differs')
    channels = root / 'channels'
    if channels.exists():
        raise ValueError('Fixture supplied derived channels')
    channels.mkdir()
    for name, value in (
        ('kin.speed', lambda row: row['ego']['speed_mps']),
        ('zone_body', lambda row: row['ego']['body_native_xyz_m']),
    ):
        (channels / (name + '.jsonl')).write_text(''.join(
            json.dumps({'time_s': row['time_s'], 'value': value(row)}) + '\n' for row in actors))
    planned = config['recording_description']
    evidence_rows = [{'name': channel['name'], 'unit': channel['unit'],
                      'reference': 'channels/' + channel['name'] + '.jsonl'}
                     for channel in planned['channels']]
    observed = measurement['value']
    requested = 1 if config['requested_zone_route'] else 0
    measured = int(observed > 0)
    result = {
        'case_id': config['case_id'],
        'measured_values': {'moving_body_rectangle_overlap_frames': observed},
        'target_checks': [{'target': 'moving vehicle body overlaps authored zone rectangle',
                           'requested': requested, 'measured': measured,
                           'method': 'source-hashed complete body polygon at 20 Hz',
                           'tolerance': 0, 'matched': requested == measured,
                           'physical_cause_confirmed': False,
                           'cause_evidence': ['native-raw-actors.jsonl', 'native-map-readback.json']}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'synthetic full-duration source fixture processed',
        'physical_failure_flags': ['official_safety_zone_designation_unverified',
                                   'original_native_motion_and_pixels_unverified'],
        'trace_reference': 'trace.jsonl',
        'video_references': ['overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': planned, 'recording_evidence': evidence_rows,
        'realized_observables': {}, 'provenance_kind': 'synthetic_cpu_fixture',
        'accepted': False, 'legal_verdict_claimed': False,
    }
    (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    report = {'format': 'c10374-zone-current-v2-analysis', 'case_id': config['case_id'],
              'measurements': {'zone_overlap_frames': measurement},
              'source_only': True, 'official_safety_zone_designation_verified': False,
              'legal_outcome_claimed': False}
    Path(output).write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
