"""Finalize original adjacent-lane body measurements; leave legal judgment open."""
import argparse
import hashlib
import json
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('road.xodr', 'lane-inventory.json', 'split-review.json',
           'classification-review.json', 'duty-review.json',
           'actor-poses.jsonl', 'video_frames.jsonl', 'overview.mkv')
CHANNELS = ('ru.subject', 'ru.motorcycle', 'ru.moped', 'st.lane_adjacency',
            'rel.occupies', 'drv.straddles_marking', 'rel.bearing',
            'rel.longitudinal_overlap', 'ru.motor_vehicle', 'kin.velocity',
            'police_duty_context')


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def overlap(a, b):
    return min(a['max_x'], b['max_x']) > max(a['min_x'], b['min_x'])


def midpoint(box):
    return (box['min_y'] + box['max_y']) / 2


def split_observation(root):
    root = Path(root)
    files = {name: required(root, name) for name in SOURCES}
    for camera in CAMERAS:
        required(root, camera + '.mkv')
    inventory = json.loads(files['lane-inventory.json'].read_text())
    review = json.loads(files['split-review.json'].read_text())
    classification = json.loads(files['classification-review.json'].read_text())
    duty = json.loads(files['duty-review.json'].read_text())
    diagnostic = (root / 'fixture-provenance.json').is_file()
    expected = 'synthetic_diagnostic' if diagnostic else 'independently_reviewed'
    for item in (review, classification, duty):
        if item.get('review_status') != expected or not item.get('reviewer') or not item.get('source'):
            raise ValueError('Independent split, classification and duty context reviews required')
    if len({item['source'] for item in (review, classification, duty)}) != 3:
        raise ValueError('Split, classification and duty sources must be separate')
    if review.get('road_sha256') != sha(files['road.xodr']) or review.get('pose_sha256') != sha(files['actor-poses.jsonl']):
        raise ValueError('Split review source binding differs')
    if review.get('overview_sha256') != sha(files['overview.mkv']) and not (diagnostic and review.get('overview_sha256') == 'synthetic_rgb_source'):
        raise ValueError('Split review pixel binding differs')
    if inventory.get('source_kind') != 'native_saved_sample' or inventory.get('cell_id') != 'C178141':
        raise ValueError('Original Native lane and actor inventory absent')
    if len(inventory.get('lane_survey', [])) != 10 or len(inventory.get('other_vehicle_ids', [])) != 2:
        raise ValueError('Original adjacent lane or participant readback absent')
    if classification.get('pose_sha256') != sha(files['actor-poses.jsonl']) or classification.get('subject_kind') not in ('motorcycle', 'moped'):
        raise ValueError('Machine classification source absent or stale')
    if duty.get('pose_sha256') != sha(files['actor-poses.jsonl']) or type(duty.get('subject_is_police_officer')) is not bool or type(duty.get('subject_performing_police_duty')) is not bool:
        raise ValueError('Police duty context source absent or stale')
    if not duty.get('officer_identity_source') or not duty.get('performance_of_duty_source') or duty['officer_identity_source'] == duty['performance_of_duty_source']:
        raise ValueError('Officer identity and duty performance require separate sources')
    if duty['subject_performing_police_duty'] and not duty['subject_is_police_officer']:
        raise ValueError('Police duty context inconsistent with officer identity')
    poses, mapping = rows(files['actor-poses.jsonl']), rows(files['video_frames.jsonl'])
    if len(poses) != 600 or len(mapping) != 600:
        raise ValueError('Incomplete original 600-frame source join')
    between, speed_samples, channels = [], [], {name: [] for name in CHANNELS}
    previous = -1
    for index, (pose, frame) in enumerate(zip(poses, mapping)):
        native = pose.get('native_frame')
        if type(native) is not int or native <= previous or frame.get('native_frame') != native:
            raise ValueError('Original Native frame join differs')
        previous = native
        if pose.get('video_frame') != index or frame.get('video_frame') != index:
            raise ValueError('Original video frame join differs')
        if abs(pose.get('time_s', -1) - index / 20) > 1e-4 or abs(frame.get('time_s', -1) - index / 20) > 1e-4:
            raise ValueError('Original frame/time join differs')
        cameras = {name: native for name in CAMERAS}
        if pose.get('camera_native_frames') != cameras or frame.get('camera_native_frames') != cameras:
            raise ValueError('Original four-camera frame join differs')
        if pose.get('other_vehicle_ids') != inventory['other_vehicle_ids']:
            raise ValueError('Surrounding vehicle actor identity differs')
        subject = pose.get('subject_footprint_m')
        others = pose.get('other_vehicle_footprints_m')
        speeds = pose.get('other_vehicle_speeds_mps')
        if not isinstance(subject, dict) or not isinstance(others, list) or len(others) != 2 or not isinstance(speeds, list) or len(speeds) != 2:
            raise ValueError('Original body or speed source missing')
        for box in [subject, *others]:
            if any(type(box.get(k)) not in (float, int) for k in ('min_x', 'max_x', 'min_y', 'max_y')) or box['min_x'] >= box['max_x'] or box['min_y'] >= box['max_y']:
                raise ValueError('Original finite body footprint invalid')
        if any(type(speed) not in (float, int) or speed < 0 for speed in speeds):
            raise ValueError('Original surrounding vehicle speed invalid')
        speed_samples.append(speeds)
        lo, hi = sorted(others, key=midpoint)
        active = midpoint(lo) < midpoint(subject) < midpoint(hi) and overlap(subject, lo) and overlap(subject, hi)
        between.append(active)
        values = {'ru.subject': {'actor_id': pose['subject_id'], 'footprint_m': subject},
                  'ru.motorcycle': {'classification': classification['subject_kind'], 'motorcycle_source': review['source']},
                  'ru.moped': {'classification': classification['subject_kind'], 'moped_alternative': classification['subject_kind'] == 'moped'},
                  'st.lane_adjacency': {'lane_survey': inventory['lane_survey'], 'review_source': review['source']},
                  'rel.occupies': {'between_body_order_and_overlap': active, 'lane_occupancy': review['lane_occupancy']},
                  'drv.straddles_marking': {'subject_footprint_m': subject, 'marking_source': review.get('marking_source')},
                  'rel.bearing': {'subject_y_m': midpoint(subject), 'other_y_m': [midpoint(box) for box in others]},
                  'rel.longitudinal_overlap': {'with_lower': overlap(subject, lo), 'with_upper': overlap(subject, hi)},
                  'ru.motor_vehicle': {'actor_ids': inventory['other_vehicle_ids'], 'footprints_m': others},
                  'kin.velocity': {'other_vehicle_speeds_mps': speeds, 'subject_xyz_m': pose.get('subject_xyz_m')},
                  'police_duty_context': {'officer_identity_source': duty['officer_identity_source'],
                      'performance_of_duty_source': duty['performance_of_duty_source'],
                      'officer_source_claim': duty['subject_is_police_officer'],
                      'duty_performance_source_claim': duty['subject_performing_police_duty']}}
        for name, value in values.items():
            channels[name].append({'time_s': index / 20, 'value': value})
    intervals = []
    start = None
    for index, active in enumerate(between + [False]):
        if active and start is None:
            start = index
        elif not active and start is not None:
            intervals.append([start, index - 1])
            start = None
    value = {'between_vehicle_frames': sum(between), 'between_vehicle_intervals': intervals,
             'left_vehicle_speed_mps_range': [min(row[0] for row in speed_samples), max(row[0] for row in speed_samples)],
             'right_vehicle_speed_mps_range': [min(row[1] for row in speed_samples), max(row[1] for row in speed_samples)],
             'subject_kind_source_claim': classification['subject_kind'],
             'classification_reference_status': classification.get('chapter_definition_status'),
             'police_officer_source_claim': duty['subject_is_police_officer'],
             'performance_of_duty_source_claim': duty['subject_performing_police_duty'],
             'officer_identity_source': duty['officer_identity_source'],
             'performance_of_duty_source': duty['performance_of_duty_source'],
             'police_duty_exception': 'requires_independent_legal_review',
             'adjacent_lane_occupancy_source_claim': review['lane_occupancy'],
             'source_sha256': {name: sha(path) for name, path in files.items()},
             'legal_verdict_claimed': False,
             'limitations': ['Body ordering and longitudinal overlap are observations, not a legal threshold or verdict.',
                             'Original classification, lane occupancy and police duty require independent review.']}
    return value, channels


def position_observation(root):
    value, _ = split_observation(root)
    return {'between_vehicle_frames': value['between_vehicle_frames'],
            'between_vehicle_intervals': value['between_vehicle_intervals']}


def classification_observation(root):
    value, _ = split_observation(root)
    return {'subject_kind_source_claim': value['subject_kind_source_claim'],
            'classification_reference_status': value['classification_reference_status']}


def duty_observation(root):
    value, _ = split_observation(root)
    return {'police_officer_source_claim': value['police_officer_source_claim'],
            'performance_of_duty_source_claim': value['performance_of_duty_source_claim'],
            'officer_identity_source': value['officer_identity_source'],
            'performance_of_duty_source': value['performance_of_duty_source']}


def lane_observation(root):
    value, _ = split_observation(root)
    return {'adjacent_lane_occupancy_source_claim': value['adjacent_lane_occupancy_source_claim'],
            'left_vehicle_speed_mps_range': value['left_vehicle_speed_mps_range'],
            'right_vehicle_speed_mps_range': value['right_vehicle_speed_mps_range']}


def report(root):
    root = Path(root)
    config = json.loads(required(root, 'config.json').read_text())
    value, channels = split_observation(root)
    sources = value['source_sha256']
    items = {'stationary_between': ('position_observation', position_observation(root)),
             'moving_or_stationary': ('lane_observation', lane_observation(root)),
             'police_duty_exception': ('duty_observation', duty_observation(root)),
             'machine_classification': ('classification_observation', classification_observation(root))}
    measurements = {key: {'method': method, 'value': observed, 'sources': sources}
                    for key, (method, observed) in items.items()}
    return {'format': 'worker-analysis-report-v1', 'case_id': config['case_id'],
            'measurements': measurements, 'scope': 'Original body/lanes and separately reviewed classification and duty sources'}, channels


def finalize(root, output):
    from worker_exchange.native_output import physical_result, provenance_record, write_result
    root, output = Path(root), Path(output)
    if output.exists() or (root / 'result.json').exists():
        raise ValueError('Use a fresh finalization stage')
    config = json.loads(required(root, 'config.json').read_text())
    analysis, channels = report(root)
    if {row['name'] for row in config['recording_description']['channels']} != set(CHANNELS):
        raise ValueError('Declared adjacent-lane channels differ')
    channel_dir = root / 'channels'
    channel_dir.mkdir(exist_ok=True)
    for name, values in channels.items():
        (channel_dir / (name + '.jsonl')).write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in values))
    value, _ = split_observation(root)
    target_between = config['split_case'] == 'between'
    measured_between = value['between_vehicle_frames'] > 0
    target = {'target': 'original motorcycle body between occupied adjacent-lane vehicles',
              'requested': target_between, 'measured': measured_between,
              'method': 'source-bound original body/vehicle interval', 'tolerance': 0,
              'matched': target_between == measured_between,
              'physical_cause_confirmed': False, 'cause_evidence': list(SOURCES)}
    evidence = [{'name': name, 'unit': 'source', 'reference': name} for name in SOURCES]
    evidence += [{'name': row['name'], 'unit': row['unit'], 'reference': row['source']}
                 for row in config['recording_description']['channels']]
    result = {'case_id': config['case_id'], 'measured_values': value,
              'target_checks': [target], 'setup_confirmed': False,
              'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'Awaiting original physical and source review',
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
