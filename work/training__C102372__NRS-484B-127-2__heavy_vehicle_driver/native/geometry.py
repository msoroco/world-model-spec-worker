"""Same-cell hill-crest truck-following geometry for unselected CPU diagnostics."""
import json
import xml.etree.ElementTree as ET

RATE_HZ = 20
FRAMES = 480
ROAD_LENGTH_M = 650.0
LANE_WIDTH_M = 4.0
LANE_Y_M = -2.0
EGO_START_X_M = 20.0
SPEED_MPS = 8.0
TRUCK_HALF_LENGTH_M = 6.0
TRUCK_HALF_WIDTH_M = 1.3
GAP_TARGET_M = {'probe_1': 165.0, 'probe_2': 140.0}
THRESHOLD_M = 500 * 0.3048


def body(x, y=LANE_Y_M):
    return [[x-TRUCK_HALF_LENGTH_M, y-TRUCK_HALF_WIDTH_M],
            [x-TRUCK_HALF_LENGTH_M, y+TRUCK_HALF_WIDTH_M],
            [x+TRUCK_HALF_LENGTH_M, y+TRUCK_HALF_WIDTH_M],
            [x+TRUCK_HALF_LENGTH_M, y-TRUCK_HALF_WIDTH_M]]


def positions(case, frame):
    if case not in GAP_TARGET_M or type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError('Unknown case or frame')
    ego_x = EGO_START_X_M + SPEED_MPS * frame / RATE_HZ
    lead_x = ego_x + 2 * TRUCK_HALF_LENGTH_M + GAP_TARGET_M[case]
    return ego_x, lead_x


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C102372-truck-follow-draft',
                  version='1', north='50', south='-50', east='700', west='-50', vendor='full-train-worker')
    road = ET.SubElement(root, 'road', id='1', name='C102372_follow', length=str(ROAD_LENGTH_M), junction='-1')
    ET.SubElement(road, 'link')
    geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                             s='0', x='0', y='0', hdg='0', length=str(ROAD_LENGTH_M))
    ET.SubElement(geometry, 'line')
    elevations = ET.SubElement(road, 'elevationProfile')
    ET.SubElement(elevations, 'elevation', s='0', a='0', b='0', c='0', d='0')
    ET.SubElement(elevations, 'elevation', s='100', a='0', b='0', c='0.0048', d='-0.000064')
    ET.SubElement(elevations, 'elevation', s='150', a='4', b='0', c='-0.0048', d='0.000064')
    ET.SubElement(elevations, 'elevation', s='200', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    left = ET.SubElement(section, 'left')
    opposing = ET.SubElement(left, 'lane', id='1', type='driving', level='false')
    ET.SubElement(opposing, 'width', sOffset='0', a=str(LANE_WIDTH_M), b='0', c='0', d='0')
    ET.SubElement(opposing, 'roadMark', sOffset='0', type='solid', color='yellow', width='0.12')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    lane = ET.SubElement(right, 'lane', id='-1', type='driving', level='false')
    ET.SubElement(lane, 'width', sOffset='0', a=str(LANE_WIDTH_M), b='0', c='0', d='0')
    ET.SubElement(lane, 'roadMark', sOffset='0', type='broken', color='white', width='0.12')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    assert road is not None and road.attrib['id'] == '1'
    assert len(road.findall('lanes/laneSection/right/lane')) == 1
    assert len(road.findall('lanes/laneSection/left/lane')) == 1
    assert road.find('planView/geometry/line') is not None
    elevation = road.findall('elevationProfile/elevation')
    assert [float(node.attrib['s']) for node in elevation] == [0, 100, 150, 200]
    assert float(elevation[2].attrib['a']) == 4
    assert abs(float(elevation[1].attrib['c'])*50**2 + float(elevation[1].attrib['d'])*50**3 - 4) < 1e-9
    assert abs(4 + float(elevation[2].attrib['c'])*50**2 + float(elevation[2].attrib['d'])*50**3) < 1e-9
    for case, gap in GAP_TARGET_M.items():
        for frame in (0, FRAMES-1):
            ego, lead = positions(case, frame)
            assert 0 < ego-TRUCK_HALF_LENGTH_M
            assert lead+TRUCK_HALF_LENGTH_M < ROAD_LENGTH_M
            for polygon in (body(ego), body(lead)):
                assert all(0 < x < ROAD_LENGTH_M and -LANE_WIDTH_M < y < 0 for x, y in polygon)
            assert abs((lead-TRUCK_HALF_LENGTH_M)-(ego+TRUCK_HALF_LENGTH_M)-gap) < 1e-9
    assert GAP_TARGET_M['probe_2'] < THRESHOLD_M < GAP_TARGET_M['probe_1']
    return {'passed': True, 'frames': FRAMES, 'rate_hz': RATE_HZ,
            'threshold_m': THRESHOLD_M, 'gaps_m': GAP_TARGET_M,
            'scope': 'authored geometry and commanded positions, no Native truck or legal proof'}


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
