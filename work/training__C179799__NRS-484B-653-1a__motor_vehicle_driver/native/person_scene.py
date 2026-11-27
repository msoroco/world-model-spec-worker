"""Authored paved route and roadside worker placement for the selected scope.

Geometry and controls are prospective. Highway status, public access, actor
identity, actual sight lines, and physical success require original sources.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

ROAD_LENGTH_M = 180.0
LANE_WIDTH_M = 3.5
EGO_START_X_M = -78.0
WORKER_X_M = 4.0
WORKER_Y_M = -5.2
WORKER_ROUTE_RELATION = "roadside worker outside right driving-lane edge"
MODES = {"condition_a": "earlier_response", "condition_b": "later_response"}


def open_drive() -> str:
    return f'''<?xml version="1.0" standalone="yes"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="4" name="C179799 authored paved route" version="1.00" date="2026-11-27" north="10" south="-10" east="90" west="-90" vendor="worker"/>
  <road name="C179799 paved route" length="{ROAD_LENGTH_M}" id="1" junction="-1">
    <link/><type s="0" type="town"/>
    <planView><geometry s="0" x="-90" y="0" hdg="0" length="{ROAD_LENGTH_M}"><line/></geometry></planView>
    <elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile>
    <lateralProfile/><lanes>
      <laneSection s="0"><left>
        <lane id="1" type="driving" level="false"><link/><width sOffset="0" a="{LANE_WIDTH_M}" b="0" c="0" d="0"/><roadMark sOffset="0" type="broken" weight="standard" color="white" width="0.12"/></lane>
      </left><center><lane id="0" type="none" level="false"><link/><roadMark sOffset="0" type="solid" weight="standard" color="yellow" width="0.12"/></lane></center><right>
        <lane id="-1" type="driving" level="false"><link/><width sOffset="0" a="{LANE_WIDTH_M}" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" weight="standard" color="white" width="0.12"/></lane>
      </right></laneSection></lanes><objects/><signals/>
  </road>
</OpenDRIVE>'''


def inspect() -> dict:
    root = ET.fromstring(open_drive())
    roads = root.findall('road')
    if len(roads) != 1 or roads[0].attrib.get('id') != '1':
        raise ValueError('Authored route identity changed')
    lanes = roads[0].findall('./lanes/laneSection/*/lane')
    if {(lane.attrib['id'], lane.attrib['type']) for lane in lanes} != {
            ('1', 'driving'), ('0', 'none'), ('-1', 'driving')}:
        raise ValueError('Paved route driving lanes changed')
    if WORKER_Y_M >= -LANE_WIDTH_M or WORKER_X_M <= EGO_START_X_M:
        raise ValueError('Roadside worker placement changed')
    return {'road_id': 1, 'driving_lane_id': -1,
            'worker_xy_m': [WORKER_X_M, WORKER_Y_M],
            'worker_relation': WORKER_ROUTE_RELATION,
            'ego_start_xy_m': [EGO_START_X_M, -LANE_WIDTH_M / 2]}


def require_source_packet(packet: dict, case_id: str) -> dict:
    if not isinstance(packet, dict) or packet.get('case_id') != case_id:
        raise ValueError('Exact-case original context source required')
    required = ('highway_or_public_access_source', 'access_kind',
                'driver_identity_source', 'vehicle_class_source',
                'worker_identity_source', 'worker_role_source',
                'worker_route_relation_source', 'sight_line_source',
                'surface_condition_source', 'nearby_property_source')
    if not all(packet.get(key) for key in required):
        raise ValueError('Original public-access, worker, driver, and encounter context source required')
    if packet['access_kind'] not in ('highway', 'public_access_premises'):
        raise ValueError('Highway or public-access-premises status unresolved')
    if packet['access_kind'] == 'public_access_premises' and not packet.get('excluded_driveway_and_farm_way_review_source'):
        raise ValueError('Public-access premises exclusions need an original source')
    if packet.get('physical_verified') is True or packet.get('legal_verdict') is not None:
        raise ValueError('Prospective source packet cannot establish physical or legal result')
    return packet
