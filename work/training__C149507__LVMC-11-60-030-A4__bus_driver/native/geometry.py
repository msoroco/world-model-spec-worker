"""One-way curb lane and authored loading-zone geometry; legal designation pending."""
import xml.etree.ElementTree as ET

CURB_FACE_Y_M = -5.0
ZONE_X_M = (15.0, 25.0)


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C149507 bus loading',
                  version='1.00', date='2026-11-24', north='0', south='0', east='80', west='-80')
    road = ET.SubElement(root, 'road', id='1', name='one-way-bus-street', length='160', junction='-1')
    ET.SubElement(road, 'link')
    line = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                         s='0', x='-80', y='0', hdg='0', length='160')
    ET.SubElement(line, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='1', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    lane = ET.SubElement(right, 'lane', id='-1', type='driving', level='false')
    ET.SubElement(lane, 'width', sOffset='0', a='5', b='0', c='0', d='0')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    lanes = root.findall('road/lanes/laneSection/right/lane')
    if road.attrib['length'] != '160' or [(int(l.attrib['id']), l.attrib['type']) for l in lanes] != [(-1, 'driving')]:
        raise ValueError('one-way bus lane contract changed')
    if CURB_FACE_Y_M != -5 or not (ZONE_X_M[0] < 20 < ZONE_X_M[1]):
        raise ValueError('curb/loading-zone geometry changed')
    return {'road_id': 1, 'bus_lane_id': -1, 'curb_face_y_m': CURB_FACE_Y_M,
            'loading_zone_x_m': list(ZONE_X_M), 'native_readback_observed': False,
            'loading_zone_designation_observed': False}
