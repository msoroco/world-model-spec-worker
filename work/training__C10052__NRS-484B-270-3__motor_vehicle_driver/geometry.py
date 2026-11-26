"""Authored C10052 alley and bicycle-lane proposal, pending Native readback."""
import json
import xml.etree.ElementTree as ET

ROAD_ID = 1
DRIVING_LANE_ID = -1
BICYCLE_LANE_ID = -2
BICYCLE_BOUNDS_M = (-60.0, -5.0, 60.0, -3.0)
ALLEY_ENTRANCE_BOUNDS_M = (-3.0, -14.0, 3.0, -5.0)
STOP_X_M = -12.0
STOP_Y_M = {'probe_a': -1.5, 'probe_b': -4.0}
BODY_HALF_LENGTH_M = 2.6
BODY_HALF_WIDTH_M = 0.9


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4',
                  name='C10052-bicycle-lane-alley-proposal', version='1',
                  date='2026-11-05', north='30', south='-30', east='70',
                  west='-70', vendor='full-train-worker')
    for ident, x, y, heading, length, lane_widths in (
            (1, -60, 0, 0, 120, ((-1, 3.0, 'driving'), (-2, 2.0, 'biking'))),
            (2, 0, -5, -1.5707963267948966, 20,
             ((-1, 3.0, 'driving'),))):
        road = ET.SubElement(root, 'road', id=str(ident), name=f'C10052_{ident}',
                             length=str(length), junction='-1')
        ET.SubElement(road, 'link')
        geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                                 s='0', x=str(x), y=str(y), hdg=str(heading),
                                 length=str(length))
        ET.SubElement(geometry, 'line')
        ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                      s='0', a='0', b='0', c='0', d='0')
        lanes = ET.SubElement(road, 'lanes')
        ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
        section = ET.SubElement(lanes, 'laneSection', s='0')
        ET.SubElement(section, 'left')
        center = ET.SubElement(section, 'center')
        ET.SubElement(center, 'lane', id='0', type='none', level='false')
        right = ET.SubElement(section, 'right')
        for lane_id, width, lane_type in lane_widths:
            lane = ET.SubElement(right, 'lane', id=str(lane_id),
                                 type=lane_type, level='false')
            ET.SubElement(lane, 'width', sOffset='0', a=str(width), b='0', c='0', d='0')
            ET.SubElement(lane, 'roadMark', sOffset='0', type='broken',
                          color='white', width='0.12')
        ET.SubElement(road, 'objects')
        ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def route(suffix, start_x_m=-45.0):
    if suffix not in STOP_Y_M:
        raise ValueError('Unknown C10052 probe')
    if start_x_m not in (-45.0, -55.0):
        raise ValueError('Unknown proposed approach start')
    points = []
    for i in range(round((STOP_X_M-start_x_m)/0.1)+1):
        x = min(start_x_m + i * 0.1, STOP_X_M)
        alpha = max(0.0, min(1.0, (x + 30.0) / 10.0))
        y = -1.5 + alpha * (STOP_Y_M[suffix] + 1.5)
        points.append((round(x, 5), round(y, 5)))
    return points


def body(center_x, center_y, forward=(1.0, 0.0)):
    fx, fy = forward
    return [[center_x + long*fx - side*fy,
             center_y + long*fy + side*fx]
            for long, side in ((-BODY_HALF_LENGTH_M, -BODY_HALF_WIDTH_M),
                               (-BODY_HALF_LENGTH_M, BODY_HALF_WIDTH_M),
                               (BODY_HALF_LENGTH_M, BODY_HALF_WIDTH_M),
                               (BODY_HALF_LENGTH_M, -BODY_HALF_WIDTH_M))]


def check():
    root = ET.fromstring(open_drive())
    assert {int(r.attrib['id']) for r in root.findall('road')} == {1, 2}
    lane = root.find("road[@id='1']/lanes/laneSection/right/lane[@id='-2']")
    assert lane is not None and lane.attrib['type'] == 'biking'
    assert STOP_X_M + BODY_HALF_LENGTH_M < ALLEY_ENTRANCE_BOUNDS_M[0]
    for suffix in STOP_Y_M:
        points = route(suffix)
        assert points[0] == (-45.0, -1.5)
        assert points[-1] == (STOP_X_M, STOP_Y_M[suffix])
        assert max(abs(b[0] - a[0]) for a, b in zip(points, points[1:])) <= .100001
    assert route('probe_a')[:151] == route('probe_b')[:151]
    assert route('probe_a', -55.0)[0] == (-55.0, -1.5)
    a = body(STOP_X_M, STOP_Y_M['probe_a'])
    b = body(STOP_X_M, STOP_Y_M['probe_b'])
    assert min(p[1] for p in a) > BICYCLE_BOUNDS_M[3]
    assert min(p[1] for p in b) < BICYCLE_BOUNDS_M[3]
    return {'roads': [1, 2], 'route_points': 331,
            'shared_prefix_points': 151,
            'scope': 'authored geometry; bicycle designation and Native identity unverified'}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
