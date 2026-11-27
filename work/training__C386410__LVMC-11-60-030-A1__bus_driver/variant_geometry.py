"""One-way curb variants with distinct physical markers, no claimed authority."""
import json
import xml.etree.ElementTree as ET

ZONE_X_M = [-2.0, 20.0]
MARKERS = {'bus_stop': ('BUS STOP', 'bus_stop'),
           'bus_stand': ('BUS STAND', 'bus_stand'),
           'route_origin': ('BUS ROUTE ORIGIN', 'origin_destination'),
           'route_destination': ('BUS ROUTE TERMINUS', 'origin_destination'),
           'other_street': ('BUS ROUTE TERMINUS', 'origin_destination')}

def open_drive(kind='route_destination'):
    if kind not in MARKERS:
        raise ValueError('Unsupported physical curb marker')
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C386410-route-standing', version='1', date='2026-11-23', north='20', south='-20', east='100', west='-100', vendor='full-train-worker')
    road = ET.SubElement(root, 'road', id='1', name='one-way-route-street', length='200', junction='-1')
    ET.SubElement(road, 'link')
    geom = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry', s='0', x='-100', y='0', hdg='0', length='200')
    ET.SubElement(geom, 'line')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(ET.SubElement(section, 'center'), 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for lane_id, lane_type in ((-1, 'driving'), (-2, 'parking')):
        lane = ET.SubElement(right, 'lane', id=str(lane_id), type=lane_type, level='false')
        ET.SubElement(lane, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='solid', color='white', width='.12')
    ET.SubElement(road, 'objects')
    signals = ET.SubElement(road, 'signals')
    ET.SubElement(signals, 'signal', id='301', s='98', t='-8', name=MARKERS[kind][0], dynamic='no', orientation='+', zOffset='2', country='USA', type='bus_zone_marker', subtype=MARKERS[kind][1], value='0', unit='none', hOffset='0', pitch='0', roll='0')
    return ET.tostring(root, encoding='unicode')

def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    lanes = road.findall('lanes/laneSection/right/lane')
    signs = road.findall('signals/signal')
    if road.attrib['length'] != '200' or [(x.attrib['id'], x.attrib['type']) for x in lanes] != [('-1', 'driving'), ('-2', 'parking')]:
        raise ValueError('residential route geometry changed')
    if len(signs) != 1 or signs[0].attrib['name'] != 'BUS ROUTE TERMINUS' or signs[0].attrib['orientation'] != '+':
        raise ValueError('route terminus marker changed')
    for kind, (name, subtype) in MARKERS.items():
        marker = ET.fromstring(open_drive(kind)).find('.//signal')
        if marker.attrib['name'] != name or marker.attrib['subtype'] != subtype:
            raise ValueError('Exact curb marker differs: ' + kind)
    return {'passed': True, 'zone_x_m': ZONE_X_M, 'parking_lane_id': -2, 'sign_declares_duration': False, 'official_designation_verified': False}

if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
