"""Source-bound taxi passenger/merchandise draft request checks."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

FRAMES = 600
HZ = 20
VIEWS = ('overview', 'approach', 'curb_reference', 'driver_reference')
PREFIX = 'training__C394327__LVMC-11-60-040__taxi_driver__'


def check_config(config, road_text):
    if (config.get('case_id') not in (PREFIX+'probe_a', PREFIX+'probe_b')
            or config.get('law_id') != 'LVMC-11-60-040'
            or config.get('cell_id') != 'C394327'
            or config.get('actor') != 'taxi_driver'
            or config.get('duration_s') != 30 or config.get('rate_hz') != HZ
            or config.get('frames') != FRAMES
            or config.get('physical_completion') is not False
            or config.get('legal_verdict') is not None):
        raise ValueError('C394327 exact scope or timing differs')
    if tuple(c.get('name') for c in config.get('cameras', ())) != VIEWS:
        raise ValueError('Four named source cameras required')
    if any(c.get('fps') != HZ or not all(c.get(k) for k in
               ('width', 'height', 'fov_deg', 'location_xyz_m', 'rotation_pyr_deg'))
           for c in config['cameras']):
        raise ValueError('Source camera geometry incomplete')
    road = ET.fromstring(road_text).find('road')
    if road is None or road.find('./planView/geometry/line') is None:
        raise ValueError('Street source missing')
    lanes = {(l.get('id'), l.get('type')) for l in
             road.findall('./lanes/laneSection/right/lane')}
    if {('-1', 'driving'), ('-2', 'parking'), ('-3', 'sidewalk')} - lanes:
        raise ValueError('Taxi curb lane source missing')
    if not any(o.get('id') == '701' and o.get('type') == 'parkingSpace'
               for o in road.findall('objects/object')):
        raise ValueError('Taxi stand curb proposal missing')
    if not any(s.get('name') == 'TAXI STAND'
               for s in road.findall('signals/signal')):
        raise ValueError('Taxi stand sign proposal missing')
    if not config.get('designation_source_required') or not config.get('other_regulations_review_required'):
        raise ValueError('Stand designation and other stopping rules require source review')
    return {'frames': FRAMES, 'source_cameras': list(VIEWS),
            'authored_taxi_stand': True, 'actual_activity_observed': False,
            'other_regulations_reviewed': False, 'carla_contacted': False,
            'physical_completion': False}


def measure(rows, source_kind):
    if source_kind not in ('authored_native_request', 'original_native'):
        raise ValueError('Unknown source kind')
    if len(rows) != FRAMES:
        raise ValueError('Full 600-frame source required')
    activities = set()
    exchange_frames = 0
    counts = []
    for i, row in enumerate(rows):
        if (row.get('frame') != i or abs(row.get('time_s', -1) - (i+1)/HZ) > 1e-8
                or row.get('source_kind') != source_kind):
            raise ValueError('Frame/time/source join differs')
        if source_kind == 'original_native':
            source = row.get('original_source')
            if not isinstance(source, dict) or not all(
                    isinstance(source.get(key), str) and source[key]
                    for key in ('native_capture_path', 'native_capture_sha256',
                                'participant_review_path', 'participant_review_sha256',
                                'designation_review_path', 'designation_review_sha256',
                                'other_regulations_review_path', 'other_regulations_review_sha256')):
                raise ValueError('Original taxi, participant, designation and regulation sources missing')
            if (row.get('observed_taxi_identity') is not True or
                    row.get('observed_stand_location') != 'outside_designated_stand'):
                raise ValueError('Observed taxi identity or outside-stand location missing')
            speed = row.get('observed_speed_mps')
            door = row.get('observed_door_open')
            count = row.get('observed_occupant_count')
            activity = row.get('observed_activity')
        else:
            if (row.get('requested_taxi_identity') is not True or
                    row.get('requested_stand_location') != 'outside_designated_stand'):
                raise ValueError('Taxicab identity or outside-stand request missing')
            speed = row.get('requested_speed_mps')
            door = row.get('requested_door_open')
            count = row.get('requested_occupant_count')
            activity = row.get('requested_activity')
        if speed != 0 or door not in (True, False):
            raise ValueError('Stopped taxi or door source missing')
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise ValueError('Occupant count missing')
        counts.append(count)
        if activity not in ('passenger_loading', 'merchandise_loading', 'no_activity'):
            raise ValueError('Loading activity source missing')
        activities.add(activity)
        if activity != 'no_activity':
            exchange_frames += 1
    active = activities - {'no_activity'}
    if len(active) != 1 or exchange_frames == 0:
        raise ValueError('Single actual loading activity required in request')
    activity = active.pop()
    if activity == 'passenger_loading' and max(counts) <= min(counts):
        raise ValueError('Passenger occupancy transition missing')
    if activity == 'merchandise_loading' and max(counts) != min(counts):
        raise ValueError('Merchandise request cannot include passenger transition')
    return {'requested_activity': activity, 'active_frames': exchange_frames,
            'active_duration_s': exchange_frames/HZ, 'legal_verdict': None,
            'occupant_count_min': min(counts), 'occupant_count_max': max(counts),
            'original_native_observed': source_kind == 'original_native'}


def read_and_measure(path, kind):
    return measure([json.loads(s) for s in Path(path).read_text().splitlines()], kind)
