"""Source-bound emergency-passage wait request meter, without legal verdict."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

FRAMES = 600
VIEWS = ('overview','approach','right_edge','driver_reference')
PREFIX = 'training__C405647__NRS-484B-267-1c__motor_vehicle_driver__'


def check_config(config, road_text):
    if (config.get('case_id') not in (PREFIX+'probe_a',PREFIX+'probe_b')
            or config.get('law_id') != 'NRS-484B-267-1c'
            or config.get('cell_id') != 'C405647'
            or config.get('actor') != 'motor_vehicle_driver'
            or config.get('duration_s') != 30 or config.get('rate_hz') != 20
            or config.get('frames') != FRAMES
            or config.get('physical_completion') is not False
            or config.get('legal_verdict') is not None):
        raise ValueError('C405647 exact scope or timing differs')
    if tuple(c.get('name') for c in config.get('cameras',())) != VIEWS:
        raise ValueError('Four named source cameras required')
    if any(c.get('fps') != 20 or not all(c.get(k) for k in
           ('width','height','fov_deg','location_xyz_m','rotation_pyr_deg'))
           for c in config['cameras']):
        raise ValueError('Source camera geometry incomplete')
    road = ET.fromstring(road_text).find('road')
    if road is None or road.find('./planView/geometry/line') is None:
        raise ValueError('Road source missing')
    lanes = {(l.get('id'),l.get('type')) for l in road.findall('./lanes/laneSection/right/lane')}
    if {('-1','driving'),('-2','driving'),('-3','shoulder')} - lanes:
        raise ValueError('Approach lane and right-edge source missing')
    if not all(config.get(k) is True for k in
               ('emergency_authorization_source_required','qualifying_flashes_source_required',
                'officer_direction_source_required','original_passage_source_required')):
        raise ValueError('Emergency qualification, officer direction and passage need sources')
    return {'frames':FRAMES,'source_cameras':list(VIEWS),
            'authored_approach_road':True,'actual_passing_observed':False,
            'qualifying_flashes_verified':False,'carla_contacted':False,
            'physical_completion':False}


def measure(rows, source_kind):
    if source_kind not in ('authored_native_request','original_native'):
        raise ValueError('Unknown source kind')
    if len(rows) != FRAMES:
        raise ValueError('Full 600-frame source required')
    passage = []
    whole_body_passage = []
    movement = []
    for i,row in enumerate(rows):
        if (row.get('frame') != i or abs(row.get('time_s',-1)-(i+1)/20) > 1e-8
                or row.get('source_kind') != source_kind):
            raise ValueError('Frame/time/source join differs')
        ego = row.get('ego_center_xy_m')
        emergency = row.get('emergency_center_xy_m')
        speed = row.get('ego_speed_mps')
        if (not isinstance(ego,list) or len(ego)!=2 or
            not isinstance(emergency,list) or len(emergency)!=2 or
            not all(isinstance(v,(int,float)) for v in ego+emergency) or
            not isinstance(speed,(int,float)) or speed < 0):
            raise ValueError('Native position or velocity source missing')
        if row.get('requested_flashing_lights') is not True:
            raise ValueError('Flashing-light request missing')
        ego_body = row.get('ego_body_xy_m')
        emergency_body = row.get('emergency_body_xy_m')
        if (not isinstance(ego_body, list) or len(ego_body) < 4 or
            not isinstance(emergency_body, list) or len(emergency_body) < 4 or
            any(not isinstance(point, list) or len(point) != 2 or
                any(not isinstance(value, (int, float)) for value in point)
                for point in ego_body + emergency_body)):
            raise ValueError('Both original body footprints required for whole-vehicle passage')
        if source_kind == 'original_native':
            if not all(isinstance(row.get(k),dict) for k in
                       ('emergency_authorization_review','flashing_light_review',
                        'officer_direction_review','body_footprint_review')):
                raise ValueError('Original emergency qualification or direction source missing')
        passage.append(emergency[1]-ego[1])
        whole_body_passage.append(min(point[1] for point in emergency_body) -
                                  max(point[1] for point in ego_body))
        if speed > 0:
            movement.append(i)
    if not passage[0] < 0 < passage[-1] or not whole_body_passage[0] < 0 < whole_body_passage[-1]:
        raise ValueError('Emergency passage span missing')
    if not movement:
        raise ValueError('Ego release span missing')
    cross = next(i for i,d in enumerate(passage) if d > 0)
    full_pass = next(i for i,d in enumerate(whole_body_passage) if d > 0)
    return {'requested_center_passage_frame':cross,
            'requested_whole_body_passage_frame':full_pass,
            'requested_first_ego_motion_frame':movement[0],
            'requested_waits_through_whole_body_passage':movement[0] > full_pass,
            'legal_verdict':None,'original_native_observed':source_kind=='original_native'}


def read_and_measure(path,kind):
    return measure([json.loads(s) for s in Path(path).read_text().splitlines()],kind)
