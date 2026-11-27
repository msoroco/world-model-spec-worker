"""Saved-only freight-zone reduction from original Native and independent reviews.

Requests, zone sign art and actor proximity do not decide material/passenger
transfer, interference, statutory expeditiousness, or legal compliance.
"""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from measure_freight import CAMERAS, FRAMES, measure


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def read_review(path, kind, case_id):
    require(path.is_file(), 'Missing required source: ' + path.name)
    review = json.loads(path.read_text())
    require(review.get('source_kind') == kind and review.get('case_id') == case_id and
            review.get('reviewer') and review.get('full_interval_reviewed') is True,
            'independent full-interval source review required: ' + path.name)
    return review


def frame_ids(review, key):
    value = review.get(key)
    require(isinstance(value, list) and all(type(i) is int and 0 <= i < FRAMES for i in value)
            and len(value) == len(set(value)), 'reviewed frame set missing: ' + key)
    return set(value)


def measure_saved(attempt, case_id):
    attempt = Path(attempt)
    for name in ('road.xodr', 'freight_trace.jsonl', 'ego_body.jsonl',
                 'material_body.jsonl', 'passenger_body.jsonl', 'waiting_body.jsonl',
                 'video_frames.jsonl'):
        require((attempt / name).is_file(), 'Missing required source: ' + name)
    zone = read_review(attempt / 'zone-review.json', 'independent_original_zone_review', case_id)
    activity = read_review(attempt / 'activity-review.json', 'independent_original_activity_review', case_id)
    require(zone['reviewer'] != activity['reviewer'], 'independent zone and activity reviewers required')
    require(zone.get('native_map_sha256') == sha(attempt / 'road.xodr') and
            zone.get('zone_kind') == 'freight_curb_loading' and
            zone.get('zone_marking_source_id') and zone.get('regulatory_sign_source_id') and
            zone.get('sign_hours_source_id') and zone.get('civil_time_source_id'),
            'original marked zone, sign or civil-time source missing')
    video_hashes = {name: sha(attempt / (name + '.mkv')) for name in CAMERAS}
    require(activity.get('video_sha256') == video_hashes and
            activity.get('materials_vehicle_classification_source_id') and
            activity.get('passenger_identity_source_id') and
            activity.get('material_identity_source_id'),
            'four original video or activity identity review missing')
    body_hashes = {name: sha(attempt / name) for name in
                   ('ego_body.jsonl', 'material_body.jsonl', 'passenger_body.jsonl', 'waiting_body.jsonl')}
    require(activity.get('body_sha256') == body_hashes,
            'original actor body source changed')
    source_rows = rows(attempt / 'freight_trace.jsonl')
    frame_rows = rows(attempt / 'video_frames.jsonl')
    require(len(source_rows) == len(frame_rows) == FRAMES, '600 joined original frames required')
    within = frame_ids(zone, 'vehicle_within_zone_frame_ids')
    material_pickup = frame_ids(activity, 'pickup_loading_frame_ids')
    material_delivery = frame_ids(activity, 'unloading_delivery_frame_ids')
    passenger_load = frame_ids(activity, 'passenger_loading_frame_ids')
    passenger_unload = frame_ids(activity, 'passenger_unloading_frame_ids')
    waiting = frame_ids(activity, 'materials_vehicle_waiting_frame_ids')
    approaching = frame_ids(activity, 'materials_vehicle_about_to_enter_frame_ids')
    require(not (material_pickup & material_delivery) and
            not (passenger_load & passenger_unload) and
            not (waiting & approaching), 'overlapping original activity classifications')
    start, end = zone.get('effective_start_minute_local'), zone.get('effective_end_minute_local')
    observed = []
    vehicle_ids = set()
    for index, (raw, frame) in enumerate(zip(source_rows, frame_rows)):
        require(raw.get('video_frame') == frame.get('video_frame') == index and
                raw.get('native_frame') == frame.get('native_frame') and
                raw.get('source_cameras') == frame.get('source_cameras') and
                abs(raw.get('time_s', -100) - index / 20) < 1e-6,
                'original Native/video frame join changed')
        vehicle_ids.add(raw.get('vehicle_id'))
        clock = datetime.fromisoformat(raw['civil_timestamp'])
        require(clock.tzinfo is not None, 'original civil clock offset missing')
        minute = clock.hour * 60 + clock.minute + clock.second / 60
        observed.append({'video_frame': index, 'native_frame': raw['native_frame'],
                         'time_s': index / 20, 'source_cameras': frame['source_cameras'],
                         'civil_minute_local': minute, 'vehicle_id': raw['vehicle_id'],
                         'zone_occupancy': 'within_marked_zone' if index in within else 'outside_zone',
                         'observed_speed_mps': raw['observed_speed_mps'],
                         'material_activity': 'pickup_loading' if index in material_pickup else
                           'unloading_delivery' if index in material_delivery else 'none_observed',
                         'passenger_activity': 'loading' if index in passenger_load else
                           'unloading' if index in passenger_unload else 'none_observed',
                         'material_vehicle_wait_state': 'waiting_to_enter' if index in waiting else
                           'about_to_enter' if index in approaching else 'none_observed'})
    require(len(vehicle_ids) == 1 and None not in vehicle_ids, 'original vehicle identity changed')
    context = {'source_kind': 'original_native_freight_zone_sources',
               'native_map_sha256': sha(attempt / 'road.xodr'),
               'zone_marking_sha256': sha(attempt / 'zone-review.json'),
               'regulatory_sign_sha256': sha(attempt / 'zone-review.json'),
               'sign_hours_source_sha256': sha(attempt / 'zone-review.json'),
               'civil_time_source_sha256': sha(attempt / 'freight_trace.jsonl'),
               'vehicle_identity_sha256': sha(attempt / 'ego_body.jsonl'),
               'material_activity_source_sha256': sha(attempt / 'activity-review.json'),
               'passenger_activity_source_sha256': sha(attempt / 'activity-review.json'),
               'waiting_vehicle_source_sha256': sha(attempt / 'waiting_body.jsonl'),
               'zone_kind': 'freight_curb_loading',
               'effective_start_minute_local': start,
               'effective_end_minute_local': end,
               'vehicle_id': next(iter(vehicle_ids))}
    measured = measure(context, observed)
    measured['case_id'] = case_id
    measured['source_sha256'] = {name: sha(attempt / name) for name in
                                ('road.xodr', 'freight_trace.jsonl', 'video_frames.jsonl',
                                 'zone-review.json', 'activity-review.json')}
    measured['original_sign_authority'] = 'independent_review_required'
    measured['original_activity_reviewed'] = True
    measured['interference'] = 'requires_original_spatial_and_temporal_review'
    measured['legal_compliance'] = 'unassessed'
    return measured, observed


def measure_freight_zone(attempt, case_id):
    return measure_saved(attempt, case_id)[0]


def finalize(attempt, output):
    attempt = Path(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    case_id = config['selected_case_id']
    measured, observed = measure_saved(attempt, case_id)
    construction = json.loads((attempt / 'construction.json').read_text())
    channel_evidence = []
    folder = attempt / 'channels'
    folder.mkdir(exist_ok=True)
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        relative = 'channels/' + name + '.jsonl'
        with (attempt / relative).open('x') as stream:
            for row in observed:
                stream.write(json.dumps({'time_s': row['time_s'],
                                         'value': row.get(name, row)}, allow_nan=False) + '\n')
        channel_evidence.append({'name': name, 'unit': channel['unit'], 'reference': relative})
    instance = {item['name']: {'source_sha256': measured['source_sha256'],
                               'original_source_review_required': True}
                for item in construction['recording_description']['context_inputs']}
    (attempt / 'instance-context.json').write_text(
        json.dumps(instance, sort_keys=True, allow_nan=False) + '\n')
    for item in construction['recording_description']['context_inputs']:
        channel_evidence.append({'name': item['name'], 'unit': item['unit'],
                                 'reference': 'instance-context.json'})
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': {'freight_zone_observation': {
                  'method': 'measure_freight_zone', 'value': measured,
                  'sources': measured['source_sha256']}},
              'source_complete': True, 'physical_or_legal_acceptance': False}
    result = {'case_id': case_id, 'measured_values': measured,
              'target_checks': [{'target': 'source-reviewed marked-zone stop',
                                 'requested': 'source-reviewed original',
                                 'measured': measured['zone_stopped_during_effective_hours_frames'],
                                 'method': 'measure_freight_zone', 'tolerance': 0,
                                 'matched': measured['zone_stopped_during_effective_hours_frames'] > 0,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(measured['source_sha256'])}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved original-source reduction; physical review pending',
              'physical_failure_flags': ['Original physical completion unconfirmed'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in
                                   ('overview', 'approach', 'reference_corner', 'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': channel_evidence,
              'realized_observables': {}, 'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    Path(output).write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
