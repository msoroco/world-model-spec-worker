"""Source-bound saved finalization of curbside two-vehicle stopping geometry."""
import argparse
import hashlib
import json
from pathlib import Path

from double_parking_meter import measure

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('road.xodr', 'map-geometry.json', 'vehicle-poses.jsonl',
           'body-footprints.jsonl', 'video_frames.jsonl',
           'highway-review.json', 'activity-review.json',
           'exception-review.json', 'pixel-review.json',
           'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')
CHANNELS = ('ego_pose', 'curbside_pose', 'curb_geometry',
            'ego_highway_side_of_curbside', 'longitudinal_overlap_m',
            'lateral_surface_gap_m', 'concurrent_overlap_at_rest',
            'longest_concurrent_run_frames', 'activity_context',
            'traffic_conflict_context', 'law_compliance_context',
            'police_direction_context', 'device_direction_context',
            'source_camera_frame_join')


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def measured(root):
    root = Path(root)
    paths = {name: required(root, name) for name in SOURCES}
    geometry = json.loads(paths['map-geometry.json'].read_text())
    highway = json.loads(paths['highway-review.json'].read_text())
    activity = json.loads(paths['activity-review.json'].read_text())
    exception = json.loads(paths['exception-review.json'].read_text())
    pixel = json.loads(paths['pixel-review.json'].read_text())
    diagnostic = (root / 'fixture-provenance.json').is_file()
    expected = 'synthetic_diagnostic' if diagnostic else 'independently_reviewed'
    for review in (highway, activity, exception, pixel):
        if review.get('review_status') != expected or not review.get('reviewer'):
            raise ValueError('Independent highway, activity, exception and pixel sources required')
    if len({r.get('source') for r in (highway, activity, exception, pixel)}) != 4:
        raise ValueError('Independent review source identities must be separate')
    if geometry.get('cell_id') != 'C229398' or geometry.get('source_kind') != 'surveyed_map_geometry':
        raise ValueError('Original surveyed curb geometry required')
    if highway.get('road_sha256') != sha(paths['road.xodr']) or highway.get('map_sha256') != sha(paths['map-geometry.json']):
        raise ValueError('Highway or curb authority binding differs')
    body_hash = sha(paths['body-footprints.jsonl'])
    if activity.get('body_sha256') != body_hash or exception.get('body_sha256') != body_hash:
        raise ValueError('Activity or exception source binding differs')
    if pixel.get('overview_sha256') != sha(paths['overview.mkv']) and not (
            diagnostic and pixel.get('overview_sha256') == 'synthetic_four_view_source'):
        raise ValueError('Pixel review does not bind source video')
    pose_rows = rows(paths['vehicle-poses.jsonl'])
    body_rows = rows(paths['body-footprints.jsonl'])
    frame_rows = rows(paths['video_frames.jsonl'])
    if len(pose_rows) != 600 or len(body_rows) != 600 or len(frame_rows) != 600:
        raise ValueError('Incomplete original 600-frame two-vehicle source join')
    channels = {name: [] for name in CHANNELS}
    subject_id = curbside_id = None
    prior_native = -1
    for i, (pose, body, frame) in enumerate(zip(pose_rows, body_rows, frame_rows)):
        native = pose.get('native_frame')
        if type(native) is not int or native <= prior_native or body.get('native_frame') != native or frame.get('native_frame') != native:
            raise ValueError('Original Native frame join differs')
        prior_native = native
        if pose.get('video_frame') != i or body.get('frame') != i or frame.get('video_frame') != i:
            raise ValueError('Original 600-frame index join differs')
        if any(abs(row.get('time_s', -1) - i / 20) > 1e-6 for row in (pose, body, frame)):
            raise ValueError('Original frame time join differs')
        camera_frames = {name: native for name in CAMERAS}
        if pose.get('camera_native_frames') != camera_frames or frame.get('camera_native_frames') != camera_frames:
            raise ValueError('Original four-camera frame join differs')
        actors = body.get('actors', {})
        current_subject = pose.get('subject_actor_id')
        current_curbside = pose.get('curbside_actor_id')
        if (actors.get('ego', {}).get('actor_id') != current_subject or
                actors.get('curbside', {}).get('actor_id') != current_curbside or
                current_subject == current_curbside):
            raise ValueError('Original two-vehicle actor identity join differs')
        if i == 0:
            subject_id, curbside_id = current_subject, current_curbside
        if (current_subject, current_curbside) != (subject_id, curbside_id):
            raise ValueError('Original actor identity changed mid-capture')
        values = {
            'ego_pose': {'xyz_m': pose.get('subject_xyz_m'), 'speed_mps': pose.get('observed_speed_mps')},
            'curbside_pose': {'xyz_m': pose.get('curbside_xyz_m')},
            'curb_geometry': geometry,
            'ego_highway_side_of_curbside': {'footprint': actors['ego']['footprint_corners_xy_m']},
            'longitudinal_overlap_m': {'two_original_footprints': actors},
            'lateral_surface_gap_m': {'two_original_footprints': actors},
            'concurrent_overlap_at_rest': {'frame': i},
            'longest_concurrent_run_frames': {'frame': i},
            'activity_context': {'requested': pose.get('requested_activity'), 'review': activity.get('activity')},
            'traffic_conflict_context': {'source': exception.get('traffic_conflict_source')},
            'law_compliance_context': {'source': exception.get('law_compliance_source')},
            'police_direction_context': {'source': exception.get('police_direction_source')},
            'device_direction_context': {'source': exception.get('device_direction_source')},
            'source_camera_frame_join': camera_frames,
        }
        for name, value in values.items():
            channels[name].append({'time_s': i / 20, 'value': value})
    diagnostic_value = measure(paths['map-geometry.json'], paths['body-footprints.jsonl'])
    diagnostic_value.update({
        'highway_authority_source': highway.get('highway_authority_source'),
        'curb_authority_source': highway.get('curb_authority_source'),
        'activity': activity.get('activity'), 'purpose_source': activity.get('purpose_source'),
        'traffic_conflict_source': exception.get('traffic_conflict_source'),
        'law_compliance_source': exception.get('law_compliance_source'),
        'police_direction_source': exception.get('police_direction_source'),
        'device_direction_source': exception.get('device_direction_source'),
        'source_sha256': {name: sha(path) for name, path in paths.items()},
        'legal_verdict_claimed': False,
    })
    return diagnostic_value, channels


def place_observation(root):
    value, _ = measured(root)
    return {'concurrent_overlap_at_rest_frame_count': value['concurrent_overlap_at_rest_frame_count'],
            'max_longitudinal_overlap_m': value['max_longitudinal_overlap_m'],
            'min_lateral_surface_gap_m': value['min_lateral_surface_gap_m']}


def activity_observation(root):
    value, _ = measured(root)
    return {'activity': value['activity'], 'purpose_source': value['purpose_source'],
            'longest_concurrent_run_frames': value['longest_concurrent_run_frames']}


def exception_observation(root):
    value, _ = measured(root)
    return {key: value[key] for key in ('traffic_conflict_source', 'law_compliance_source',
                                        'police_direction_source', 'device_direction_source')}


def report(root):
    root = Path(root)
    config = json.loads(required(root, 'config.json').read_text())
    value, channels = measured(root)
    sources = value['source_sha256']
    items = {
        'highway_side_place': ('place_observation', place_observation(root)),
        'stop_mode': ('activity_observation', activity_observation(root)),
        'stand_mode': ('activity_observation', activity_observation(root)),
        'park_mode': ('activity_observation', activity_observation(root)),
        'traffic_conflict_necessity': ('exception_observation', exception_observation(root)),
        'compliance_with_law': ('exception_observation', exception_observation(root)),
        'police_direction': ('exception_observation', exception_observation(root)),
        'device_direction': ('exception_observation', exception_observation(root)),
    }
    measurements = {key: {'method': method, 'value': observed, 'sources': sources}
                    for key, (method, observed) in items.items()}
    return {'format': 'worker-analysis-report-v1', 'case_id': config['case_id'],
            'measurements': measurements,
            'scope': 'Original two-vehicle curbside body/halt and independent activity and exception sources'}, channels


def finalize(root, output):
    from worker_exchange.native_output import physical_result, provenance_record, write_result
    root, output = Path(root), Path(output)
    if output.exists() or (root / 'result.json').exists():
        raise ValueError('Fresh saved finalization stage required')
    config = json.loads(required(root, 'config.json').read_text())
    analysis, channels = report(root)
    if {row['name'] for row in config['recording_description']['channels']} != set(CHANNELS):
        raise ValueError('Declared double-parking channels differ')
    channel_dir = root / 'channels'
    channel_dir.mkdir(exist_ok=True)
    for name, values in channels.items():
        (channel_dir / (name + '.jsonl')).write_text(''.join(
            json.dumps(row, allow_nan=False) + '\n' for row in values))
    value = measured(root)[0]
    requested = config['case_id'].rsplit('__', 1)[-1] != 'clear'
    measured_overlap = value['concurrent_overlap_at_rest_frame_count'] > 0
    target = {'target': 'original stationary highway-side body overlap with curbside stopped vehicle',
              'requested': requested, 'measured': measured_overlap,
              'method': 'source-bound 600-frame two-body geometry and halt', 'tolerance': 0,
              'matched': requested == measured_overlap,
              'physical_cause_confirmed': False, 'cause_evidence': list(SOURCES)}
    evidence = [{'name': name, 'unit': 'source', 'reference': name} for name in SOURCES]
    evidence += [{'name': row['name'], 'unit': row['unit'], 'reference': row['source']}
                 for row in config['recording_description']['channels']]
    result = {'case_id': config['case_id'], 'measured_values': value,
              'target_checks': [target], 'setup_confirmed': False,
              'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'Awaiting original source and physical review',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              **provenance_record(root), 'accepted': False,
              'legal_verdict_claimed': False}
    physical_result(root, result)
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + '\n')
    write_result(root, result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
