"""Finalize source-bound device-zone observations; retain legal and authority uncertainty."""
import argparse
import hashlib
import json
from pathlib import Path
from measure_zone import CAMERAS, measure

SOURCES = ('road.xodr', 'device-inventory.json', 'device-review.json',
           'condition-review.json', 'activity-review.json', 'exception-review.json',
           'vehicle-poses.jsonl', 'video_frames.jsonl', 'overview.mkv')
CHANNELS = ('ego_pose', 'device_prohibited_place_occupancy', 'device_identity',
            'device_authority', 'device_instruction_and_scope', 'device_condition',
            'civil_time', 'vehicle_activity', 'traffic_conflict_context',
            'law_compliance_context', 'police_direction_context', 'device_direction_context',
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
    for name in CAMERAS:
        required(root, name + '.mkv')
    inventory = json.loads(paths['device-inventory.json'].read_text())
    device = json.loads(paths['device-review.json'].read_text())
    condition = json.loads(paths['condition-review.json'].read_text())
    activity = json.loads(paths['activity-review.json'].read_text())
    exception = json.loads(paths['exception-review.json'].read_text())
    diagnostic = (root / 'fixture-provenance.json').is_file()
    expected = 'synthetic_diagnostic' if diagnostic else 'independently_reviewed'
    for review in (device, condition, activity, exception):
        if review.get('review_status') != expected or not review.get('reviewer'):
            raise ValueError('Independent device, condition, activity and exception sources required')
    if len({review.get('source') for review in (device, condition, activity, exception)}) != 4:
        raise ValueError('Review source identities must be separate')
    road_hash = sha(paths['road.xodr'])
    pose_hash = sha(paths['vehicle-poses.jsonl'])
    if inventory.get('cell_id') != 'C135709' or inventory.get('source_kind') != 'native_saved_sample':
        raise ValueError('Original device inventory absent')
    if device.get('road_sha256') != road_hash or condition.get('device_review_sha256') != sha(paths['device-review.json']):
        raise ValueError('Device or condition source binding differs')
    if activity.get('pose_sha256') != pose_hash or exception.get('pose_sha256') != pose_hash:
        raise ValueError('Activity or exception source binding differs')
    if device.get('pixel_sha256') != sha(paths['overview.mkv']) and not (diagnostic and device.get('pixel_sha256') == 'synthetic_rgb_source'):
        raise ValueError('Device pixel binding differs')
    if device.get('device_code') not in ('no_stopping', 'no_standing', 'no_parking'):
        raise ValueError('Device instruction source absent')
    zone = device.get('governed_zone_bounds_m')
    poses, frames = rows(paths['vehicle-poses.jsonl']), rows(paths['video_frames.jsonl'])
    if len(poses) != 600 or len(frames) != 600:
        raise ValueError('Incomplete original 600-frame source join')
    observations = []
    channels = {name: [] for name in CHANNELS}
    prior_native = -1
    for index, (pose, frame) in enumerate(zip(poses, frames)):
        native = pose.get('native_frame')
        if type(native) is not int or native <= prior_native or frame.get('native_frame') != native:
            raise ValueError('Original Native frame join differs')
        prior_native = native
        if pose.get('video_frame') != index or frame.get('video_frame') != index:
            raise ValueError('Original video frame join differs')
        if abs(pose.get('time_s', -1) - index / 20) > 1e-6 or abs(frame.get('time_s', -1) - index / 20) > 1e-6:
            raise ValueError('Original frame/time join differs')
        cameras = {name: native for name in CAMERAS}
        if pose.get('camera_native_frames') != cameras or frame.get('camera_native_frames') != cameras:
            raise ValueError('Original four-camera frame join differs')
        xyz = pose.get('vehicle_xyz_m')
        half_length, half_width = pose.get('bbox_half_length_m'), pose.get('bbox_half_width_m')
        if not isinstance(xyz, list) or len(xyz) != 3 or not isinstance(half_length, (int, float)) or not isinstance(half_width, (int, float)):
            raise ValueError('Original vehicle pose or body absent')
        footprint = {'min_x': xyz[0] - half_length, 'max_x': xyz[0] + half_length,
                     'min_y': xyz[1] - half_width, 'max_y': xyz[1] + half_width}
        obs = {'video_frame': index, 'native_frame': native, 'time_s': index / 20,
               'source_cameras': {name: index for name in CAMERAS},
               'observed_speed_mps': pose['observed_speed_mps'], 'vehicle_footprint_m': footprint}
        observations.append(obs)
        values = {'ego_pose': {'xyz_m': xyz, 'speed_mps': pose['observed_speed_mps']},
                  'device_prohibited_place_occupancy': {'zone_bounds_m': zone, 'footprint_m': footprint},
                  'device_identity': {'device_code': device['device_code']},
                  'device_authority': {'authority_source': device.get('authority_source'), 'official_status': device.get('official_status')},
                  'device_instruction_and_scope': {'instruction': device['device_code'], 'zone_bounds_m': zone},
                  'device_condition': {'condition': condition.get('condition'), 'class': condition.get('vehicle_class')},
                  'civil_time': {'civil_time': condition.get('civil_time')},
                  'vehicle_activity': {'activity': activity.get('activity'), 'purpose': activity.get('purpose')},
                  'traffic_conflict_context': {'necessity_source': exception.get('traffic_conflict_source')},
                  'law_compliance_context': {'law_source': exception.get('law_compliance_source')},
                  'police_direction_context': {'police_source': exception.get('police_direction_source')},
                  'device_direction_context': {'device_source': exception.get('device_direction_source')},
                  'source_camera_frame_join': cameras}
        for name, value in values.items():
            channels[name].append({'time_s': index / 20, 'value': value})
    value = measure(zone, observations)
    value.update({'device_code': device['device_code'], 'official_status': device.get('official_status'),
                  'authority_source': device.get('authority_source'), 'device_traffic_purpose': device.get('traffic_purpose'),
                  'device_legal_consistency': device.get('legal_consistency'),
                  'condition': condition.get('condition'), 'civil_time': condition.get('civil_time'),
                  'vehicle_class_condition': condition.get('vehicle_class'),
                  'activity': activity.get('activity'), 'purpose': activity.get('purpose'),
                  'responsible_person_source': activity.get('responsible_person_source'),
                  'actual_service_activity': activity.get('actual_service_activity'),
                  'traffic_conflict_source': exception.get('traffic_conflict_source'),
                  'law_compliance_source': exception.get('law_compliance_source'),
                  'police_direction_source': exception.get('police_direction_source'),
                  'device_direction_source': exception.get('device_direction_source'),
                  'source_sha256': {name: sha(path) for name, path in paths.items()},
                  'legal_verdict_claimed': False})
    return value, channels


def zone_observation(root):
    value, _ = measured(root)
    return {'zone_overlap_during_rest': value['zone_overlap_during_rest'], 'rest_interval_frames': value['rest_interval_frames']}


def device_observation(root):
    value, _ = measured(root)
    return {key: value[key] for key in ('device_code', 'official_status', 'authority_source', 'device_traffic_purpose', 'device_legal_consistency')}


def condition_observation(root):
    value, _ = measured(root)
    return {key: value[key] for key in ('condition', 'civil_time', 'vehicle_class_condition')}


def activity_observation(root):
    value, _ = measured(root)
    return {key: value[key] for key in ('activity', 'purpose', 'responsible_person_source', 'actual_service_activity')}


def exception_observation(root):
    value, _ = measured(root)
    return {key: value[key] for key in ('traffic_conflict_source', 'law_compliance_source',
            'police_direction_source', 'device_direction_source')}


def report(root):
    root = Path(root)
    config = json.loads(required(root, 'config.json').read_text())
    value, channels = measured(root)
    sources = value['source_sha256']
    items = {'device_zone_measurement': ('zone_observation', zone_observation(root)),
             'device_identity_authority': ('device_observation', device_observation(root)),
             'condition_and_time': ('condition_observation', condition_observation(root)),
             'vehicle_activity': ('activity_observation', activity_observation(root)),
             'statutory_exceptions': ('exception_observation', exception_observation(root))}
    measurements = {key: {'method': method, 'value': observed, 'sources': sources}
                    for key, (method, observed) in items.items()}
    return {'format': 'worker-analysis-report-v1', 'case_id': config['case_id'],
            'measurements': measurements,
            'scope': 'Original device-zone motion and independently reviewed device, condition, activity and exception sources'}, channels


def finalize(root, output):
    from worker_exchange.native_output import physical_result, provenance_record, write_result
    root, output = Path(root), Path(output)
    if output.exists() or (root / 'result.json').exists():
        raise ValueError('Use a fresh finalization stage')
    config = json.loads(required(root, 'config.json').read_text())
    analysis, channels = report(root)
    if {row['name'] for row in config['recording_description']['channels']} != set(CHANNELS):
        raise ValueError('Declared device-zone channels differ')
    channel_dir = root / 'channels'
    channel_dir.mkdir(exist_ok=True)
    for name, values in channels.items():
        (channel_dir / (name + '.jsonl')).write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in values))
    value = measured(root)[0]
    requested = config['zone_case'] == 'inside'
    target = {'target': 'original stationary footprint within independently reviewed device zone',
              'requested': requested, 'measured': value['zone_overlap_during_rest'],
              'method': 'source-bound 600-frame Native body and speed', 'tolerance': 0,
              'matched': value['zone_overlap_during_rest'] == requested,
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
              **provenance_record(root), 'accepted': False, 'legal_verdict_claimed': False}
    physical_result(root, result)
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + '\n')
    write_result(root, result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
