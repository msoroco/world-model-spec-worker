"""Authored same-cell street intersection for an unmarked crossing draft."""
import xml.etree.ElementTree as ET

from geometry import open_drive as marked_open_drive


def open_drive():
    root = ET.fromstring(marked_open_drive())
    road = ET.SubElement(root, 'road', id='3', name='intersecting-business-street',
                         length='40', junction='7')
    ET.SubElement(road, 'link')
    ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                  s='0', x='21', y='-20', hdg='1.5707963267948966', length='40').append(ET.Element('line'))
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    for side, sign in (('left', 1), ('right', -1)):
        branch = ET.SubElement(section, side)
        lane = ET.SubElement(branch, 'lane', id=str(sign), type='driving', level='false')
        ET.SubElement(lane, 'width', sOffset='0', a='2', b='0', c='0', d='0')
        sidewalk = ET.SubElement(branch, 'lane', id=str(2*sign), type='sidewalk', level='false')
        ET.SubElement(sidewalk, 'width', sOffset='0', a='1.5', b='0', c='0', d='0')
    ET.SubElement(ET.SubElement(section, 'center'), 'lane', id='0', type='none', level='false')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    junction = ET.SubElement(root, 'junction', id='7', name='C188094 unmarked intersection')
    connection = ET.SubElement(junction, 'connection', id='1', incomingRoad='1',
                               connectingRoad='3', contactPoint='start')
    ET.SubElement(connection, 'laneLink', **{'from': '-1', 'to': '-1'})
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    roads = {r.get('id'): r for r in root.findall('road')}
    junction = root.find('junction')
    if set(roads) != {'1', '2', '3'} or junction is None or junction.get('id') != '7':
        raise ValueError('Same-cell unmarked intersection incomplete')
    if roads['3'].findall('lanes/laneSection/*/lane[@type="sidewalk"]') == []:
        raise ValueError('Intersecting sidewalk lanes absent')
    return {'road_id': 1, 'roadway_bounds_m': {'min_x': -100, 'max_x': 100, 'min_y': -4, 'max_y': 4},
            'crosswalk_bounds_m': {'min_x': -2, 'max_x': 2, 'min_y': -4, 'max_y': 4},
            'unmarked_crosswalk_bounds_m': {'min_x': 20, 'max_x': 22, 'min_y': -4, 'max_y': 4},
            'unmarked_junction_id': 7, 'overpass_deck_road_id': 2,
            'overpass_deck_height_m': 5, 'native_readback_observed': False,
            'business_district_sourced': False}


if __name__ == '__main__':
    print(check())
