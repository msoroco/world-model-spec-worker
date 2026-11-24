"""Authored one-way street and two separate curb parking segments."""
import json
import xml.etree.ElementTree as ET

CITY_SPACE = [[6.0, -7.0], [19.0, -7.0], [19.0, -3.5], [6.0, -3.5]]
OTHER_SPACE = [[-19.0, -7.0], [-6.0, -7.0], [-6.0, -3.5], [-19.0, -3.5]]


def geometry():
    return {'city_space_polygon_xy_m': CITY_SPACE, 'other_space_polygon_xy_m': OTHER_SPACE,
            'city_space_id': 'city-space-01', 'other_space_id': 'other-space-01',
            'road_kind': 'one_way_road', 'source_status': 'authored_geometry_pending_Native_readback'}


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C150129 one-way curb parking',
                  version='1.00', date='2026-11-23', north='0', south='0', east='50', west='-50')
    road = ET.SubElement(root, 'road', id='1', name='one-way-city-street', length='100', junction='-1')
    ET.SubElement(road, 'link')
    segment = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                            s='0', x='-50', y='0', hdg='0', length='100')
    ET.SubElement(segment, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation', s='0', a='8', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for lane_id, kind, width in ((-1, 'driving', 3.5), (-2, 'parking', 3.5)):
        lane = ET.SubElement(right, 'lane', id=str(lane_id), type=kind, level='false')
        ET.SubElement(lane, 'width', sOffset='0', a=str(width), b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='solid', color='white', width='.10')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    lanes = road.findall('lanes/laneSection/right/lane')
    if road.attrib['length'] != '100' or [(int(l.attrib['id']), l.attrib['type']) for l in lanes] != [(-1, 'driving'), (-2, 'parking')]:
        raise ValueError('one-way parking lane inventory differs')
    if CITY_SPACE[0][0] <= OTHER_SPACE[1][0] or CITY_SPACE[0][1] != OTHER_SPACE[0][1]:
        raise ValueError('parking segments overlap or differ laterally')
    return {'passed': True, 'road_length_m': 100, 'lane_ids': [-1, -2],
            'lane_types': ['driving', 'parking'], 'city_space_polygon_xy_m': CITY_SPACE,
            'other_space_polygon_xy_m': OTHER_SPACE,
            'native_map_readback_observed': False, 'designation_authority_observed': False}


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
