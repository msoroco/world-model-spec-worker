"""Exact source-bound parked lamp meter; no low-beam legal shortcut."""
import json
import math
import re
from pathlib import Path
import xml.etree.ElementTree as ET

FRAMES = 600
HZ = 20
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def check_config(config, road_text):
    prefix = 'training__C276263__NRS-484D-165-4__motor_vehicle_driver__'
    if (config.get('case_id') not in (prefix+'probe_a',prefix+'probe_b')
            or config.get('law_id') != 'NRS-484D-165-4'
            or config.get('cell_id') != 'C276263'
            or config.get('actor') != 'motor_vehicle_driver'
            or config.get('duration_s') != 30 or config.get('rate_hz') != HZ
            or config.get('frames') != FRAMES
            or config.get('physical_completion') not in (False,{})
            or config.get('legal_verdict') is not None):
        raise ValueError('C276263 exact scope or duration differs')
    if tuple(c.get('name') for c in config.get('cameras',())) != VIEWS:
        raise ValueError('Four source cameras required')
    if any(c.get('fps') != HZ or not all(c.get(k) for k in
           ('width','height','fov_deg','location_xyz_m','rotation_pyr_deg'))
           for c in config['cameras']):
        raise ValueError('Source camera geometry incomplete')
    root = ET.fromstring(road_text)
    road = root.find('road')
    if road is None or road.get('id') != '1':
        raise ValueError('Sloped road missing')
    elevation = road.find('./elevationProfile/elevation')
    if elevation is None or not 0 < float(elevation.get('b','0')) < 0.1:
        raise ValueError('Road grade missing')
    lanes = {(x.get('id'),x.get('type')) for x in road.findall('./lanes/laneSection/right/lane')}
    if not {('-1','driving'),('-2','parking'),('-3','sidewalk')} <= lanes:
        raise ValueError('Curb parking lane or sidewalk source missing')
    if not any(o.get('type') == 'curbstone' for o in road.findall('objects/object')):
        raise ValueError('Curb-edge source missing')
    if not config.get('original_beam_pixel_review_required'):
        raise ValueError('Pixel beam evidence required')
    return {'case_id':config['case_id'],'frames':FRAMES,
            'source_cameras':list(VIEWS),'authored_grade':float(elevation.get('b')),
            'actual_parking_observed':False,'beam_depressed_or_dimmed_observed':False,
            'carla_contacted':False,'physical_completion':False}


def measure(rows, source_kind):
    if source_kind not in ('authored_native_request','original_native'):
        raise ValueError('Unknown source kind')
    if len(rows) != FRAMES:
        raise ValueError('Full 600-frame lamp source required')
    states = set()
    observed_states = set()
    parked_frames = 0
    reviewed_frames = 0
    for i,row in enumerate(rows):
        if (row.get('frame') != i or
                abs(row.get('time_s',-1) - (i+1)/HZ) > 1e-8 or
                row.get('source_kind') != source_kind):
            raise ValueError('Original frame/time/source join differs')
        xyz = row.get('ego_center_xyz_m')
        if not isinstance(xyz,list) or len(xyz)!=3 or not all(
                isinstance(v,(int,float)) and math.isfinite(v) for v in xyz):
            raise ValueError('Original position missing')
        speed = row.get('ego_speed_mps')
        if not isinstance(speed,(int,float)) or not math.isfinite(speed) or speed < 0:
            raise ValueError('Original speed missing')
        if row.get('requested_headlamp_lit') is not True:
            raise ValueError('Lighted-headlamp request absent')
        state = row.get('requested_beam_state')
        if state not in ('low_beam','high_beam'):
            raise ValueError('Distinct requested beam state missing')
        states.add(state)
        if source_kind == 'original_native':
            if not isinstance(row.get('observed_light_state_bits'),int):
                raise ValueError('Original CARLA light-state readback missing')
            observed = row.get('observed_beam_state')
            if observed not in ('low_beam','high_beam','off','unknown'):
                raise ValueError('Original beam state readback missing')
            observed_states.add(observed)
            if not isinstance(row.get('beam_pixel_review'),dict):
                raise ValueError('Original beam aim/intensity pixel review missing')
            review = row['beam_pixel_review']
            if review.get('status') not in ('pending','reviewed'):
                raise ValueError('Beam pixel review status missing')
            if review['status'] == 'reviewed':
                if not isinstance(review.get('source_path'),str) or not review['source_path']:
                    raise ValueError('Beam pixel source missing')
                if not re.fullmatch('[0-9a-f]{64}',review.get('source_sha256','')):
                    raise ValueError('Beam pixel source hash missing')
                if not all(isinstance(review.get(k),(int,float)) and math.isfinite(review[k])
                           for k in ('aim_elevation_deg','relative_intensity')):
                    raise ValueError('Measured beam aim/intensity missing')
                reviewed_frames += 1
            if row.get('observed_parking_activity') not in ('parked','loading','unloading','unknown'):
                raise ValueError('Original parking activity missing')
            if row['observed_parking_activity'] == 'parked':
                parked_frames += 1
            footprint = row.get('observed_footprint_xyz_m')
            if not isinstance(footprint,list) or len(footprint) < 4 or any(
                    not isinstance(v,list) or len(v)!=3 or not all(
                        isinstance(x,(int,float)) and math.isfinite(x) for x in v)
                    for v in footprint):
                raise ValueError('Original vehicle footprint missing')
            if not isinstance(row.get('observed_curb_lane_id'),int):
                raise ValueError('Original curb lane readback missing')
    if len(states)!=1:
        raise ValueError('Beam request changed within parked window')
    return {'format':'c276263-parked-headlamp-meter-v1',
            'source_kind':source_kind,'frames':FRAMES,'requested_beam_state':states.pop(),
            'observed_beam_states':sorted(observed_states),
            'parked_activity_frames':parked_frames,
            'beam_pixel_reviewed_frames':reviewed_frames,
            'actual_parking_observed':source_kind=='original_native' and parked_frames==FRAMES,
            'beam_depressed_or_dimmed_observed':False,
            'legal_verdict':None,'original_native_observed':source_kind=='original_native'}


def read_and_measure(path,source_kind):
    return measure([json.loads(line) for line in Path(path).read_text().splitlines()],
                   source_kind)
