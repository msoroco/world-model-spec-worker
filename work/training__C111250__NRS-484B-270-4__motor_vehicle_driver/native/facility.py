"""Authored C111250 intersection/cycle-facility proposal and saved-body metric.

Coordinates are engineering proposals, not an official designation or Native readback.
The motor lane remains beside the centerline; the cycle lane is its right neighbor.
"""
import math
import xml.etree.ElementTree as ET

INTERSECTION = (-7.0, 7.0)
MOTOR_LANE = (0.0, 3.5)
CYCLE_LANE = (3.5, 5.5)


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C111250-cycle-through-proposal',
                  version='1', date='2026-11-23', north='100', south='-100', east='100',
                  west='-100', vendor='full-train-worker')
    roads = ((1, 0, -100, math.pi/2, 93, -1), (2, 0, 7, math.pi/2, 93, -1),
             (3, -100, 0, 0, 93, -1), (4, 7, 0, 0, 93, -1),
             (13, 0, -7, math.pi/2, 14, 100), (14, -7, 0, 0, 14, 100))
    for ident, x, y, heading, length, junction in roads:
        road = ET.SubElement(root, 'road', id=str(ident), name='C111250_'+str(ident),
                             length=str(length), junction=str(junction))
        link = ET.SubElement(road, 'link')
        if ident in (1, 3):
            ET.SubElement(link, 'successor', elementType='junction', elementId='100')
        elif ident in (2, 4):
            ET.SubElement(link, 'predecessor', elementType='junction', elementId='100')
        else:
            incoming, outgoing = (1, 2) if ident == 13 else (3, 4)
            ET.SubElement(link, 'predecessor', elementType='road', elementId=str(incoming), contactPoint='end')
            ET.SubElement(link, 'successor', elementType='road', elementId=str(outgoing), contactPoint='start')
        geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry', s='0',
                                 x=str(x), y=str(y), hdg=str(heading), length=str(length))
        ET.SubElement(geometry, 'line')
        ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                      s='0', a='0', b='0', c='0', d='0')
        lanes = ET.SubElement(road, 'lanes')
        ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
        section = ET.SubElement(lanes, 'laneSection', s='0')
        left, center, right = (ET.SubElement(section, name) for name in ('left', 'center', 'right'))
        for group, lane_id, lane_type, width in ((left, 1, 'driving', 3.5),
                                                  (center, 0, 'none', 0),
                                                  (right, -1, 'driving', 3.5)):
            lane = ET.SubElement(group, 'lane', id=str(lane_id), type=lane_type, level='false')
            if width:
                ET.SubElement(lane, 'width', sOffset='0', a=str(width), b='0', c='0', d='0')
            if ident == 13 and lane_id:
                ll = ET.SubElement(lane, 'link')
                ET.SubElement(ll, 'predecessor', id=str(lane_id))
                ET.SubElement(ll, 'successor', id=str(lane_id))
            ET.SubElement(lane, 'roadMark', sOffset='0', type='solid' if lane_id == 0 else 'broken',
                          color='yellow' if lane_id == 0 else 'white', width='0.12')
        if ident in (1, 2, 13):
            cycle = ET.SubElement(right, 'lane', id='-2', type='biking', level='false')
            ET.SubElement(cycle, 'width', sOffset='0', a='2', b='0', c='0', d='0')
            ET.SubElement(cycle, 'roadMark', sOffset='0', type='solid', color='white', width='0.12')
            if ident == 13:
                ll = ET.SubElement(cycle, 'link')
                ET.SubElement(ll, 'predecessor', id='-2')
                ET.SubElement(ll, 'successor', id='-2')
        ET.SubElement(road, 'objects')
        ET.SubElement(road, 'signals')
    junction = ET.SubElement(root, 'junction', id='100', name='centerline-cycle-lane-intersection')
    for cid, incoming, connecting, lanes in ((0, 1, 13, (-1, -2)), (1, 3, 14, (-1,))):
        connection = ET.SubElement(junction, 'connection', id=str(cid),
                                   incomingRoad=str(incoming), connectingRoad=str(connecting),
                                   contactPoint='start')
        for lane in lanes:
            ET.SubElement(connection, 'laneLink', **{'from': str(lane), 'to': str(lane)})
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    if {r.attrib['id'] for r in root.findall('road')} != {'1', '2', '3', '4', '13', '14'}:
        raise ValueError('Intersection road inventory differs')
    if len(root.findall('junction/connection/laneLink')) != 3:
        raise ValueError('Cycle and motor through links missing')
    for road_id in ('1', '13', '2'):
        road = next(r for r in root.findall('road') if r.attrib['id'] == road_id)
        lanes = {l.attrib['id']: l for l in road.findall('lanes/laneSection/right/lane')}
        if lanes['-1'].attrib['type'] != 'driving' or lanes['-2'].attrib['type'] != 'biking':
            raise ValueError('Designated facility and adjacent motor lane differ')
    return {'passed': True, 'main_road_cycle_lane_ids': [-2, -2, -2],
            'centerline_preserved': True, 'intersection_y_m': INTERSECTION,
            'native_map_readback_observed': False, 'official_designation_proven': False}


def body_overlap(row):
    """Measure original/saved body overlap; this is not a legal threshold."""
    vertices = row['body_xy_m']
    if len(vertices) != 4 or any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in vertices):
        raise ValueError('Four finite saved body corners required')
    xs, ys = [p[0] for p in vertices], [p[1] for p in vertices]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    facility_width = max(0, min(xmax, CYCLE_LANE[1]) - max(xmin, CYCLE_LANE[0]))
    intersection_length = max(0, min(ymax, INTERSECTION[1]) - max(ymin, INTERSECTION[0]))
    return {'cycle_intersection_body_overlap_m2': round(facility_width * intersection_length, 6),
            'inside_intersection': intersection_length > 0,
            'cycle_lane_body_overlap_m': round(facility_width, 6),
            'speed_mps': row['speed_mps']}
