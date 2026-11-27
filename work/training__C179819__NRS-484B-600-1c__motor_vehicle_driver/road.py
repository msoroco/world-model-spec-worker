"""Two same-direction lanes and a clear 1,800 m speed-observation corridor."""
import xml.etree.ElementTree as ET

LENGTH_M = 1800.0
EGO_LANE_ID = -1
OTHER_LANE_ID = -2


def open_drive():
    width = '<width sOffset="0" a="3.7" b="0" c="0" d="0" />'
    lane = lambda ident: f'<lane id="{ident}" type="driving" level="false">{width}<roadMark sOffset="0" type="broken" color="white" width="0.12" /></lane>'
    return ('<OpenDRIVE><header revMajor="1" revMinor="4" name="C179819-posted-speed-road" version="1" '
            'date="2026-11-25" north="20" south="-20" east="1800" west="0" vendor="worker" />'
            '<road id="1" name="C179819_posted_corridor" length="1800" junction="-1">'
            '<link /><planView><geometry s="0" x="0" y="0" hdg="0" length="1800"><line /></geometry></planView>'
            '<elevationProfile><elevation s="0" a="0" b="0" c="0" d="0" /></elevationProfile>'
            '<lanes><laneOffset s="0" a="0" b="0" c="0" d="0" /><laneSection s="0">'
            '<left /><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width="0.12" /></lane></center>'
            f'<right>{lane(EGO_LANE_ID)}{lane(OTHER_LANE_ID)}</right>'
            '</laneSection></lanes><objects /><signals><signal id="30" s="40" t="-4.1" name="authored_30_mph" dynamic="no" orientation="+" zOffset="2" country="US" type="274" subtype="0" value="30" unit="mph" /></signals></road></OpenDRIVE>')


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    if road is None or road.attrib.get('id') != '1' or float(road.attrib['length']) != LENGTH_M:
        raise ValueError('Corridor identity or length differs')
    if {int(l.attrib['id']) for l in root.findall('.//lane') if l.attrib.get('type') == 'driving'} != {EGO_LANE_ID, OTHER_LANE_ID}:
        raise ValueError('Separate ego and other-vehicle driving lanes required')
    if float(road.find('planView/geometry').attrib['length']) != LENGTH_M:
        raise ValueError('Surveyed route geometry differs from road length')
    signal = road.find('signals/signal')
    if (signal is None or signal.attrib.get('value') != '30' or
            signal.attrib.get('unit') != 'mph' or float(signal.attrib.get('s', -1)) != 40):
        raise ValueError('Authored 30 mph source sign omitted')
    return {'road_id': 1, 'posted_corridor_m': LENGTH_M, 'ego_lane_id': EGO_LANE_ID,
            'other_vehicle_lane_id': OTHER_LANE_ID, 'same_direction': True,
            'other_vehicle_constructed': True, 'speed_target_verified': False}
