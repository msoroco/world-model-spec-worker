"""Author exact divided-road left-turn requests; no legal authority is inferred."""
import json
import math
import xml.etree.ElementTree as ET

CASES = {
    'through_opening': {'crossing_x_m': 0.0, 'physical_target': 'opening'},
    'across_divider': {'crossing_x_m': 12.0, 'physical_target': 'continuous_section'},
}
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))
MEDIAN_BOUNDS = [-20.0, -2.0, 20.0, 2.0]
OPENING_BOUNDS = [-3.0, -2.0, 3.0, 2.0]
BARRIER_BOUNDS = [[-20.0, -2.0, -3.0, 2.0], [3.0, -2.0, 20.0, 2.0]]


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4',
                  name='C124163-divided-median', version='1',
                  north='20', south='-20', east='70', west='-70',
                  vendor='worker-authored')
    for road_id, y, heading, start_x, name in (
            (1241631, -5.0, 0.0, -70.0, 'eastbound_right_hand_roadway'),
            (1241632, 5.0, math.pi, 70.0, 'westbound_right_hand_roadway')):
        road = ET.SubElement(root, 'road', id=str(road_id), name=name,
                             length='140', junction='-1')
        ET.SubElement(road, 'link')
        line = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                             s='0', x=str(start_x), y=str(y), hdg=str(heading),
                             length='140')
        ET.SubElement(line, 'line')
        ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                      s='0', a='0', b='0', c='0', d='0')
        lanes = ET.SubElement(road, 'lanes')
        ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
        section = ET.SubElement(lanes, 'laneSection', s='0')
        ET.SubElement(ET.SubElement(section, 'center'), 'lane', id='0',
                      type='none', level='false')
        lane = ET.SubElement(ET.SubElement(section, 'right'), 'lane', id='-1',
                             type='driving', level='false')
        ET.SubElement(lane, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
        objects = ET.SubElement(road, 'objects')
        if road_id == 1241631:
            for index, (xmin, _, xmax, _) in enumerate(BARRIER_BOUNDS):
                ET.SubElement(objects, 'object', id=str(index+1),
                              name='median_dividing_section_'+str(index+1),
                              type='barrier', s=str(xmin+70), t='5', zOffset='0',
                              hdg='0', pitch='0', roll='0',
                              length=str(xmax-xmin), width='4', height='0.25')
        ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def request(suffix):
    case = CASES[suffix]
    return {'format': 'worker-authored-median-left-turn-request',
            'case': suffix, 'source_map': open_drive(),
            'ego_blueprint': 'vehicle.tesla.model3',
            'start_xyz_m': [-25.0, -5.0, 1.5],
            'target_crossing_x_m': case['crossing_x_m'],
            'physical_target': case['physical_target'],
            'route_waypoints_xy_m': [[-25.0, -5.0],
                                     [case['crossing_x_m']-5, -5.0],
                                     [case['crossing_x_m'], -5.0],
                                     [case['crossing_x_m'], 5.0],
                                     [case['crossing_x_m']-5, 5.0]],
            'median_bounds_m': MEDIAN_BOUNDS,
            'opening_bounds_m': OPENING_BOUNDS,
            'barrier_bounds_m': BARRIER_BOUNDS,
            'public_authority_establishment': 'pending_original_source',
            'physical_realization': 'unverified',
            'rate_hz': 20, 'duration_s': 30, 'frames': 600,
            'cameras': [{'name': name, 'width': width, 'height': height}
                        for name, width, height in CAMERAS]}


def check(value):
    if value.get('format') != 'worker-authored-median-left-turn-request':
        raise ValueError('Wrong scene request format')
    suffix = value.get('case')
    if suffix not in CASES or value.get('target_crossing_x_m') != CASES[suffix]['crossing_x_m']:
        raise ValueError('Crossing station differs from selected case')
    root = ET.fromstring(value['source_map'])
    roads = root.findall('road')
    if {road.get('id') for road in roads} != {'1241631', '1241632'}:
        raise ValueError('Two directional roadways required')
    if any(len(road.findall('./lanes/laneSection/right/lane')) != 1
           for road in roads):
        raise ValueError('Directional lane missing')
    if len(root.findall('.//object[@type="barrier"]')) != 2:
        raise ValueError('Authored median dividing sections missing')
    if value['median_bounds_m'] != MEDIAN_BOUNDS or value['opening_bounds_m'] != OPENING_BOUNDS or value['barrier_bounds_m'] != BARRIER_BOUNDS:
        raise ValueError('Median or opening geometry changed')
    if {camera.get('name') for camera in value.get('cameras', [])} != {x[0] for x in CAMERAS}:
        raise ValueError('Four camera sources required')
    if (value.get('rate_hz'), value.get('duration_s'), value.get('frames')) != (20, 30, 600):
        raise ValueError('600-frame source plan required')
    if value.get('public_authority_establishment') != 'pending_original_source' or value.get('physical_realization') != 'unverified':
        raise ValueError('Authored request cannot establish authority or physics')
    return {'case': suffix, 'camera_count': 4, 'frames': 600,
            'source_kind': 'authored_not_native', 'authority_verified': False}


if __name__ == '__main__':
    print(json.dumps({suffix: check(request(suffix)) for suffix in CASES}, indent=2))
