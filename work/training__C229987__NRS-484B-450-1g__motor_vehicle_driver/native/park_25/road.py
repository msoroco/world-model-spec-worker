"""Straight Native approach with a roadside traffic signal specification.

The runner must read back the physical actor and governed lane; authored XML
alone does not establish official status or legal applicability.
"""
import xml.etree.ElementTree as ET

LENGTH_M = 180.0
EGO_LANE_ID = -1
SIGNAL_STATION_M = 100.0
SIGNAL_LATERAL_M = -4.2
SIGNAL_ID = '401'


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4',
                  name='C229987-roadside-signal', version='1', date='2026-11-26',
                  north='20', south='-20', east='180', west='0', vendor='worker')
    road = ET.SubElement(root, 'road', id='1', name='c229987_highway_approach',
                         length=str(LENGTH_M), junction='-1')
    ET.SubElement(road, 'link')
    geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                             s='0', x='0', y='0', hdg='0', length=str(LENGTH_M))
    ET.SubElement(geometry, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    centre = ET.SubElement(section, 'center')
    ET.SubElement(centre, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    lane = ET.SubElement(right, 'lane', id=str(EGO_LANE_ID), type='driving', level='false')
    ET.SubElement(lane, 'width', sOffset='0', a='3.7', b='0', c='0', d='0')
    ET.SubElement(lane, 'roadMark', sOffset='0', type='broken', color='white', width='.12')
    ET.SubElement(road, 'objects')
    signals = ET.SubElement(road, 'signals')
    ET.SubElement(signals, 'signal', id=SIGNAL_ID, name='roadside-vehicular-head',
                  s=str(SIGNAL_STATION_M), t=str(SIGNAL_LATERAL_M), zOffset='4.5',
                  hOffset='0', orientation='+', dynamic='yes', country='OpenDRIVE',
                  type='1000001', subtype='1')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    road = root.find("road[@id='1']")
    signal = road.find("signals/signal[@id='401']") if road is not None else None
    lane = road.find("lanes/laneSection/right/lane[@id='-1']") if road is not None else None
    if (road is None or float(road.attrib['length']) != LENGTH_M or
            signal is None or signal.attrib['dynamic'] != 'yes' or
            float(signal.attrib['s']) != SIGNAL_STATION_M or
            float(signal.attrib['t']) != SIGNAL_LATERAL_M or lane is None):
        raise ValueError('Exact roadside signal or approach geometry differs')
    return {'road_id': 1, 'length_m': LENGTH_M, 'ego_lane_id': EGO_LANE_ID,
            'signal_station_m': SIGNAL_STATION_M, 'roadside_offset_m': abs(SIGNAL_LATERAL_M),
            'signal_specified': True, 'native_signal_instantiated': False,
            'highway_and_official_status_source_review_pending': True}
