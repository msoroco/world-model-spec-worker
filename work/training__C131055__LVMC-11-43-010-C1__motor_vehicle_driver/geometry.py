"""Two-lane authored roundabout geometry; original Native map readback remains required."""
import json
import math
import xml.etree.ElementTree as ET

REFERENCE_RADIUS_M = 10.0
LANE_WIDTH_M = 4.0
QUARTER_M = math.pi * REFERENCE_RADIUS_M / 2


def lane(section, lane_id):
    right = section.find('right')
    if right is None:
        right = ET.SubElement(section, 'right')
    item = ET.SubElement(right, 'lane', id=str(lane_id), type='driving', level='false')
    ET.SubElement(item, 'width', sOffset='0', a=str(LANE_WIDTH_M), b='0', c='0', d='0')
    ET.SubElement(item, 'roadMark', sOffset='0', type='broken', color='white', width='.10')


def road(root, ident, name, x, y, heading, length, curve=None):
    item = ET.SubElement(root, 'road', id=str(ident), name=name, length=f'{length:.9f}', junction='-1')
    geo = ET.SubElement(ET.SubElement(item, 'planView'), 'geometry', s='0', x=str(x), y=str(y),
                        hdg=str(heading), length=f'{length:.9f}')
    if curve is None:
        ET.SubElement(geo, 'line')
    else:
        ET.SubElement(geo, 'arc', curvature=str(curve))
    ET.SubElement(ET.SubElement(item, 'elevationProfile'), 'elevation', s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(item, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(ET.SubElement(section, 'center'), 'lane', id='0', type='none', level='false')
    lane(section, -1)
    lane(section, -2)
    return item


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C131055 two-lane roundabout',
                  version='1.00', north='60', south='-60', east='60', west='-60')
    starts = ((0, -REFERENCE_RADIUS_M, 0), (REFERENCE_RADIUS_M, 0, math.pi / 2),
              (0, REFERENCE_RADIUS_M, math.pi), (-REFERENCE_RADIUS_M, 0, 3 * math.pi / 2))
    for index, (x, y, heading) in enumerate(starts, 1):
        ring = road(root, index, 'circulatory-quarter-'+str(index), x, y, heading,
                    QUARTER_M, 1 / REFERENCE_RADIUS_M)
        links = ET.SubElement(ring, 'link')
        ET.SubElement(links, 'predecessor', elementType='road',
                      elementId=str(4 if index == 1 else index-1), contactPoint='end')
        ET.SubElement(links, 'successor', elementType='road',
                      elementId=str(1 if index == 4 else index+1), contactPoint='start')
    approach = road(root, 5, 'south-entry', 0, -48, math.pi/2, 30)
    ET.SubElement(ET.SubElement(approach, 'link'), 'successor', elementType='road', elementId='1', contactPoint='start')
    road(root, 6, 'west-exit', -18, 0, math.pi, 30)
    road(root, 7, 'south-u-turn-exit', 0, -18, -math.pi/2, 30)
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    roads = root.findall('road')
    if len(roads) != 7 or any(road.find('planView/geometry/arc') is None for road in roads[:4]):
        raise ValueError('Four-quarter ring absent')
    if any({lane.attrib['id'] for lane in road.findall('lanes/laneSection/right/lane')} != {'-1','-2'} for road in roads):
        raise ValueError('Two circulatory lanes absent')
    if abs(sum(float(road.attrib['length']) for road in roads[:4]) - 2*math.pi*REFERENCE_RADIUS_M) > 1e-6:
        raise ValueError('Ring circumference differs')
    return {'authored_inner_center_radius_m':12,'authored_outer_center_radius_m':16,
            'ring_quarters':4,'entry_road':5,'west_exit_road':6,'south_exit_road':7,
            'native_topology_verified':False,'physical_completion_claimed':False}


if __name__ == '__main__':
    print(json.dumps(check(),sort_keys=True))
