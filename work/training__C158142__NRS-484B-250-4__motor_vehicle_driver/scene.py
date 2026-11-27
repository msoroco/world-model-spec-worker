"""Exact authored no-stop-line intersection for C158142.

OpenDRIVE readback and original pixels remain mandatory at Native execution.
"""
import math
import xml.etree.ElementTree as ET

RATE_HZ = 20
FRAMES = 600
NEAR_CROSSWALK_X = -12.0
INTERSECTION_ENTRY_X = -7.0
EGO_LANE_Y = -1.75
OTHER_LANE_X = 1.75


def road_xml():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4',
                  name='C158142-inoperative-crosswalk', version='1', date='2026-11-25',
                  north='100', south='-100', east='100', west='-100', vendor='worker')
    roads = ((1, -100, 0, 0, 93, -1), (2, 7, 0, 0, 93, -1),
             (3, 0, -100, math.pi / 2, 93, -1),
             (4, 0, 7, math.pi / 2, 93, -1),
             (13, -7, 0, 0, 14, 100), (14, 0, -7, math.pi / 2, 14, 100))
    for ident, x, y, heading, length, junction in roads:
        road = ET.SubElement(root, 'road', id=str(ident), name=f'c158142_{ident}',
                             length=str(length), junction=str(junction))
        link = ET.SubElement(road, 'link')
        if ident in (1, 3):
            ET.SubElement(link, 'successor', elementType='junction', elementId='100')
        elif ident in (2, 4):
            ET.SubElement(link, 'predecessor', elementType='junction', elementId='100')
        else:
            before, after = (1, 2) if ident == 13 else (3, 4)
            ET.SubElement(link, 'predecessor', elementType='road',
                          elementId=str(before), contactPoint='end')
            ET.SubElement(link, 'successor', elementType='road',
                          elementId=str(after), contactPoint='start')
        geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                                 s='0', x=str(x), y=str(y), hdg=str(heading),
                                 length=str(length))
        ET.SubElement(geometry, 'line')
        ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                      s='0', a='0', b='0', c='0', d='0')
        lanes = ET.SubElement(road, 'lanes')
        ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
        section = ET.SubElement(lanes, 'laneSection', s='0')
        for side, lane_id in (('left', 1), ('center', 0), ('right', -1)):
            group = ET.SubElement(section, side)
            lane = ET.SubElement(group, 'lane', id=str(lane_id),
                                 type='none' if lane_id == 0 else 'driving', level='false')
            if lane_id:
                if ident in (13, 14):
                    lane_link = ET.SubElement(lane, 'link')
                    ET.SubElement(lane_link, 'predecessor', id=str(lane_id))
                    ET.SubElement(lane_link, 'successor', id=str(lane_id))
                ET.SubElement(lane, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
            ET.SubElement(lane, 'roadMark', sOffset='0', type='solid' if lane_id == 0
                          else 'broken', color='yellow' if lane_id == 0 else 'white',
                          width='0.12')
        objects = ET.SubElement(road, 'objects')
        if ident == 1:
            # Near side crosswalk, spanning both incoming and opposing lanes.
            ET.SubElement(objects, 'object', id='301', name='near-side-crosswalk',
                          type='crosswalk', s='89.5', t='0', zOffset='0', hdg='0',
                          length='3', width='7', height='0')
        signals = ET.SubElement(road, 'signals')
        if ident == 1:
            ET.SubElement(signals, 'signal', id='401', name='ego-vehicular-head',
                          s='84', t='-4.2', zOffset='4.5', hOffset='0',
                          orientation='+', dynamic='yes', country='OpenDRIVE',
                          type='1000001', subtype='1')
    junction = ET.SubElement(root, 'junction', id='100', name='four-way')
    for index, incoming, connector in ((0, 1, 13), (1, 3, 14)):
        connection = ET.SubElement(junction, 'connection', id=str(index),
                                   incomingRoad=str(incoming),
                                   connectingRoad=str(connector), contactPoint='start')
        for lane in (-1, 1):
            ET.SubElement(connection, 'laneLink', **{'from': str(lane), 'to': str(lane)})
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(road_xml())
    roads = {int(road.attrib['id']): road for road in root.findall('road')}
    if set(roads) != {1, 2, 3, 4, 13, 14}:
        raise ValueError('intersection roads missing')
    if len(root.findall('junction/connection')) != 2:
        raise ValueError('through connections missing')
    crosswalk = roads[1].find("objects/object[@id='301']")
    if crosswalk is None or crosswalk.attrib['type'] != 'crosswalk':
        raise ValueError('near-side crosswalk object missing')
    if -100 + float(crosswalk.attrib['s']) - float(crosswalk.attrib['length']) / 2 != NEAR_CROSSWALK_X:
        raise ValueError('crosswalk near edge differs')
    if root.findall(".//object[@type='stopLine']") or root.findall(".//signal[@type='294']"):
        raise ValueError('selected branch has no stop line')
    signal = roads[1].find("signals/signal[@id='401']")
    if signal is None or signal.attrib['dynamic'] != 'yes':
        raise ValueError('installed signal specification missing')
    return {'passed': True, 'frames': FRAMES, 'rate_hz': RATE_HZ,
            'crosswalk_near_x_m': NEAR_CROSSWALK_X,
            'intersection_entry_x_m': INTERSECTION_ENTRY_X,
            'no_authored_stop_line': True, 'signal_specified': True,
            'native_signal_instantiated': False, 'physical_pixels_verified': False}


if __name__ == '__main__':
    import json
    print(json.dumps(check()))
