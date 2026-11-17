"""Authored two-way rail approach road; rail assets are spawned separately."""
import xml.etree.ElementTree as ET


ROAD_ID = 177225
ROAD_START_X_M = -100.0
ROAD_LENGTH_M = 200.0
LANE_WIDTH_M = 3.5


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4',
                  name='C177225-directed-rail-crossing-draft', version='1',
                  north='15', south='-15', east='100', west='-100',
                  vendor='full-train-worker')
    road = ET.SubElement(root, 'road', id=str(ROAD_ID),
                         name='C177225_two_way_approach',
                         length=str(ROAD_LENGTH_M), junction='-1')
    ET.SubElement(road, 'link')
    geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                             s='0', x=str(ROAD_START_X_M), y='0', hdg='0',
                             length=str(ROAD_LENGTH_M))
    ET.SubElement(geometry, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    for side, ident in (('left', 1), ('center', 0), ('right', -1)):
        group = ET.SubElement(section, side)
        lane = ET.SubElement(group, 'lane', id=str(ident),
                             type='none' if ident == 0 else 'driving', level='false')
        if ident:
            ET.SubElement(lane, 'width', sOffset='0', a=str(LANE_WIDTH_M),
                          b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0',
                      type='solid' if ident == 0 else 'broken',
                      color='yellow' if ident == 0 else 'white', width='0.12')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def validate_authored_road():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    if root.tag != 'OpenDRIVE' or road is None or road.attrib['id'] != str(ROAD_ID):
        raise ValueError('Authored rail approach road missing')
    if road.find('planView/geometry/line') is None:
        raise ValueError('Rail approach lacks straight road geometry')
    lanes = road.findall('lanes/laneSection/*/lane')
    if {lane.attrib['id'] for lane in lanes} != {'-1', '0', '1'}:
        raise ValueError('Both bus driving approaches are required')
    if ROAD_START_X_M > -70 or ROAD_START_X_M + ROAD_LENGTH_M < 70:
        raise ValueError('Road does not contain both bus starts')
    return {'road_id': ROAD_ID, 'driving_lane_ids': [-1, 1],
            'bus_start_stations_m': [-70, 70],
            'scope': 'authored OpenDRIVE only; Native readback pending'}
