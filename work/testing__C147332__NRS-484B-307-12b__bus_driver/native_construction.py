"""CPU-checkable one-way road and bus route geometry for the red-X cases.

The road and head are engineering candidates. Official highway/device status
requires a separately reviewed original source packet before Native dispatch.
"""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

from bus_route import BUS_HALF_WIDTH_M, ROUTES, route


ROAD_LENGTH_M = 90.0
LANE_WIDTH_M = 3.6
ROAD_ID = "147332"


def candidate_opendrive():
    return '''<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="4" name="C147332 red-X engineering candidate" version="1" north="3" south="-8" east="90" west="0" vendor="worker-candidate"/>
  <road name="one-way two-lane engineering candidate" length="90" id="147332" junction="-1">
    <link/>
    <planView><geometry s="0" x="0" y="0" hdg="0" length="90"><line/></geometry></planView>
    <elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile>
    <lateralProfile/>
    <lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0"><center><lane id="0" type="none" level="false"/></center>
        <right>
          <lane id="-1" type="driving" level="false"><width sOffset="0" a="3.6" b="0" c="0" d="0"/><roadMark sOffset="0" type="broken" weight="standard" color="white" width="0.12" laneChange="both"/></lane>
          <lane id="-2" type="driving" level="false"><width sOffset="0" a="3.6" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" weight="standard" color="white" width="0.12" laneChange="none"/></lane>
        </right>
      </laneSection>
    </lanes>
  </road>
</OpenDRIVE>
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_road(path):
    path = Path(path)
    tree = ET.parse(path)
    road = tree.getroot().find('road')
    if road is None or road.attrib.get('id') != ROAD_ID or float(road.attrib.get('length', 0)) != ROAD_LENGTH_M:
        raise ValueError('wrong exact one-way road source')
    right = road.find('./lanes/laneSection/right')
    if right is None:
        raise ValueError('right-hand one-way lanes missing')
    lanes = {int(lane.attrib['id']): lane for lane in right.findall('lane')}
    if set(lanes) != {-1, -2} or any(lane.attrib.get('type') != 'driving' for lane in lanes.values()):
        raise ValueError('two right-side driving lanes required')
    if any(float(lane.find('width').attrib['a']) != LANE_WIDTH_M for lane in lanes.values()):
        raise ValueError('source lane width differs from route contract')
    if road.find('./lanes/laneSection/left/lane') is not None:
        raise ValueError('counterflow lane present in one-way road')
    return {'road_id': ROAD_ID, 'road_sha256': sha(path), 'lane_ids': [-1, -2],
            'lane_width_m': LANE_WIDTH_M, 'native_import_verified': False}


def check_scene(scene, road_path):
    suffix = scene.get('case_id', '').removeprefix(scene.get('assignment_id', '') + '__')
    if suffix not in ROUTES or scene.get('route') != route(suffix):
        raise ValueError('exact bus route differs from case construction')
    if scene.get('bus_blueprint_id') != 'vehicle.mitsubishi.fusorosa':
        raise ValueError('exact bus blueprint changed')
    if scene.get('map_source_sha256') != sha(road_path):
        raise ValueError('scene map source differs from original candidate bytes')
    source = check_road(road_path)
    signal = scene.get('signal', {})
    if (signal.get('display') != 'red_x' or signal.get('governed_lane_id') != 'red_lane' or
            signal.get('longitudinal_m') != 50.0 or
            signal.get('lateral_m') != -1.8 or signal.get('height_m', 0) < 5.0):
        raise ValueError('overhead red X is not placed above governed lane')
    for x, y in scene['route']['waypoint_centers_m']:
        if not (0 <= x <= ROAD_LENGTH_M and -7.2 + BUS_HALF_WIDTH_M < y < -BUS_HALF_WIDTH_M):
            raise ValueError('full bus width departs the two driving lanes')
    return {'case_id': scene['case_id'], 'road': source,
            'bus_route_target_checked': True, 'signal_geometry_target_checked': True,
            'official_device_reviewed': False, 'native_motion_verified': False}
