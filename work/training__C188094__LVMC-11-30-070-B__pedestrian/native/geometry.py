"""At-grade crosswalk and nearby raised overpass proposal for C188094."""
import xml.etree.ElementTree as ET


def _lane(section, side, lane_id):
    lane = ET.SubElement(ET.SubElement(section, side), 'lane', id=str(lane_id), type='driving', level='false')
    ET.SubElement(lane, 'width', sOffset='0', a='4', b='0', c='0', d='0')


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C188094 overpass crossing',
                  version='1.00', date='2026-11-24', north='100', south='-100', east='100', west='-100')
    road = ET.SubElement(root, 'road', id='1', name='paved-road', length='200', junction='-1')
    ET.SubElement(road, 'link')
    ET.SubElement(ET.SubElement(road, 'planView'), 'geometry', s='0', x='-100', y='0', hdg='0', length='200').append(ET.Element('line'))
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation', s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    _lane(section, 'left', 1)
    ET.SubElement(ET.SubElement(section, 'center'), 'lane', id='0', type='none', level='false')
    _lane(section, 'right', -1)
    objects = ET.SubElement(road, 'objects')
    ET.SubElement(objects, 'object', id='101', name='marked-crosswalk', type='crosswalk',
                  s='98', t='0', zOffset='0', hdg='0', length='4', width='8', height='0')
    ET.SubElement(road, 'signals')
    deck = ET.SubElement(root, 'road', id='2', name='pedestrian-overpass-deck', length='30', junction='-1')
    ET.SubElement(deck, 'link')
    ET.SubElement(ET.SubElement(deck, 'planView'), 'geometry', s='0', x='30', y='-15', hdg='1.5707963267948966', length='30').append(ET.Element('line'))
    ET.SubElement(ET.SubElement(deck, 'elevationProfile'), 'elevation', s='0', a='5', b='0', c='0', d='0')
    dlanes = ET.SubElement(deck, 'lanes')
    ET.SubElement(dlanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    ds = ET.SubElement(dlanes, 'laneSection', s='0')
    ET.SubElement(ds, 'left')
    ET.SubElement(ET.SubElement(ds, 'center'), 'lane', id='0', type='none', level='false')
    walk = ET.SubElement(ET.SubElement(ds, 'right'), 'lane', id='-1', type='sidewalk', level='false')
    ET.SubElement(walk, 'width', sOffset='0', a='3', b='0', c='0', d='0')
    ET.SubElement(deck, 'objects')
    ET.SubElement(deck, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    roads = root.findall('road')
    crosswalk = roads[0].find('objects/object')
    if len(roads) != 2 or crosswalk.attrib['type'] != 'crosswalk' or roads[1].find('elevationProfile/elevation').attrib['a'] != '5':
        raise ValueError('crosswalk/overpass geometry changed')
    return {'road_id': 1, 'roadway_bounds_m': {'min_x': -100, 'max_x': 100, 'min_y': -4, 'max_y': 4},
            'crosswalk_bounds_m': {'min_x': -2, 'max_x': 2, 'min_y': -4, 'max_y': 4},
            'overpass_deck_road_id': 2, 'overpass_deck_height_m': 5,
            'business_district_sourced': False, 'native_readback_observed': False}
