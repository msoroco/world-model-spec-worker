"""Exact six-case change-lane request policy; original source remains unobserved."""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET

DISTANCES_FT = (90, 100, 110, 290, 300, 310)
FRAMES = 600
RATE_HZ = 20
COURSE_CHANGE_ODOMETER_M = 120.0
SPEED_REQUEST_MPS = 5.0


def road_xml() -> str:
    """Authored straight, same-direction two-lane road for the frozen cell."""
    return ('<OpenDRIVE><header revMajor="1" revMinor="4" name="C245490-change-lane" '
        'version="1" date="2026-11-26" north="10" south="-10" east="200" west="-100" '
        'vendor="worker"/><road id="1" name="same-direction-two-lane" length="300" '
        'junction="-1"><planView><geometry s="0" x="-100" y="0" hdg="0" '
        'length="300"><line/></geometry></planView><elevationProfile><elevation '
        's="0" a="0" b="0" c="0" d="0"/></elevationProfile><lanes><laneOffset '
        's="0" a="0" b="0" c="0" d="0"/><laneSection s="0"><center><lane '
        'id="0" type="none" level="false"><roadMark sOffset="0" type="solid" '
        'color="yellow" width="0.12"/></lane></center><right><lane id="-1" '
        'type="driving" level="false"><width sOffset="0" a="3.5" b="0" '
        'c="0" d="0"/><roadMark sOffset="0" type="broken" color="white" '
        'width="0.12"/></lane><lane id="-2" type="driving" level="false">'
        '<width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark '
        'sOffset="0" type="solid" color="white" width="0.12"/></lane>'
        '</right></laneSection></lanes></road></OpenDRIVE>')


def verify_road(xml: str) -> dict:
    root = ET.fromstring(xml)
    roads = root.findall('./road')
    if len(roads) != 1 or float(roads[0].get('length')) < 270:
        raise ValueError('Approach road too short for 300-foot signaling')
    lanes = roads[0].findall('./lanes/laneSection/right/lane')
    if [lane.get('id') for lane in lanes] != ['-1', '-2'] or any(
            lane.get('type') != 'driving' for lane in lanes):
        raise ValueError('Same-direction change-lane source missing')
    return {'lane_ids': ['-1', '-2'], 'length_m': float(roads[0].get('length')),
            'source_kind': 'authored_OpenDRIVE_unverified_Native'}


def area_for_distance(distance_ft: int) -> str:
    if distance_ft not in DISTANCES_FT:
        raise ValueError('Unselected signal boundary')
    return 'business_or_residential' if distance_ft < 200 else 'other'


def request(distance_ft: int) -> dict:
    area = area_for_distance(distance_ft)
    onset = COURSE_CHANGE_ODOMETER_M - distance_ft * 0.3048
    if onset <= 0 or COURSE_CHANGE_ODOMETER_M / SPEED_REQUEST_MPS >= FRAMES / RATE_HZ:
        raise ValueError('Signal onset or lane change outside 600-frame approach')
    return {'requested_signal_distance_ft': distance_ft, 'area_class_requested': area,
        'signal_onset_odometer_m': onset,
        'course_change_request_odometer_m': COURSE_CHANGE_ODOMETER_M,
        'speed_request_mps': SPEED_REQUEST_MPS, 'frames': FRAMES,
        'rate_hz': RATE_HZ, 'duration_s': FRAMES / RATE_HZ,
        'signal_side': 'left', 'maneuver': 'change_lane',
        'layout': 'same_direction_multilane', 'control': 'lane_marking',
        'area_class_originally_verified': False, 'legal_verdict': None}


def controls(distance_ft: int, odometer_m: float) -> dict:
    if not math.isfinite(odometer_m) or odometer_m < 0:
        raise ValueError('Invalid original odometer readback')
    plan = request(distance_ft)
    return {'left_signal_requested': odometer_m >= plan['signal_onset_odometer_m'],
        'lane_change_requested': odometer_m >= COURSE_CHANGE_ODOMETER_M,
        'signal_requested_only': True}
